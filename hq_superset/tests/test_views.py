import datetime
import jwt

from unittest.mock import patch, MagicMock
from flask import session

from hq_superset.oauth import OAuthSessionExpired, get_valid_cchq_oauth_token
from hq_superset.utils import (SESSION_USER_DOMAINS_KEY, 
    SESSION_OAUTH_RESPONSE_KEY)
from .base_test import SupersetTestCase
from .utils import setup_hq_db


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


class OAuthMock():

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

    def authorize_access_token(self):
        return {"access_token": "some-key"}

    def get(self, url, token):
        return {
            'api/v0.5/identity/': MockResponse(self.user_json, 200),
            'api/v0.5/user_domains?feature_flag=superset-analytics&can_view_reports=true': MockResponse(self.domain_json, 200)
        }[url]


class TestViews(SupersetTestCase):

    def setUp(self):
        super(TestViews, self).setUp()
        self.app.testing = True
        self.app.appbuilder.add_permissions(update_perms=True)
        self.app.appbuilder.sm.sync_role_definitions()

        self.oauth_mock = OAuthMock()
        self.oauth_mock = OAuthMock()
        appbuilder = self.app.appbuilder
        appbuilder.sm.oauth_remotes = {"commcare": self.oauth_mock}

        gamma_role = self.app.appbuilder.sm.find_role('Gamma')
        self.app.appbuilder.sm.add_user(**self.oauth_mock.user_json, role=[gamma_role])
        setup_hq_db()

    def login(self, client):
        # bypass oauth-workflow by skipping login and oauth flow
        state = jwt.encode({}, self.app.config["SECRET_KEY"], algorithm="HS256")
        return client.get(f"/oauth-authorized/commcare?state={state}", follow_redirects=True)

    @staticmethod
    def logout(client):
        return client.get("/logout/")

    def test_unauthenticated_users_redirects_to_login(self):
        client = self.app.test_client()
        response = client.get('/', follow_redirects=True)
        self.assertEqual(response.status, "200 OK")
        self.assertEqual(
            response.request.path,
            '/login/'
        )

    def test_redirects_to_domain_select_after_login(self):
        with self.app.test_client() as client:
            assert SESSION_USER_DOMAINS_KEY not in session
            self.login(client)
            response = client.get('/', follow_redirects=True)
            self.assertEqual(response.status, "200 OK")
            self.assertTrue('/domain/list' in response.request.path)
            self.assertEqual(
                session[SESSION_USER_DOMAINS_KEY],
                self.oauth_mock.domain_json["objects"]
            )
            self.logout(client)

    def test_domain_select_works(self):
        client = self.app.test_client()
        self.login(client)
        response = client.get('/domain/select/test1/', follow_redirects=True)
        self.assertTrue('/superset/welcome/' in response.request.path)
        self.logout(client)
