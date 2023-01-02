from hq_superset.utils import SESSION_USER_DOMAINS_KEY

import json
import jwt
import logging
import os
from typing import List

from flask import Flask, session
from flask_appbuilder import AppBuilder
from flask_appbuilder import SQLA
from flask_appbuilder.security.sqla.models import Permission, Role, User, ViewMenu
from flask_appbuilder.tests.base import FABTestCase
from flask_appbuilder.tests.const import PASSWORD_ADMIN, USERNAME_ADMIN
import prison
from werkzeug.security import generate_password_hash


log = logging.getLogger(__name__)

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

class UserAPITestCase(FABTestCase):
    def setUp(self) -> None:
        self.app = Flask('__name__')
        self.basedir = os.path.abspath(os.path.dirname(__file__))
        self.app.config.from_object("hq_superset.tests.config_for_tests.superset_config")
        self.db = SQLA(self.app)

        self.session = self.db.session
        self.appbuilder = AppBuilder(self.app, self.session)

        self.oauth_mock = OAuthMock()
        self.oauth_mock = OAuthMock()
        appbuilder = self.appbuilder
        appbuilder.sm.oauth_remotes = {"commcare": self.oauth_mock}

        gamma_role = self.appbuilder.sm.find_role('Gamma')
        self.appbuilder.sm.add_user(**self.oauth_mock.user_json, role=[gamma_role])

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
        self.assertEqual(
            response.request.path,
            '/login/'
        )

    def test_redirects_to_domain_select_after_login(self):
        client = self.app.test_client()
        with self.app.app_context():
            assert SESSION_USER_DOMAINS_KEY not in session
            self.login(client)
            response = client.get('/', follow_redirects=True)
            self.assertTrue('/domain/list' in response.request.path)
            self.assertEqual(
                session[SESSION_USER_DOMAINS_KEY],
                self.oauth_mock.domain_json["objects"]
            )
            self.logout(client)

    def test_domain_select_works(self):
        client = self.app.test_client()
        self.login(client)
        response = client.get('/domain/select/test1', follow_redirects=True)
        self.assertTrue('/superset/welcome/' in response.request.path)
        self.logout(client)

    def tearDown(self):
        self.appbuilder.session.close()
        engine = self.appbuilder.session.get_bind(mapper=None, clause=None)
        for baseview in self.appbuilder.baseviews:
            if hasattr(baseview, "datamodel"):
                baseview.datamodel.session = None
        engine.dispose()
