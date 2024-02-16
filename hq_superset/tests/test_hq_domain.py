from unittest.mock import patch

from flask import g

from hq_superset.hq_domain import (
    DOMAIN_EXCLUDED_VIEWS,
    after_request_hook,
    before_request_hook,
    ensure_domain_selected,
    is_valid_user_domain,
    user_domains,
)
from hq_superset.utils import (
    SESSION_USER_DOMAINS_KEY,
    DomainSyncUtil,
    get_schema_name_for_domain,
)

from .base_test import HQDBTestCase, SupersetTestCase
from .utils import setup_hq_db

MOCK_DOMAIN_SESSION = {
    SESSION_USER_DOMAINS_KEY: [
        {'domain_name': 'test1', 'project_name': 'test1'},
        {'domain_name': 'test2', 'project_name': 'test 1'},
    ]
}


@patch('hq_superset.hq_domain.session', new=MOCK_DOMAIN_SESSION)
class TestDomainUtils(SupersetTestCase):
    @patch('hq_superset.hq_domain.is_user_admin', return_value=False)
    def test_user_domains_returns_session_domains(self, mock):
        self.assertEqual(user_domains(), ['test1', 'test2'])

    @patch('hq_superset.hq_domain.is_user_admin', return_value=True)
    def test_user_domains_is_empty_for_admin(self, mock):
        self.assertEqual(user_domains(), [])

    @patch('hq_superset.hq_domain.is_user_admin', return_value=False)
    def test_is_valid_user_domain(self, mock):
        self.assertEqual(is_valid_user_domain('test1'), True)
        self.assertEqual(is_valid_user_domain('unknown'), False)

    @patch('hq_superset.hq_domain.is_user_admin', return_value=True)
    def test_is_valid_user_domain_admin(self, mock):
        self.assertEqual(is_valid_user_domain('test1'), True)
        self.assertEqual(is_valid_user_domain('unknown'), True)


@patch('hq_superset.hq_domain.session', new=MOCK_DOMAIN_SESSION)
class TestEnsureDomainSelected(SupersetTestCase):
    @patch('hq_superset.hq_domain.is_user_admin', return_value=False)
    def test_if_domain_not_set_redirects(self, *args):
        with patch('hq_superset.hq_domain.request') as request_mock:
            request_mock.url_rule.endpoint = 'any'
            response = ensure_domain_selected()
            self.assertEqual(response.status, '302 FOUND')
            self.assertTrue('/domain/list' in str(response.data))

    @patch('hq_superset.hq_domain.is_user_admin', return_value=False)
    def test_does_not_redirect_for_special_urls(self, *args):
        with patch('hq_superset.hq_domain.request') as request_mock:
            request_mock.url_rule.endpoint = DOMAIN_EXCLUDED_VIEWS[0]
            self.assertEqual(ensure_domain_selected(), None)

    @patch('hq_superset.hq_domain.is_user_admin', return_value=False)
    def test_if_domain_is_set_does_not_redirect(self, *args):
        with patch('hq_superset.hq_domain.request') as request_mock:
            request_mock.url_rule.endpoint = 'any'
            domain = 'test1'
            request_mock.cookies = {'hq_domain': domain}
            self.assertFalse(getattr(g, 'hq_domain', False))
            ensure_domain_selected()
            self.assertEqual(g.hq_domain, domain)

    @patch('hq_superset.hq_domain.is_user_admin', return_value=False)
    def test_if_invalid_domain_redirects(self, *args):
        with patch('hq_superset.hq_domain.request') as request_mock:
            request_mock.url_rule.endpoint = 'any'
            request_mock.cookies = {'hq_domain': 'not-user-domain'}
            response = ensure_domain_selected()
            self.assertEqual(response.status, '302 FOUND')
            self.assertTrue('/domain/list' in str(response.data))

    @patch('hq_superset.hq_domain.is_user_admin', return_value=True)
    def test_does_not_redirect_for_admin(self, *args):
        with patch('hq_superset.hq_domain.request') as request_mock:
            request_mock.url_rule.endpoint = 'any'
            self.assertEqual(ensure_domain_selected(), None)


class TestCustomHooks(SupersetTestCase):
    def test_hooks_are_registered(self):
        import superset

        self.assertEqual(
            superset.app.before_request_funcs[None][-1], before_request_hook
        )

        self.assertEqual(
            superset.app.after_request_funcs[None][-1], after_request_hook
        )


class TestDomainSyncUtil(HQDBTestCase):
    def setUp(self):
        super(TestDomainSyncUtil, self).setUp()
        self.domain = 'test-domain'
        setup_hq_db()

    def test_schema_gets_created(self):
        schema_name = get_schema_name_for_domain(self.domain)
        with self.hq_db.get_sqla_engine_with_context() as engine:
            self.assertFalse(
                engine.dialect.has_schema(engine, schema_name),
            )
            DomainSyncUtil._ensure_schema_created(self.domain)
            self.assertTrue(
                engine.dialect.has_schema(engine, schema_name),
            )
