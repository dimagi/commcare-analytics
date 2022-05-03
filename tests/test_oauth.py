import unittest
from unittest.mock import MagicMock

from hq_superset.oauth import CommCareSecurityManager, SupersetSecurityManager


class TestOauth(unittest.TestCase):

    def setUp(self) -> None:
        app_builder = MagicMock()
        self.csm = CommCareSecurityManager(app_builder)


if __name__ == '__main__':
    unittest.main()
