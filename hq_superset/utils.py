import ast
import secrets
import string
import sys
from contextlib import contextmanager
from datetime import date, datetime
from functools import partial
from typing import Any, Generator
from zipfile import ZipFile

import pandas
import sqlalchemy
from cryptography.fernet import Fernet
from flask import current_app
from flask_login import current_user
from sqlalchemy.sql import TableClause
from superset.utils.database import get_or_create_db

from .const import HQ_DATABASE_NAME
from .exceptions import DatabaseMissing

DOMAIN_PREFIX = "hqdomain_"
SESSION_USER_DOMAINS_KEY = "user_hq_domains"
SESSION_OAUTH_RESPONSE_KEY = "oauth_response"


def get_hq_database():
    """
    Returns the user-created database for datasets imported from
    CommCare HQ. If it has not been created and its URI is set in
    ``superset_config``, it will create it. Otherwise, it will raise a
    ``DatabaseMissing`` exception.
    """
    from superset import app, db
    from superset.models.core import Database

    try:
        return (
            db.session
            .query(Database)
            .filter_by(database_name=HQ_DATABASE_NAME)
            .one()
        )
    except sqlalchemy.orm.exc.NoResultFound:
        db_uri = app.config.get('HQ_DATABASE_URI')
        if db_uri:
            return get_or_create_db(HQ_DATABASE_NAME, db_uri)
        raise DatabaseMissing('CommCare HQ database missing')


def get_schema_name_for_domain(domain):
    # Prefix in-case domain name matches with know schemas such as public
    return f"{DOMAIN_PREFIX}{domain}"


def get_role_name_for_domain(domain):
    # Prefix in-case domain name matches with known role names such as admin
    # Same prefix pattern as schema only by coincidence, not a must.
    return f"{DOMAIN_PREFIX}{domain}"


def get_column_dtypes(datasource_defn):
    """
    Maps UCR column data types to Pandas data types.

    See corehq/apps/userreports/datatypes.py for possible data types.
    """
    # TODO: How are array indicators handled in CSV export?
    pandas_dtypes = {
        'date': 'datetime64[ns]',
        'datetime': 'datetime64[ns]',
        'string': 'string',
        'integer': 'Int64',
        'decimal': 'Float64',
        'small_integer': 'Int8',  # TODO: Is this true?
    }
    column_dtypes = {'doc_id': 'string'}
    date_columns = ['inserted_at']
    array_type_columns = []
    for ind in datasource_defn['configured_indicators']:
        indicator_datatype = ind.get('datatype', 'string')

        if indicator_datatype == "array":
            array_type_columns.append(ind['column_id'])
        elif pandas_dtypes[indicator_datatype] == 'datetime64[ns]':
            # the dtype datetime64[ns] is not supported for parsing,
            # pass this column using parse_dates instead
            date_columns.append(ind['column_id'])
        else:
            column_dtypes[ind['column_id']] = pandas_dtypes[indicator_datatype]
    return column_dtypes, date_columns, array_type_columns


def parse_date(date_str):
    """
    Simple, fast date parser for dates formatted by CommCare HQ.

    >>> parse_date('2022-02-24 12:29:19.450137')
    datetime.datetime(2022, 2, 24, 12, 29, 19, 450137)
    >>> parse_date('2022-02-22')
    datetime.date(2022, 2, 22)
    >>> parse_date('not a date')
    'not a date'

    """
    if pandas.isna(date_str):
        # data is missing/None
        return None
    try:
        if len(date_str) > 10:
            return datetime.fromisoformat(date_str)
        else:
            return date.fromisoformat(date_str)
    except ValueError:
        return date_str


class DomainSyncUtil:

    def __init__(self, security_manager):
        self.sm = security_manager

    def _ensure_domain_role_created(self, domain):
        # This inbuilt method creates only if the role doesn't exist.
        return self.sm.add_role(get_role_name_for_domain(domain))

    def _ensure_schema_perm_created(self, domain):
        menu_name = self.sm.get_schema_perm(get_hq_database(), get_schema_name_for_domain(domain))
        permission = self.sm.find_permission_view_menu("schema_access", menu_name)
        if not permission:
            permission = self.sm.add_permission_view_menu("schema_access", menu_name)
        return permission

    @staticmethod
    def _ensure_schema_created(domain):
        schema_name = get_schema_name_for_domain(domain)
        database = get_hq_database()
        with database.get_sqla_engine_with_context() as engine:
            if not engine.dialect.has_schema(engine, schema_name):
                engine.execute(sqlalchemy.schema.CreateSchema(schema_name))

    def re_eval_roles(self, existing_roles, new_domain_role):
        # Filter out other domain roles
        new_domain_roles = [
            r
            for r in existing_roles
            if not r.name.startswith(DOMAIN_PREFIX)
        ] + [new_domain_role]
        additional_roles = [
            self.sm.add_role(r)
            for r in self.sm.appbuilder.app.config['AUTH_USER_ADDITIONAL_ROLES']
        ]
        return new_domain_roles + additional_roles

    def sync_domain_role(self, domain):
        # This creates DB schema, role and schema permissions for the domain and
        #   assigns the role to the current_user
        self._ensure_schema_created(domain)
        permission = self._ensure_schema_perm_created(domain)
        role = self._ensure_domain_role_created(domain)
        self.sm.add_permission_role(role, permission)
        current_user.roles = self.re_eval_roles(current_user.roles, role)
        self.sm.get_session.add(current_user)
        self.sm.get_session.commit()


@contextmanager
def get_datasource_file(path):
    with ZipFile(path) as zipfile:
        filename = zipfile.namelist()[0]
        yield zipfile.open(filename)


def get_fernet_keys():
    return [
        Fernet(encoded(key, 'ascii'))
        for key in current_app.config['FERNET_KEYS']
    ]


def encoded(string_maybe, encoding):
    """
    Returns ``string_maybe`` encoded with ``encoding``, otherwise
    returns it unchanged.

    >>> encoded('abc', 'utf-8')
    b'abc'
    >>> encoded(b'abc', 'ascii')
    b'abc'
    >>> encoded(123, 'utf-8')
    123

    """
    if hasattr(string_maybe, 'encode'):
        return string_maybe.encode(encoding)
    return string_maybe


def convert_to_array(string_array):
    """
    Converts the string representation of a list to a list.
    >>> convert_to_array("['hello', 'world']")
    ['hello', 'world']

    >>> convert_to_array("'hello', 'world'")
    ['hello', 'world']

    >>> convert_to_array("[None]")
    []

    >>> convert_to_array("hello, world")
    []
    """

    def array_is_falsy(array_values):
        return not array_values or array_values == [None]

    try:
        array_values = ast.literal_eval(string_array)
    except ValueError:
        return []

    if isinstance(array_values, tuple):
        array_values = list(array_values)

    # Test for corner cases
    if array_is_falsy(array_values):
        return []

    return array_values


def js_to_py_datetime(jsdt, preserve_tz=True):
    """
    JavaScript UTC datetimes end in "Z". In Python < 3.11,
    ``datetime.isoformat()`` doesn't like it, and raises
    "ValueError: Invalid isoformat string"

    >>> jsdt = '2024-02-24T14:01:25.397469Z'
    >>> js_to_py_datetime(jsdt)
    datetime.datetime(2024, 2, 24, 14, 1, 25, 397469, tzinfo=datetime.timezone.utc)
    >>> js_to_py_datetime(jsdt, preserve_tz=False)
    datetime.datetime(2024, 2, 24, 14, 1, 25, 397469)
    >>> js_to_py_datetime(None) is None
    True

    """
    if jsdt is None or jsdt == '':
        return None
    if preserve_tz:
        if sys.version_info >= (3, 11):
            return datetime.fromisoformat(jsdt)
        pydt = jsdt.replace('Z', '+00:00')
    else:
        pydt = jsdt.replace('Z', '')
    return datetime.fromisoformat(pydt)


def cast_data_for_table(
    data: list[dict[str, Any]],
    table: TableClause,
) -> Generator[dict[str, Any], None, None]:
    """
    Returns ``data`` with values cast in the correct data types for
    the columns of ``table``.
    """
    cast_functions = {
        # 'BIGINT': int,
        # 'TEXT': str,
        'TIMESTAMP': partial(js_to_py_datetime, preserve_tz=False),
        # TODO: What else?
    }

    column_types = {c.name: str(c.type) for c in table.columns}
    for row in data:
        cast_row = {}
        for column, value in row.items():
            type_name = column_types[column]
            if type_name in cast_functions:
                cast_func = cast_functions[type_name]
                cast_row[column] = cast_func(value)
            else:
                cast_row[column] = value
        yield cast_row


def generate_secret():
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for __ in range(64))
