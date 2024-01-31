import ast
import os
from contextlib import contextmanager
from datetime import date, datetime
from zipfile import ZipFile

import pandas
import sqlalchemy
from flask import g
from flask_login import current_user
from sqlalchemy.dialects import postgresql

from .models import DataSetChange

DOMAIN_PREFIX = "hqdomain_"
SESSION_USER_DOMAINS_KEY = "user_hq_domains"
SESSION_OAUTH_RESPONSE_KEY = "oauth_response"
HQ_DB_CONNECTION_NAME = "HQ Data"
ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES = 5_000_000  # ~5MB


def get_datasource_export_url(domain, datasource_id):
    return f"a/{domain}/configurable_reports/data_sources/export/{datasource_id}/?format=csv"


class CCHQApiException(Exception):
    pass



def get_hq_database():
    # Todo; cache to avoid multiple lookups in single request
    from superset import db
    from superset.models.core import Database

    try:
        hq_db = (
            db.session
            .query(Database)
            .filter_by(database_name=HQ_DB_CONNECTION_NAME)
            .one()
        )
    except sqlalchemy.orm.exc.NoResultFound as err:
        raise CCHQApiException('CommCare HQ database missing') from err
    return hq_db


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


class AsyncImportHelper:
    def __init__(self, domain, datasource_id):
        self.domain = domain
        self.datasource_id = datasource_id

    @property
    def progress_key(self):
        return f"{self.domain}_{self.datasource_id}_import_task_id"

    @property
    def task_id(self):
        from superset.extensions import cache_manager

        return cache_manager.cache.get(self.progress_key)

    def is_import_in_progress(self):
        if not self.task_id:
            return False
        from celery.result import AsyncResult
        res = AsyncResult(self.task_id)
        return not res.ready()

    def mark_as_in_progress(self, task_id):
        from superset.extensions import cache_manager

        cache_manager.cache.set(self.progress_key, task_id)

    def mark_as_complete(self):
        from superset.extensions import cache_manager

        cache_manager.cache.delete(self.progress_key)


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


def download_datasource(domain, datasource_id):
    import superset

    from hq_superset.hq_requests import HQRequest, HqUrl
    from hq_superset.tasks import subscribe_to_hq_datasource_task

    hq_request = HQRequest(
        url=HqUrl.datasource_export_url(domain, datasource_id),
    )
    response = hq_request.get()
    if response.status_code != 200:
        raise CCHQApiException("Error downloading the UCR export from HQ")

    filename = f"{datasource_id}_{datetime.now()}.zip"
    path = os.path.join(superset.config.SHARED_DIR, filename)

    with open(path, "wb") as f:
        f.write(response.content)

    subscribe_to_hq_datasource_task.delay(domain, datasource_id)

    return path, len(response.content)


def get_datasource_defn(domain, datasource_id):
    from hq_superset.hq_requests import HQRequest, HqUrl

    hq_request = HQRequest(url=HqUrl.datasource_details_url(domain, datasource_id))
    response = hq_request.get()

    if response.status_code != 200:
        raise CCHQApiException("Error downloading the UCR definition from HQ")
    return response.json()


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


def refresh_hq_datasource(
    domain,
    datasource_id,
    display_name,
    file_path,
    datasource_defn,
    user_id=None,
):
    """
    Pulls the data from CommCare HQ and creates/replaces the
    corresponding Superset dataset
    """
    # See `CsvToDatabaseView.form_post()` in
    # https://github.com/apache/superset/blob/master/superset/views/database/views.py

    import superset
    from superset import db
    from superset.connectors.sqla.models import SqlaTable
    from superset.sql_parse import Table

    database = get_hq_database()
    schema = get_schema_name_for_domain(domain)
    csv_table = Table(table=datasource_id, schema=schema)
    column_dtypes, date_columns, array_columns = get_column_dtypes(
        datasource_defn
    )

    converters = {
        column_name: convert_to_array for column_name in array_columns
    }
    # TODO: can we assume all array values will be of type TEXT?
    sqlconverters = {
        column_name: postgresql.ARRAY(sqlalchemy.types.TEXT)
        for column_name in array_columns
    }

    def to_sql(df, replace=False):
        database.db_engine_spec.df_to_sql(
            database,
            csv_table,
            df,
            to_sql_kwargs={
                "if_exists": "replace" if replace else "append",
                "dtype": sqlconverters,
            },
        )

    try:
        with get_datasource_file(file_path) as csv_file:

            _iter = pandas.read_csv(
                chunksize=10000,
                filepath_or_buffer=csv_file,
                encoding="utf-8",
                parse_dates=date_columns,
                date_parser=parse_date,
                keep_default_na=True,
                dtype=column_dtypes,
                converters=converters,
                iterator=True,
                low_memory=True,
            )

            to_sql(next(_iter), replace=True)

            for df in _iter:
                to_sql(df, replace=False)

        explore_database = get_explore_database(database)
        sqla_table = (
            db.session.query(SqlaTable)
            .filter_by(
                table_name=datasource_id,
                schema=csv_table.schema,
                database_id=explore_database.id,
            )
            .one_or_none()
        )
        if sqla_table:
            sqla_table.description = display_name
            sqla_table.fetch_metadata()
        if not sqla_table:
            sqla_table = SqlaTable(table_name=datasource_id)
            # Store display name from HQ into description since
            #   sqla_table.table_name stores datasource_id
            sqla_table.description = display_name
            sqla_table.database = explore_database
            sqla_table.database_id = database.id
            if user_id:
                user = superset.appbuilder.sm.get_user_by_id(user_id)
            else:
                user = g.user
            sqla_table.owners = [user]
            sqla_table.user_id = user.get_id()
            sqla_table.schema = csv_table.schema
            sqla_table.fetch_metadata()
            db.session.add(sqla_table)
        db.session.commit()
    except Exception as ex:  # pylint: disable=broad-except
        db.session.rollback()
        raise ex


def get_explore_database(database):
    """
    Returns the database that should be used for exploration. e.g. If
    Hive was used to upload a CSV, Presto will be a better option to
    explore its tables.
    """
    from superset import db
    from superset.models.core import Database

    explore_database_id = database.explore_database_id
    if explore_database_id:
        return (
            db.session.query(Database)
            .filter_by(id=explore_database_id)
            .one_or_none()
            or database
        )
    else:
        return database


def update_dataset(change: DataSetChange):
    from superset import db
    from superset.connectors.sqla.models import SqlaTable

    database = get_hq_database()
    # explore_database = get_explore_database(database)  # TODO: Necessary?
    sqla_table = (
        db.session.query(SqlaTable)
        .filter_by(
            table_name=change.data_source_id,
            # database_id=explore_database.id,
        )
        .one_or_none()
    )
    if sqla_table is None:
        raise ValueError(f'{change.data_source_id} table not found.')

    if change.action == 'delete':
        stmt = (
            sqla_table
            .delete()
            .where(sqla_table.doc_id == change.data['doc_id'])
        )
    elif change.action == 'upsert':
        stmt = (
            sqla_table
            .insert()
            .values(change.data)  # TODO: Do we need to cast anything?
            .on_conflict_do_update(
                index_elements=['doc_id'],
                set_=change.data,
            )
        )
    else:
        raise ValueError(f'Invalid DataSetChange action {change.action!r}')
    try:
        db.session.execute(stmt)
        db.session.commit()
    except Exception:  # pylint: disable=broad-except
        db.session.rollback()
        raise
