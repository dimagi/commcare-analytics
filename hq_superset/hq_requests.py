import superset

from hq_superset.oauth import get_valid_cchq_oauth_token


class HqUrl:
    @classmethod
    def datasource_export_url(cls, domain, datasource_id):
        return f'a/{domain}/configurable_reports/data_sources/export/{datasource_id}/?format=csv'

    @classmethod
    def datasource_list_url(cls, domain):
        return f'a/{domain}/api/v0.5/ucr_data_source/'

    @classmethod
    def datasource_details_url(cls, domain, datasource_id):
        return f'a/{domain}/api/v0.5/ucr_data_source/{datasource_id}/'

    @classmethod
    def subscribe_to_datasource_url(cls, domain, datasource_id):
        return f'a/{domain}/configurable_reports/data_sources/subscribe/{datasource_id}/'


class HQRequest:
    def __init__(self, url):
        self.url = url

    @property
    def oauth_token(self):
        return get_valid_cchq_oauth_token()

    @property
    def commcare_provider(self):
        return superset.appbuilder.sm.oauth_remotes['commcare']

    @property
    def api_base_url(self):
        return self.commcare_provider.api_base_url

    @property
    def absolute_url(self):
        return f'{self.api_base_url}{self.url}'

    def get(self):
        return self.commcare_provider.get(self.url, token=self.oauth_token)

    def post(self, data):
        return self.commcare_provider.post(
            self.url, data=data, token=self.oauth_token
        )
