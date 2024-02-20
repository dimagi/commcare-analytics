import os

from superset.extensions import celery_app

from .utils import AsyncImportHelper, refresh_hq_datasource


@celery_app.task(name='refresh_hq_datasource_task')
def refresh_hq_datasource_task(domain, datasource_id, display_name, export_path, datasource_defn, user_id):
    try:
        refresh_hq_datasource(domain, datasource_id, display_name, export_path, datasource_defn, user_id)
    except Exception:
        AsyncImportHelper(domain, datasource_id).mark_as_complete()
        raise
    os.remove(export_path)
