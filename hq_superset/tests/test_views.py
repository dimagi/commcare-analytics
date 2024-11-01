import json
import os
import pickle
from io import StringIO
from unittest.mock import patch

import jwt
from flask import redirect, session
from sqlalchemy.sql import text

from hq_superset.exceptions import HQAPIException
from hq_superset.tests.base_test import HQDBTestCase
from hq_superset.tests.const import (
    TEST_DATASOURCE,
    TEST_UCR_CSV_V1,
    TEST_UCR_CSV_V2,
)
from hq_superset.tests.utils import MockResponse, OAuthMock, UserMock
from hq_superset.utils import (
    SESSION_USER_DOMAINS_KEY,
    DomainSyncUtil,
    get_schema_name_for_domain,
)


class TestViews(HQDBTestCase):

    def setUp(self):
        super(TestViews, self).setUp()
        self.app.appbuilder.add_permissions(update_perms=True)
        self.app.appbuilder.sm.sync_role_definitions()

        self.oauth_mock = OAuthMock()
        self.app.appbuilder.sm.oauth_remotes = {"commcare": self.oauth_mock}

        gamma_role = self.app.appbuilder.sm.find_role('Gamma')
        self.user = self.app.appbuilder.sm.find_user(self.oauth_mock.user_json['username'])
        if not self.user:
            self.user = self.app.appbuilder.sm.add_user(**self.oauth_mock.user_json, role=[gamma_role])

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
        with self.hq_db.get_sqla_engine_with_context() as engine:
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

    @patch.object(DomainSyncUtil, "_get_domain_access", return_value=({"can_write": True, "can_read": True}, []))
    def test_domain_select_works(self, *args):
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

    @patch('hq_superset.hq_requests.get_valid_cchq_oauth_token', return_value={})
    @patch.object(DomainSyncUtil, "sync_domain_role", return_value=True)
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

    @patch.object(DomainSyncUtil, "sync_domain_role", return_value=True)
    def test_datasource_upload(self, *args):
        client = self.app.test_client()
        self.login(client)
        client.get('/domain/select/test1/', follow_redirects=True)
        ucr_id = self.oauth_mock.test1_datasources['objects'][0]['id']
        with patch("hq_superset.views.trigger_datasource_refresh") as refresh_mock:
            refresh_mock.return_value = redirect("/tablemodelview/list/")
            client.get(f'/hq_datasource/update/{ucr_id}?name=ds1', follow_redirects=True)
            refresh_mock.assert_called_once_with(
                'test1',
                ucr_id,
                'ds1'
            )

    @patch.object(DomainSyncUtil, "sync_domain_role", return_value=True)
    def test_trigger_datasource_refresh_with_api_exception(self, *args):
        with patch("hq_superset.views.download_and_subscribe_to_datasource", side_effect=HQAPIException('mocked error')):
            client = self.app.test_client()
            self.login(client)
            client.get('/domain/select/test1/', follow_redirects=True)
            ucr_id = self.oauth_mock.test1_datasources['objects'][0]['id']
            response = client.get(f'/hq_datasource/update/{ucr_id}?name=ds1')

            with client.session_transaction() as session:
                flash_danger_message = dict(session['_flashes']).get('danger')
                self.assertEqual(
                    flash_danger_message,
                    'The datasource refresh failed: mocked error. Please try again or report if issue persists.'
                )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, "/tablemodelview/list/")

    def test_trigger_datasource_refresh_with_errors(self, *args):
        from hq_superset.views import (
            ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES,
            trigger_datasource_refresh,
        )

        file_path = '/file_path/towards/dimagi'
        file_size = ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES - 1
        with (
            patch("hq_superset.views.download_and_subscribe_to_datasource", return_value=(file_path, file_size)),
            patch("hq_superset.views.get_datasource_defn", return_value=TEST_DATASOURCE),
            patch("hq_superset.views.refresh_hq_datasource", side_effect=Exception('mocked error')),
            patch('hq_superset.views.os.remove') as os_remove_mock
        ):
            response = trigger_datasource_refresh('test1', 1, 'ds_name')

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, "/tablemodelview/list/")
            os_remove_mock.assert_called_once_with(file_path)

    @patch('hq_superset.hq_requests.get_valid_cchq_oauth_token', return_value={})
    @patch('hq_superset.services.subscribe_to_hq_datasource')
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

            with (
                patch("hq_superset.views.download_and_subscribe_to_datasource") as download_ds_mock,
                patch("hq_superset.views.get_datasource_defn") as ds_defn_mock,
                patch(routing_method) as refresh_mock,
                patch("hq_superset.views.g") as mock_g
            ):
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
                    user_id
                )

        # When datasource size is more than the limit, it should get
        #   queued via celery
        _test_sync_or_async(
            ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES + 1,
            "hq_superset.views.queue_refresh_task",
            UserMock().user_id
        )
        # When datasource size is within the limit, it should get
        #   refreshed directly
        _test_sync_or_async(
            ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES - 1,
            "hq_superset.views.refresh_hq_datasource",
            None
        )

    @patch('hq_superset.hq_requests.get_valid_cchq_oauth_token', return_value={})
    @patch('hq_superset.services.subscribe_to_hq_datasource')
    @patch('hq_superset.hq_requests.HQRequest.get')
    def test_download_datasource(self, hq_request_get_mock, subscribe_mock, *args):
        from hq_superset.services import download_and_subscribe_to_datasource

        hq_request_get_mock.return_value = MockResponse(
            json_data=TEST_UCR_CSV_V1,
            status_code=200,
        )
        ucr_id = self.oauth_mock.test1_datasources['objects'][0]['id']
        path, size = download_and_subscribe_to_datasource('test1', ucr_id)
        subscribe_mock.assert_called_once_with(
            'test1',
            ucr_id,
        )
        with open(path, 'rb') as f:
            self.assertEqual(pickle.load(f), TEST_UCR_CSV_V1)
            self.assertEqual(size, len(pickle.dumps(TEST_UCR_CSV_V1)))
        os.remove(path)

    @patch('hq_superset.services.unsubscribe_from_hq_datasource')
    @patch('hq_superset.hq_requests.get_valid_cchq_oauth_token', return_value={})
    def test_refresh_hq_datasource(self, unsubscribe_mock, *args):
        from hq_superset.services import refresh_hq_datasource

        ucr_id = self.oauth_mock.test1_datasources['objects'][0]['id']
        ds_name = "ds1"
        with (
            patch("hq_superset.services.get_datasource_file") as csv_mock,
            self.app.test_client() as client
        ):
            self.login(client)
            client.get('/domain/select/test1/', follow_redirects=True)
            
            def _test_upload(test_data, expected_output):
                csv_mock.return_value = StringIO(test_data)
                refresh_hq_datasource('test1', ucr_id, ds_name, '_', TEST_DATASOURCE)
                datasets = json.loads(client.get('/api/v1/dataset/').data)
                self.assertEqual(len(datasets['result']), 1)
                self.assertEqual(datasets['result'][0]['schema'], get_schema_name_for_domain('test1'))
                self.assertEqual(datasets['result'][0]['table_name'], ucr_id)
                self.assertEqual(datasets['result'][0]['description'], ds_name)
                with self.hq_db.get_sqla_engine_with_context() as engine:
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
            unsubscribe_mock.assert_called()

            client.get('/hq_datasource/list/', follow_redirects=True)
            self.assert_context('ucr_id_to_pks', {})
