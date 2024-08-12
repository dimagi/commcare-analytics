import json
import os
import pickle
from io import StringIO
from unittest.mock import patch

import jwt
from flask import redirect, session
from sqlalchemy.sql import text

from hq_superset.utils import (
    SESSION_USER_DOMAINS_KEY,
    get_role_name_for_domain,
    get_schema_name_for_domain,
    refresh_hq_datasource,
)

from .base_test import HQDBTestCase
from .utils import TEST_DATASOURCE


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    @property
    def content(self):
        return pickle.dumps(self.json_data)


class UserMock:
    user_id = '123'

    def get_id(self):
        return self.user_id


class OAuthMock:
    def __init__(self):
        self.user_json = {
            'username': 'testuser1',
            'first_name': 'user',
            'last_name': '1',
            'email': 'test@example.com',
        }
        self.domain_json = {
            'objects': [
                {'domain_name': 'test1', 'project_name': 'test1'},
                {'domain_name': 'test2', 'project_name': 'test 1'},
            ]
        }
        self.test1_datasources = {
            'objects': [
                {
                    'id': 'test1_ucr1',
                    'display_name': 'Test1 UCR1',
                },
                {
                    'id': 'test1_ucr2',
                    'display_name': 'Test1 UCR2',
                },
            ]
        }
        self.test2_datasources = {
            'objects': [
                {
                    'id': 'test2_ucr1',
                    'display_name': 'Test2 UCR1',
                }
            ]
        }
        self.api_base_url = 'https://cchq.org/'

    def authorize_access_token(self):
        return {'access_token': 'some-key'}

    def get(self, url, token):
        return {
            'api/v0.5/identity/': MockResponse(self.user_json, 200),
            'api/v0.5/user_domains?feature_flag=superset-analytics&can_view_reports=true': MockResponse(
                self.domain_json, 200
            ),
            'a/test1/api/v0.5/ucr_data_source/': MockResponse(
                self.test1_datasources, 200
            ),
            'a/test2/api/v0.5/ucr_data_source/': MockResponse(
                self.test2_datasources, 200
            ),
            'a/test1/api/v0.5/ucr_data_source/test1_ucr1/': MockResponse(
                TEST_DATASOURCE, 200
            ),
            'a/test1/configurable_reports/data_sources/export/test1_ucr1/?format=csv': MockResponse(
                TEST_UCR_CSV_V1, 200
            ),
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
        self.app.appbuilder.sm.oauth_remotes = {'commcare': self.oauth_mock}

        gamma_role = self.app.appbuilder.sm.find_role('Gamma')
        self.user = self.app.appbuilder.sm.find_user(
            self.oauth_mock.user_json['username']
        )
        if not self.user:
            self.user = self.app.appbuilder.sm.add_user(
                **self.oauth_mock.user_json, role=[gamma_role]
            )

    def login(self, client):
        # bypass oauth-workflow by skipping login and oauth flow
        with client.session_transaction() as session_:
            session_['oauth_state'] = 'mock_state'
        state = jwt.encode({}, 'mock_state', algorithm='HS256')
        return client.get(
            f'/oauth-authorized/commcare?state={state}', follow_redirects=True
        )

    @staticmethod
    def logout(client):
        return client.get('/logout/')

    def test_unauthenticated_users_redirects_to_login(self):
        client = self.app.test_client()
        response = client.get('/', follow_redirects=True)
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.request.path, '/login/')

    def _assert_hq_domain_cookie(self, client, response, domain):
        response = client.get('/', follow_redirects=True)
        if domain:
            self.assertEqual(response.request.cookies['hq_domain'], domain)
        else:
            self.assertTrue('hq_domain' not in response.request.cookies)

    def _assert_pg_schema_exists(self, domain, exists):
        with self.hq_db.get_sqla_engine_with_context() as engine:
            self.assertEqual(
                engine.dialect.has_schema(
                    engine, get_schema_name_for_domain(domain)
                ),
                exists,
            )

    def test_redirects_to_domain_select_after_login(self):
        with self.app.test_client() as client:
            assert SESSION_USER_DOMAINS_KEY not in session
            self.login(client)
            response = client.get('/', follow_redirects=True)
            self.assertEqual(response.status, '200 OK')
            self.assertTrue('/domain/list' in response.request.path)
            self.assertEqual(
                session[SESSION_USER_DOMAINS_KEY],
                self.oauth_mock.domain_json['objects'],
            )
            self.logout(client)

    def test_domain_select_works(self):
        client = self.app.test_client()
        self.login(client)

        self._assert_pg_schema_exists('test1', False)
        response = client.get('/domain/select/test1/', follow_redirects=True)
        self.assertEqual(response.status, '200 OK')
        self.assertTrue('/superset/welcome/' in response.request.path)
        self._assert_hq_domain_cookie(client, response, 'test1')
        self._assert_pg_schema_exists('test1', True)

        # Check that hq_domain cookie gets updated after domain switch
        response = client.get('/domain/select/test2/', follow_redirects=True)
        self.assertEqual(response.status, '200 OK')
        self._assert_hq_domain_cookie(client, response, 'test2')

        # Check that hq_domain cookie gets unset after logout
        response = self.logout(client)

        self._assert_hq_domain_cookie(client, response, None)

    def test_non_user_domain_cant_be_selected(self):
        client = self.app.test_client()
        self.login(client)
        response = client.get(
            '/domain/select/wrong_domain/', follow_redirects=True
        )
        self.assertEqual(response.status, '200 OK')
        self.assertTrue('/domain/list' in response.request.path)
        self.logout(client)

    @patch('hq_superset.oauth.get_valid_cchq_oauth_token', return_value={})
    def test_datasource_list(self, *args):
        def _do_assert(datasources):
            self.assert_template_used('hq_datasource_list.html')
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
        with patch(
            'hq_superset.views.trigger_datasource_refresh'
        ) as refresh_mock:
            refresh_mock.return_value = redirect('/tablemodelview/list/')
            client.get(
                f'/hq_datasource/update/{ucr_id}?name=ds1',
                follow_redirects=True,
            )
            refresh_mock.assert_called_once_with('test1', ucr_id, 'ds1')

    @patch('hq_superset.oauth.get_valid_cchq_oauth_token', return_value={})
    @patch('hq_superset.views.os.remove')
    def test_trigger_datasource_refresh(self, *args):
        from hq_superset.views import (
            ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES,
            trigger_datasource_refresh,
        )

        domain = 'test1'
        ds_name = 'ds_name'
        file_path = '/file_path'
        ucr_id = self.oauth_mock.test1_datasources['objects'][0]['id']

        def _test_sync_or_async(ds_size, routing_method, user_id):
            with patch(
                'hq_superset.views.download_datasource'
            ) as download_ds_mock, patch(
                'hq_superset.views.get_datasource_defn'
            ) as ds_defn_mock, patch(routing_method) as refresh_mock, patch(
                'hq_superset.views.g'
            ) as mock_g:
                mock_g.user = UserMock()
                download_ds_mock.return_value = file_path, ds_size
                ds_defn_mock.return_value = TEST_DATASOURCE
                trigger_datasource_refresh(domain, ucr_id, ds_name)
                refresh_mock.assert_called_once_with(
                    domain,
                    ucr_id,
                    ds_name,
                    file_path,
                    TEST_DATASOURCE,
                    user_id,
                )

        # When datasource size is more than the limit, it should get
        #   queued via celery
        _test_sync_or_async(
            ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES + 1,
            'hq_superset.views.queue_refresh_task',
            UserMock().user_id,
        )
        # When datasource size is within the limit, it should get
        #   refreshed directly
        _test_sync_or_async(
            ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES - 1,
            'hq_superset.views.refresh_hq_datasource',
            None,
        )

    @patch('hq_superset.oauth.get_valid_cchq_oauth_token', return_value={})
    @patch('hq_superset.tasks.subscribe_to_hq_datasource_task.delay')
    @patch('hq_superset.hq_requests.HQRequest.get')
    def test_download_datasource(
        self, hq_request_get_mock, subscribe_task_mock, *args
    ):
        from hq_superset.views import download_datasource

        hq_request_get_mock.return_value = MockResponse(
            json_data=TEST_UCR_CSV_V1,
            status_code=200,
        )
        ucr_id = self.oauth_mock.test1_datasources['objects'][0]['id']
        path, size = download_datasource('test1', ucr_id)

        subscribe_task_mock.assert_called_once_with(
            'test1',
            ucr_id,
        )
        with open(path, 'rb') as f:
            self.assertEqual(pickle.load(f), TEST_UCR_CSV_V1)
            self.assertEqual(size, len(pickle.dumps(TEST_UCR_CSV_V1)))
        os.remove(path)

    @patch('hq_superset.oauth.get_valid_cchq_oauth_token', return_value={})
    def test_refresh_hq_datasource(self, *args):
        ucr_id = self.oauth_mock.test1_datasources['objects'][0]['id']
        ds_name = 'ds1'
        with patch(
            'hq_superset.utils.get_datasource_file'
        ) as csv_mock, self.app.test_client() as client:
            self.login(client)
            client.get('/domain/select/test1/', follow_redirects=True)

            def _test_upload(test_data, expected_output):
                csv_mock.return_value = StringIO(test_data)
                refresh_hq_datasource(
                    'test1', ucr_id, ds_name, '_', TEST_DATASOURCE
                )
                datasets = json.loads(client.get('/api/v1/dataset/').data)
                self.assertEqual(len(datasets['result']), 1)
                self.assertEqual(
                    datasets['result'][0]['schema'],
                    get_schema_name_for_domain('test1'),
                )
                self.assertEqual(datasets['result'][0]['table_name'], ucr_id)
                self.assertEqual(datasets['result'][0]['description'], ds_name)
                with self.hq_db.get_sqla_engine_with_context() as engine:
                    with engine.connect() as connection:
                        result = connection.execute(
                            text(
                                'SELECT doc_id FROM hqdomain_test1.test1_ucr1'
                            )
                        ).fetchall()
                        self.assertEqual(result, expected_output)
                # Check that updated dataset is reflected in the list view
                client.get('/hq_datasource/list/', follow_redirects=True)
                self.assert_context('ucr_id_to_pks', {'test1_ucr1': 1})
                # Check that switching to other domains doesn't display the datasets
                client.get('/domain/select/test2/', follow_redirects=True)
                client.get('/hq_datasource/list/', follow_redirects=True)
                self.assert_context('ucr_id_to_pks', {})
                client.get('/domain/select/test1/', follow_redirects=True)

            # Test Create
            _test_upload(TEST_UCR_CSV_V1, [('a1',), ('a2',)])
            # Test Update
            _test_upload(TEST_UCR_CSV_V2, [('a1',), ('a2',), ('a3',)])
            # Test Delete
            datasets = json.loads(client.get('/api/v1/dataset/').data)
            _id = datasets['result'][0]['id']
            response = client.get(f'/hq_datasource/delete/{_id}')
            self.assertEqual(response.status, '302 FOUND')
            client.get('/hq_datasource/list/', follow_redirects=True)
            self.assert_context('ucr_id_to_pks', {})

    # def test_dataset_update(self):
    #     # The equivalent of something like:
    #     #
    #     # $ curl -X POST \
    #     #     -H "Content-Type: application/json" \
    #     #     -d '{"action": "upsert", "data_source_id": "abc123", "data": {"doc_id": "abc123"}}' \
    #     #     http://localhost:8088/hq_webhook/change/
    #
    #     ucr_id = self.oauth_mock.test1_datasources['objects'][0]['id']
    #     ds_name = "ds1"
    #     with patch("hq_superset.views.get_datasource_file") as csv_mock, \
    #             self.app.test_client() as client:
    #
    #         self.login(client)
    #
    # def test_dataset_insert(self):
    #     pass
    #
    # def test_dataset_delete(self):
    #     pass

    def test_domain_gets_expected_permissions(self):
        sm = self.app.appbuilder.sm
        domain_name = 'test2'
        expected_permissions_map = {
            'schema_access': f'[HQ Data].[hqdomain_{domain_name}]',
            'can_save': 'Datasource',
        }

        with self.app.test_client() as client:
            self.login(client)
            client.get(f'/domain/select/{domain_name}/', follow_redirects=True)

            domain_role = get_role_name_for_domain(domain_name)
            role = sm.find_role(domain_role)
            permissions = list(sm.get_role_permissions(role))

            expected_permissions_not_present = list(
                expected_permissions_map.keys()
            )
            for permission, target in permissions:
                expected_permissions_not_present.remove(permission)
                assert target == expected_permissions_map[permission]

            assert (
                expected_permissions_not_present == []
            ), 'Not all expected permissions were granted'
