import pickle

from hq_superset.tests.const import TEST_DATASOURCE, TEST_UCR_CSV_V1


class OAuthMock(object):

    def __init__(self):
        self.user_json = {
            'username': 'testuser1',
            'first_name': 'user',
            'last_name': '1',
            'email': 'test@example.com',
        }
        self.domain_json = {
            "objects": [
                {
                    "domain_name":"test1",
                    "project_name":"test1"
                },
                {
                    "domain_name":"test2",
                    "project_name":"test 1"
                },
            ]
        }
        self.test1_datasources = {
            "objects": [
                {
                    "id": 'test1_ucr1',
                    "display_name": 'Test1 UCR1',
                },
                {
                    "id": 'test1_ucr2',
                    "display_name": 'Test1 UCR2',
                },
            ]
        }
        self.test2_datasources = {
            "objects": [
                {
                    "id": 'test2_ucr1',
                    "display_name": 'Test2 UCR1',
                }
            ]
        }
        self.api_base_url = "https://cchq.org/"
        self.user_domain_roles = {
            "permissions": {"can_view": True, "can_edit": True},
            "roles": ["Gamma", "sql_lab"],
        }

    def authorize_access_token(self):
        return {"access_token": "some-key"}

    def get(self, url, token):
        return {
            'api/v0.5/identity/': MockResponse(self.user_json, 200),
            'api/v0.5/user_domains?feature_flag=superset-analytics&can_view_reports=true': MockResponse(
                self.domain_json, 200
            ),
            'a/test1/api/v0.5/ucr_data_source/': MockResponse(self.test1_datasources, 200),
            'a/test2/api/v0.5/ucr_data_source/': MockResponse(self.test2_datasources, 200),
            'a/test1/api/v0.5/ucr_data_source/test1_ucr1/': MockResponse(TEST_DATASOURCE, 200),
            'a/test1/configurable_reports/data_sources/export/test1_ucr1/?format=csv': MockResponse(
                TEST_UCR_CSV_V1, 200
            ),
            'a/test1/api/v0.5/analytics-roles/': MockResponse(self.user_domain_roles, 200),
            'a/test2/api/v0.5/analytics-roles/': MockResponse(self.user_domain_roles, 200),
        }[url]


class UserMock(object):
    user_id = '123'

    def get_id(self):
        return self.user_id


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    @property
    def content(self):
        return pickle.dumps(self.json_data)

