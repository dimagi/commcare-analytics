import doctest
import json

from unittest.mock import patch
from .base_test import SupersetTestCase

from hq_superset.hq_domain import user_domains
from hq_superset.utils import SESSION_USER_DOMAINS_KEY


SESSION_MOCK_VALUE = {
    SESSION_USER_DOMAINS_KEY:[
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

@patch('hq_superset.hq_domain.session', new=SESSION_MOCK_VALUE)
class TestHQDomain(SupersetTestCase):

    @patch('hq_superset.hq_domain.is_user_admin', return_value=False)
    def test_user_domains(self, admin_mock):
        import hq_superset
        print(hq_superset.hq_domain.session)
        self.assertEqual(user_domains(), ['test1', 'test2'])

    @patch('hq_superset.hq_domain.is_user_admin', return_value=True)
    def test_user_domains_admin(self, admin_mock):
        self.assertEqual(user_domains(), [])

