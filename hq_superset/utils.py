import os
from contextlib import contextmanager
from datetime import date, datetime
from zipfile import ZipFile

import pandas
import sqlalchemy
from flask_login import current_user
from superset.extensions import cache_manager

DOMAIN_PREFIX = "hqdomain_"
SESSION_USER_DOMAINS_KEY = "user_hq_domains"
SESSION_OAUTH_RESPONSE_KEY = "oauth_response"
HQ_DB_CONNECTION_NAME = "HQ Data"

ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES = 5_000_000  # ~5MB


class CCHQApiException(Exception):
    pass


def get_datasource_export_url(domain, datasource_id):
    return f"a/{domain}/configurable_reports/data_sources/export/{datasource_id}/?format=csv"


def get_datasource_list_url(domain):
    return f"a/{domain}/api/v0.5/ucr_data_source/"


def get_datasource_details_url(domain, datasource_id):
    return f"a/{domain}/api/v0.5/ucr_data_source/{datasource_id}/"


def get_hq_database():
    # Todo; cache to avoid multiple lookups in single request
    from superset import db
    from superset.models.core import Database

    # Todo; get actual DB once that's implemented
    return db.session.query(Database).filter_by(database_name=HQ_DB_CONNECTION_NAME).one()


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
        return cache_manager.cache.get(self.progress_key)

    def is_import_in_progress(self):
        if not self.task_id:
            return False
        from celery.result import AsyncResult
        res = AsyncResult(self.task_id)
        return not res.ready()

    def mark_as_in_progress(self, task_id):
        cache_manager.cache.set(self.progress_key, task_id)

    def mark_as_complete(self):
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


def download_datasource(provider, oauth_token, domain, datasource_id):
    import superset
    datasource_url = get_datasource_export_url(domain, datasource_id)
    response = provider.get(datasource_url, token=oauth_token)
    if response.status_code != 200:
        raise CCHQApiException("Error downloading the UCR export from HQ")

    filename = f"{datasource_id}_{datetime.now()}.zip"
    path = os.path.join(superset.config.SHARED_DIR, filename)
    with open(path, "wb") as f:
        f.write(response.content)

    return path, len(response.content)


def get_datasource_defn(provider, oauth_token, domain, datasource_id):
    url = get_datasource_details_url(domain, datasource_id)
    response = provider.get(url, token=oauth_token)
    if response.status_code != 200:
        raise CCHQApiException("Error downloading the UCR definition from HQ")
    return response.json()
