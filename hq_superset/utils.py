from datetime import date, datetime
from superset.extensions import cache_manager

import pandas
import sqlalchemy


def get_datasource_export_url(domain, datasource_id):
    return f"a/{domain}/configurable_reports/data_sources/export/{datasource_id}/?format=csv"


def get_datasource_list_url(domain):
    return f"a/{domain}/api/v0.5/ucr_data_source/"


def get_datasource_details_url(domain, datasource_id):
    return f"a/{domain}/api/v0.5/ucr_data_source/{datasource_id}/"


def get_ucr_database():
    # Todo; cache to avoid multiple lookups in single request
    from superset import db
    from superset.models.core import Database

    # Todo; get actual DB once that's implemented
    return db.session.query(Database).filter_by(database_name="HQ Data").one()


def create_schema_if_not_exists(domain):
    # Create a schema in the database where HQ's UCR data is stored
    schema_name = get_schema_name_for_domain(domain)
    database = get_ucr_database()
    engine = database.get_sqla_engine()
    if not engine.dialect.has_schema(engine, schema_name):
        engine.execute(sqlalchemy.schema.CreateSchema(schema_name))


DOMAIN_PREFIX = "hqdomain_"
SESSION_USER_DOMAINS_KEY = "user_hq_domains"
SESSION_OAUTH_RESPONSE_KEY = "oauth_response"


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
        res = AsyncResult(task_id)
        return not res.ready()

    def mark_as_in_progress(self, task_id):
        cache_manager.cache.set(self.progress_key, task_id)

    def mark_as_complete(self):
        cache_manager.cache.delete(self.progress_key, self.task_id)
