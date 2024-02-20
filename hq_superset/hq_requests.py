import superset
from hq_superset.oauth import get_valid_cchq_oauth_token


class HQRequest:

    def __init__(self, url):
        self.url = url

    @property
    def oauth_token(self):
        return get_valid_cchq_oauth_token()

    @property
    def commcare_provider(self):
        return superset.appbuilder.sm.oauth_remotes["commcare"]

    @property
    def api_base_url(self):
        return self.commcare_provider.api_base_url

    @property
    def absolute_url(self):
        return f"{self.api_base_url}{self.url}"

    def get(self):
        return self.commcare_provider.get(self.url, token=self.oauth_token)

    def post(self, data):
        return self.commcare_provider.post(self.url, data=data, token=self.oauth_token)
