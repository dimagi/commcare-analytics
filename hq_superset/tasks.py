import os

from superset.extensions import celery_app
from sqlalchemy import delete

from .exceptions import TableMissing
from .models import DataSetChange, OAuth2Token, db
from .services import AsyncImportHelper, refresh_hq_datasource


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


@celery_app.task(name='process_dataset_change')
def process_dataset_change(request_json):
    change = DataSetChange(**request_json)
    try:
        change.update_dataset()
    except TableMissing:
        pass


# ToDo: schedule this to run once every week/day
def delete_revoked_tokens():
    stmt = (
        delete(OAuth2Token)
        .where(OAuth2Token.access_token_revoked_at != 0)
    )
    db.session.execute(stmt)
    db.session.commit()
