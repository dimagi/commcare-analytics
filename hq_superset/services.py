import logging
import os
import uuid
from datetime import datetime

import pandas
import sqlalchemy
import superset
from flask import g, current_app, request
from sqlalchemy.dialects import postgresql
from superset import db
from superset.connectors.sqla.models import SqlaTable
from superset.extensions import cache_manager
from superset.sql_parse import Table

from .exceptions import HQAPIException
from .hq_requests import HQRequest
from .hq_url import datasource_details, datasource_export, datasource_subscribe
from .models import OAuth2Client
from .utils import (
    convert_to_array,
    get_column_dtypes,
    get_datasource_file,
    get_hq_database,
    get_schema_name_for_domain,
    generate_secret,
    parse_date,
)

logger = logging.getLogger(__name__)


def download_and_subscribe_to_datasource(domain, datasource_id):
    hq_request = HQRequest(url=datasource_export(domain, datasource_id))
    response = hq_request.get()

    if response.status_code != 200:
        raise HQAPIException("Error downloading the UCR export from HQ")

    filename = f"{datasource_id}_{datetime.now()}.zip"
    path = os.path.join(superset.config.SHARED_DIR, filename)
    with open(path, "wb") as f:
        f.write(response.content)

    subscribe_to_hq_datasource(domain, datasource_id)

    return path, len(response.content)


def get_datasource_defn(domain, datasource_id):
    hq_request = HQRequest(url=datasource_details(domain, datasource_id))
    response = hq_request.get()
    if response.status_code != 200:
        raise HQAPIException(
            "Error downloading the UCR definition from HQ: "
            f"HTTP status {response.status_code}: {response.content}"
        )
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

    def dataframe_to_sql(df, replace=False):
        """
        Upload Pandas DataFrame ``df`` to ``database``.
        """
        database.db_engine_spec.df_to_sql(
            database,
            csv_table,
            df,
            to_sql_kwargs={
                "if_exists": "replace" if replace else "append",
                "dtype": sql_converters,
                "index": False,
            },
        )

    database = get_hq_database()
    schema = get_schema_name_for_domain(domain)
    csv_table = Table(table=datasource_id, schema=schema)
    column_dtypes, date_columns, array_columns = get_column_dtypes(
        datasource_defn
    )
    converters = {
        column_name: convert_to_array for column_name in array_columns
    }
    sql_converters = {
        # Assumes all array values will be of type TEXT
        column_name: postgresql.ARRAY(sqlalchemy.types.TEXT)
        for column_name in array_columns
    }

    try:
        with get_datasource_file(file_path) as csv_file:
            dataframes = pandas.read_csv(
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
            dataframe_to_sql(next(dataframes), replace=True)
            for df in dataframes:
                dataframe_to_sql(df, replace=False)

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


def subscribe_to_hq_datasource(domain, datasource_id):
    client = _get_or_create_oauth2client(domain)
    hq_request = HQRequest(url=datasource_subscribe(domain, datasource_id))
    scheme = _get_url_scheme()
    webhook_url = current_app.url_for(
        'DataSetChangeAPI.post_dataset_change',
        _external=True,
        _scheme=scheme,
    )
    token_url = current_app.url_for(
        'OAuth.issue_access_token',
        _external=True,
        _scheme=scheme,
    )
    response = hq_request.post({
        'webhook_url': webhook_url,
        'token_url': token_url,
        'client_id': client.client_id,
        'client_secret': client.get_client_secret(),
    })
    if response.status_code == 201:
        return
    if response.status_code < 500:
        logger.error(
            f"Failed to subscribe to data source {datasource_id} due to the following issue: {response.data}"
        )
    if response.status_code >= 500:
        logger.exception(
            f"Failed to subscribe to data source {datasource_id} due to a remote server error"
        )


def _get_url_scheme():
    scheme = 'https'
    # Allow "http" for localhost only. Use request.server because
    # request.scheme can return "http" for HTTPS requests (because proxy?)
    if request.server:
        host, port = request.server
        if host == '127.0.0.1':  # Also True if hostname is "localhost"
            scheme = 'http'
    return scheme


def _get_or_create_oauth2client(domain):
    client = db.session.query(OAuth2Client).filter_by(domain=domain).first()
    if client:
        return client

    client = OAuth2Client(
        domain=domain,
        client_id=str(uuid.uuid4()),
    )
    client.set_client_secret(generate_secret())
    client.set_client_metadata({"grant_types": ["client_credentials"]})
    db.session.add(client)
    db.session.commit()
    return client


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
