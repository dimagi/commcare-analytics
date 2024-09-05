import requests
import json


def subscribe_data_sources(superset_base_url, hq_base_url, data_sources_file_path, username, apikey):
    from hq_superset.services import (
        _get_or_create_oauth2client,
        datasource_subscribe,
    )

    def data_sources_by_domain():
        with open(data_sources_file_path) as file:
            datasource_ids_by_domain = json.loads(file.read())

        # Validate file content
        assert isinstance(datasource_ids_by_domain, dict)
        for domain, ds_ids in datasource_ids_by_domain.items():
            if not isinstance(ds_ids, list):
                raise Exception(f"{domain} expected a list of data source IDs")
        return datasource_ids_by_domain

    webhook_url = f"{superset_base_url}/change/"
    token_url = f"{superset_base_url}/token"

    failed_data_source_ids = {}
    for domain, datasource_ids in data_sources_by_domain().items():
        for datasource_id in datasource_ids:
            client = _get_or_create_oauth2client(domain)

            endpoint = datasource_subscribe(domain, datasource_id)
            data = {
                'webhook_url': webhook_url,
                'token_url': token_url,
                'client_id': client.client_id,
                'client_secret': client.get_client_secret(),
            }
            response = requests.post(
                f"{hq_base_url}/{endpoint}",
                data=data,
                headers={
                    "Authorization": f"ApiKey {username}:{apikey}"
                }
            )

            if response.status_code != 201:
                failed_data_source_ids[datasource_id] = response.content

    print("Done!")
    if failed_data_source_ids:
        print("The following data sources failed to subscribe")
        print(failed_data_source_ids)
