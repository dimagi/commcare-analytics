import os
import superset
import time

from superset.extensions import celery_app

from hq_superset.exceptions import TableMissing
from hq_superset.models import DataSetChange
from hq_superset.services import AsyncImportHelper, refresh_hq_datasource


@celery_app.task(name='refresh_hq_datasource_task')
def refresh_hq_datasource_task(domain, datasource_id, display_name, export_path, datasource_defn, user_id):
    try:
        refresh_hq_datasource(domain, datasource_id, display_name, export_path, datasource_defn, user_id)
    except Exception:
        AsyncImportHelper(domain, datasource_id).mark_as_complete()
        raise
    finally:
        if os.path.exists(export_path):
            os.remove(export_path)


@celery_app.task(name='process_dataset_change', ignore_result=True, store_errors_even_if_ignored=True)
def process_dataset_change(request_json):
    change = DataSetChange(**request_json)
    try:
        change.update_dataset()
    except TableMissing:
        pass


@celery_app.task(name='delete_redundant_shared_files')
def delete_redundant_shared_files():
    """
    Delete shared temporary files older than REMOVE_SHARED_FILES_AFTER days
    """
    directory = superset.config.SHARED_DIR

    now = time.time()
    redundant_timestamp = now - (superset.config.REMOVE_SHARED_FILES_AFTER * 86400)

    for file_name in os.listdir(directory):
        file_path = os.path.join(directory, file_name)
        if os.stat(file_path).st_mtime < redundant_timestamp:
            if os.path.isfile(file_path):
                os.remove(file_path)
