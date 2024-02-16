import datetime
from unittest.mock import patch

from flask import session

from hq_superset.oauth import OAuthSessionExpired, get_valid_cchq_oauth_token
from hq_superset.utils import (
    SESSION_OAUTH_RESPONSE_KEY,
    SESSION_USER_DOMAINS_KEY,
)

from .base_test import SupersetTestCase


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


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

    def authorize_access_token(self):
        return {'access_token': 'some-key'}

    def get(self, url, token):
        return {
            'api/v0.5/identity/': MockResponse(self.user_json, 200),
            'api/v0.5/user_domains?feature_flag=superset-analytics&can_view_reports=true': MockResponse(
                self.domain_json, 200
            ),
        }[url]


class TestOauthSecurityManger(SupersetTestCase):
    def tearDown(self):
        session.clear()

    def test_oauth_user_info(self):
        oauth_mock = OAuthMock()
        appbuilder = self.app.appbuilder
        appbuilder.sm.oauth_remotes = {'commcare': oauth_mock}
        self.assertEqual(
            appbuilder.sm.oauth_user_info('commcare'), oauth_mock.user_json
        )
        self.assertEqual(
            session[SESSION_USER_DOMAINS_KEY],
            oauth_mock.domain_json['objects'],
        )


class TestGetOAuthTokenGetter(SupersetTestCase):
    def tearDown(self):
        session.clear()

    def test_if_token_not_available_raises_exception(self):
        with self.assertRaises(OAuthSessionExpired):
            get_valid_cchq_oauth_token()

    def test_returns_current_token_if_not_expired(self):
        session[SESSION_OAUTH_RESPONSE_KEY] = {
            'access_token': 'some key',
            'expires_at': int(
                (
                    datetime.datetime.now() + datetime.timedelta(minutes=2)
                ).timestamp()
            ),
        }
        self.assertEqual(
            get_valid_cchq_oauth_token(), session[SESSION_OAUTH_RESPONSE_KEY]
        )

    def test_tries_token_refresh_if_expired(self):
        session[SESSION_OAUTH_RESPONSE_KEY] = {
            'access_token': 'some key',
            'refresh_token': 'refresh token',
            'expires_at': int(
                (
                    datetime.datetime.now() - datetime.timedelta(minutes=2)
                ).timestamp()
            ),
        }
        with patch(
            'hq_superset.oauth.refresh_and_fetch_token'
        ) as refresh_mock, patch(
            'hq_superset.oauth.CommCareSecurityManager.set_oauth_session'
        ) as set_mock:
            refresh_mock.return_value = {'access_token': 'new key'}
            self.assertEqual(
                get_valid_cchq_oauth_token(), {'access_token': 'new key'}
            )
            refresh_mock.assert_called_once_with(
                session[SESSION_OAUTH_RESPONSE_KEY]['refresh_token']
            )
            set_mock.assert_called_once_with(
                'commcare', {'access_token': 'new key'}
            )
