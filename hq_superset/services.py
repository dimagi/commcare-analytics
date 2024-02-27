import os
from datetime import datetime

import pandas
import sqlalchemy
import superset
from flask import g
from sqlalchemy.dialects import postgresql
from superset import db
from superset.connectors.sqla.models import SqlaTable
from superset.extensions import cache_manager
from superset.sql_parse import Table

from .utils import (
    CCHQApiException,
    convert_to_array,
    get_column_dtypes,
    get_datasource_details_url,
    get_datasource_export_url,
    get_datasource_file,
    get_hq_database,
    get_schema_name_for_domain,
    parse_date,
)


def download_datasource(provider, oauth_token, domain, datasource_id):
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

        sqla_table = (
            db.session.query(SqlaTable)
            .filter_by(
                table_name=datasource_id,
                schema=csv_table.schema,
                database_id=database.id,
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
            sqla_table.database = database
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
