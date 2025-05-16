import json
from contextlib import contextmanager
from unittest.mock import patch

from hq_superset.tests.base_test import HQDBTestCase


class TestAPI(HQDBTestCase):

    def test_post_dataset_change_with_doc_ids(self):
        payload = {
            "data_source_id": "abc123",
            "doc_id": "",
            "doc_ids": ["def123", "def456"],
            "data": [
                {"doc_id": "def123", "foo": "bar"},
                {"doc_id": "def456", "foo": "bar"}
            ]
        }
        with (
            patch_oauth_validation(),
            patch('hq_superset.api.process_dataset_change.delay')
        ):
            response = self.client.post(
                '/commcarehq_dataset/change/',
                data=json.dumps(payload),
                content_type='application/json',
                headers={"Authorization": "Bearer test-token"}
            )
        assert response.status_code == 202
        assert response.text == 'Dataset change accepted'

    def test_post_dataset_change_with_doc_id(self):
        payload = {
            "data_source_id": "abc123",
            "doc_id": "def123",
            "data": [
                {"doc_id": "def123", "foo": "bar"}
            ]
        }
        with (
            patch_oauth_validation(),
            patch('hq_superset.api.process_dataset_change.delay')
        ):
            response = self.client.post(
                '/commcarehq_dataset/change/',
                data=json.dumps(payload),
                content_type='application/json',
                headers={"Authorization": "Bearer test-token"}
            )
        assert response.status_code == 202
        assert response.text == 'Dataset change accepted'

    def test_post_dataset_change_invalid_format(self):
        # Missing required fields
        payload = {"foo": "bar"}
        with patch_oauth_validation():
            response = self.client.post(
                '/commcarehq_dataset/change/',
                data=json.dumps(payload),
                content_type='application/json',
                headers={"Authorization": "Bearer test-token"}
            )
        assert response.status_code == 400
        assert response.json == {'error': 'Could not parse change request'}

    def test_post_dataset_change_invalid_json(self):
        with patch_oauth_validation():
            response = self.client.post(
                '/commcarehq_dataset/change/',
                data='invalid json',
                content_type='application/json',
                headers = {"Authorization": "Bearer test-token"}
            )
        assert response.status_code == 400
        assert response.json == {"error": "Invalid JSON syntax"}

    def test_post_dataset_change_too_large(self):
        row = {"doc_id": "def123", "foo": "bar"}
        row_str = json.dumps(row)
        num_rows = 10 * 1024 * 1024 // len(row_str) + 1  # > 10MB limit
        payload = {
            "data_source_id": "abc123",
            "doc_id": "def123",
            "data": [row] * num_rows
        }
        with patch_oauth_validation():
            response = self.client.post(
                '/commcarehq_dataset/change/',
                data=json.dumps(payload),
                content_type='application/json',
                headers={"Authorization": "Bearer test-token"}
            )
        assert response.status_code == 413
        assert response.json == {'error': 'Entity is too large'}


@contextmanager
def patch_oauth_validation():

    class DummyValidator:
        TOKEN_TYPE = 'bearer'
        def __call__(self, *a, **kw):
            return self
        def validate_request(self, *a, **kw):
            return True
        def authenticate_token(self, token_string):
            class Token: pass
            return Token()
        def validate_token(self, token, scopes, request, **kwargs):
            return True  # Accepts any token

    with patch("hq_superset.oauth2_server.create_bearer_token_validator", return_value=DummyValidator):
        # Re-register the patched validator with require_oauth
        from hq_superset import oauth2_server
        oauth2_server.require_oauth._token_validators.clear()
        oauth2_server.require_oauth.register_token_validator(DummyValidator())

        yield
