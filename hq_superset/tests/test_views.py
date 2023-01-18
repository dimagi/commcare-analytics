import datetime
import json
import jwt

from io import StringIO
from unittest.mock import patch, MagicMock
from flask import session, redirect
from sqlalchemy.sql import text
from superset.connectors.sqla.models import SqlaTable

from hq_superset.oauth import OAuthSessionExpired, get_valid_cchq_oauth_token
from hq_superset.utils import (SESSION_USER_DOMAINS_KEY, 
    SESSION_OAUTH_RESPONSE_KEY, get_schema_name_for_domain)
from .base_test import SupersetTestCase, HQDBTestCase
from .utils import TEST_DATASOURCE


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

    def authorize_access_token(self):
        return {"access_token": "some-key"}

    def get(self, url, token):
        return {
            'api/v0.5/identity/': MockResponse(self.user_json, 200),
            'api/v0.5/user_domains?feature_flag=superset-analytics&can_view_reports=true': MockResponse(self.domain_json, 200),
            'a/test1/api/v0.5/ucr_data_source/': MockResponse(self.test1_datasources, 200),
            'a/test2/api/v0.5/ucr_data_source/': MockResponse(self.test2_datasources, 200),
            'a/test1/api/v0.5/ucr_data_source/test1_ucr1/': MockResponse(TEST_DATASOURCE, 200),
        }[url]


TEST_UCR_CSV_V1 = """\
doc_id,inserted_at,data_visit_date_eaece89e,data_visit_number_33d63739,data_lmp_date_5e24b993,data_visit_comment_fb984fda
a1, 2021-12-20, 2022-01-19, 100, 2022-02-20, some_text
a2, 2021-12-22, 2022-02-19, 10, 2022-03-20, some_other_text
"""

TEST_UCR_CSV_V2 = """\
doc_id,inserted_at,data_visit_date_eaece89e,data_visit_number_33d63739,data_lmp_date_5e24b993,data_visit_comment_fb984fda
a1, 2021-12-20, 2022-01-19, 100, 2022-02-20, some_text
a2, 2021-12-22, 2022-02-19, 10, 2022-03-20, some_other_text
a3, 2021-11-22, 2022-01-19, 10, 2022-03-20, some_other_text2
"""

class TestViews(HQDBTestCase):

    def setUp(self):
        super(TestViews, self).setUp()
        self.app.appbuilder.add_permissions(update_perms=True)
        self.app.appbuilder.sm.sync_role_definitions()

        self.oauth_mock = OAuthMock()
        self.app.appbuilder.sm.oauth_remotes = {"commcare": self.oauth_mock}

        gamma_role = self.app.appbuilder.sm.find_role('Gamma')
        self.app.appbuilder.sm.add_user(**self.oauth_mock.user_json, role=[gamma_role])

    def login(self, client):
        # bypass oauth-workflow by skipping login and oauth flow
        with client.session_transaction() as session_:
            session_["oauth_state"] = "mock_state"
        state = jwt.encode({}, "mock_state", algorithm="HS256")
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

    def _assert_hq_domain_cookie(self, client, response, domain):
        response = client.get('/', follow_redirects=True)
        if domain:
            self.assertEqual(response.request.cookies['hq_domain'], domain)
        else:
            self.assertTrue('hq_domain' not in response.request.cookies)

    def _assert_pg_schema_exists(self, domain, exists):
        engine = self.hq_db.get_sqla_engine()
        self.assertEqual(
            engine.dialect.has_schema(engine, get_schema_name_for_domain(domain)),
            exists
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

        self._assert_pg_schema_exists('test1', False)
        response = client.get('/domain/select/test1/', follow_redirects=True)
        self.assertEqual(response.status, "200 OK")
        self.assertTrue('/superset/welcome/' in response.request.path)
        self._assert_hq_domain_cookie(client, response, 'test1')
        self._assert_pg_schema_exists('test1', True)

        # Check that hq_domain cookie gets updated after domain switch
        response = client.get('/domain/select/test2/', follow_redirects=True)
        self.assertEqual(response.status, "200 OK")
        self._assert_hq_domain_cookie(client, response, 'test2')

        # Check that hq_domain cookie gets unset after logout
        response = self.logout(client)

        self._assert_hq_domain_cookie(client, response, None)

    def test_non_user_domain_cant_be_selected(self):
        client = self.app.test_client()
        self.login(client)
        response = client.get('/domain/select/wrong_domain/', follow_redirects=True)
        self.assertEqual(response.status, "200 OK")
        self.assertTrue('/domain/list' in response.request.path)
        self.logout(client)

    @patch('hq_superset.views.get_valid_cchq_oauth_token', return_value={})
    def test_datasource_list(self, *args):
        def _do_assert(datasources):
            self.assert_template_used("hq_datasource_list.html")
            self.assert_context('hq_datasources', datasources)
            self.assert_context('ucr_id_to_pks', {})
            self.assert_context('hq_base_url', self.oauth_mock.api_base_url)

        client = self.app.test_client()
        self.login(client)
        client.get('/domain/select/test1/', follow_redirects=True)
        client.get('/hq_datasource/list/', follow_redirects=True)
        _do_assert(self.oauth_mock.test1_datasources)
        # Switching domain should get other domains datasources
        client.get('/domain/select/test2/', follow_redirects=True)
        client.get('/hq_datasource/list/', follow_redirects=True)
        _do_assert(self.oauth_mock.test2_datasources)

    def test_datasource_upload(self, *args):
        client = self.app.test_client()
        self.login(client)
        client.get('/domain/select/test1/', follow_redirects=True)
        ucr_id = self.oauth_mock.test1_datasources['objects'][0]['id']
        with patch("hq_superset.views.refresh_hq_datasource") as refresh_mock:
            refresh_mock.return_value = redirect("/tablemodelview/list/")
            client.get(f'/hq_datasource/update/{ucr_id}?name=ds1', follow_redirects=True)
            refresh_mock.assert_called_once_with(
                'test1',
                ucr_id,
                'ds1'
            )

    @patch('hq_superset.views.get_valid_cchq_oauth_token', return_value={})
    def test_refresh_hq_datasource(self, *args):

        from hq_superset.views import refresh_hq_datasource
        client = self.app.test_client()
        
        ucr_id = self.oauth_mock.test1_datasources['objects'][0]['id']
        ds_name = "ds1"
        with patch("hq_superset.views.get_csv_file") as csv_mock, \
            self.app.test_client() as client:
            self.login(client)
            client.get('/domain/select/test1/', follow_redirects=True)
            
            def _test_upload(test_data, expected_output):
                csv_mock.return_value = StringIO(test_data)
                refresh_hq_datasource('test1', ucr_id, ds_name)
                datasets = json.loads(client.get('/api/v1/dataset/').data)
                self.assertEqual(len(datasets['result']), 1)
                self.assertEqual(datasets['result'][0]['schema'], get_schema_name_for_domain('test1'))
                self.assertEqual(datasets['result'][0]['table_name'], ucr_id)
                self.assertEqual(datasets['result'][0]['description'], ds_name)
                engine = self.hq_db.get_sqla_engine()
                with engine.connect() as connection:
                    result = connection.execute(text(
                        'SELECT doc_id FROM hqdomain_test1.test1_ucr1'
                    )).fetchall()
                    self.assertEqual(
                        result,
                        expected_output
                    )
                # Check that updated dataset is reflected in the list view
                client.get('/hq_datasource/list/', follow_redirects=True)
                self.assert_context('ucr_id_to_pks', {'test1_ucr1': 1})
                # Check that switching to other domains doesn't display the datasets
                client.get('/domain/select/test2/', follow_redirects=True)
                client.get('/hq_datasource/list/', follow_redirects=True)
                self.assert_context('ucr_id_to_pks', {})
                client.get('/domain/select/test1/', follow_redirects=True)

            # Test Create
            _test_upload(TEST_UCR_CSV_V1, [('a1', ), ('a2', )])
            # Test Update
            _test_upload(TEST_UCR_CSV_V2, [('a1', ), ('a2', ), ('a3', )])
            # Test Delete
            datasets = json.loads(client.get('/api/v1/dataset/').data)
            _id = datasets['result'][0]['id']
            response = client.get(f'/hq_datasource/delete/{_id}')
            self.assertEqual(response.status, "302 FOUND")
            client.get('/hq_datasource/list/', follow_redirects=True)
            self.assert_context('ucr_id_to_pks', {})
