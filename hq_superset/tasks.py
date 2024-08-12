import logging
import os

from superset.extensions import celery_app

from .utils import AsyncImportHelper, refresh_hq_datasource

logger = logging.getLogger(__name__)


@celery_app.task(name='refresh_hq_datasource_task')
def refresh_hq_datasource_task(
    domain, datasource_id, display_name, export_path, datasource_defn, user_id
):
    try:
        refresh_hq_datasource(
            domain,
            datasource_id,
            display_name,
            export_path,
            datasource_defn,
            user_id,
        )
    except Exception:
        AsyncImportHelper(domain, datasource_id).mark_as_complete()
        raise
    os.remove(export_path)


@celery_app.task(name='subscribe_to_hq_datasource_task')
def subscribe_to_hq_datasource_task(domain, datasource_id):
    from superset.config import BASE_URL

    from hq_superset.hq_requests import HQRequest, HqUrl
    from hq_superset.models import HQClient

    if HQClient.get_by_domain(domain) is None:
        hq_request = HQRequest(
            url=HqUrl.subscribe_to_datasource_url(domain, datasource_id)
        )

        client_id, client_secret = HQClient.create_domain_client(domain)

        response = hq_request.post(
            {
                'webhook_url': f'{BASE_URL}/hq_webhook/change/',
                'token_url': f'{BASE_URL}/oauth/token',
                'client_id': client_id,
                'client_secret': client_secret,
            }
        )
        if response.status_code == 201:
            return
        if response.status_code < 500:
            logger.error(
                f'Failed to subscribe to data source {datasource_id} due to the following issue: {response.data}'
            )
        if response.status_code >= 500:
            logger.exception(
                f'Failed to subscribe to data source {datasource_id} due to a remote server error'
            )
