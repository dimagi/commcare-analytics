from hq_superset.hq_requests import HQRequest
from hq_superset.tests.base_test import SupersetTestCase


class TestAbsoluteUrl(SupersetTestCase):

    def test_absolute_url(self):
        url = "/test-url"
        hq_request = HQRequest(url)
        self.assertEqual(
            hq_request.absolute_url,
            'http://127.0.0.1:8000/test-url'
        )

    def test_absolute_url_no_slash(self):
        url = "test-url"
        hq_request = HQRequest(url)
        self.assertEqual(
            hq_request.absolute_url,
            'http://127.0.0.1:8000/test-url'
        )
