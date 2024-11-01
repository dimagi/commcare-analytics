import doctest
from unittest.mock import patch

from flask import session

from hq_superset.utils import DomainSyncUtil, get_column_dtypes

from ..const import SESSION_DOMAIN_ROLE_LAST_SYNCED_AT
from .base_test import LoginUserTestMixin, SupersetTestCase
from .const import TEST_DATASOURCE


def test_get_column_dtypes():
    datasource_defn = TEST_DATASOURCE
    column_dtypes, date_columns, _ = get_column_dtypes(datasource_defn)
    assert column_dtypes == {
        'doc_id': 'string',
        'data_visit_comment_fb984fda': 'string',
        'data_visit_number_33d63739': 'Int64'
    }
    assert set(date_columns) == {
        'inserted_at',
        'data_lmp_date_5e24b993',
        'data_visit_date_eaece89e'
    }


def test_doctests():
    import hq_superset.utils
    results = doctest.testmod(hq_superset.utils)
    assert results.failed == 0


class TestDomainSyncUtil(LoginUserTestMixin, SupersetTestCase):
    PLATFORM_ROLE_NAMES = ["Gamma", "sql_lab", "dataset_editor"]

    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_gamma_role_assigned_for_edit_permissions(self, get_domain_access_mock):
        security_manager = self.app.appbuilder.sm
        self._ensure_platform_roles_exist(security_manager)

        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=True,
            can_read=True,
            roles=[],
        )
        additional_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")
        assert len(additional_roles) == 1
        assert additional_roles[0].name == "Gamma"

    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_no_roles_assigned_without_at_least_read_permission(self, get_domain_access_mock):
        security_manager = self.app.appbuilder.sm
        self._ensure_platform_roles_exist(security_manager)

        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=False,
            can_read=False,
            roles=["sql_lab", "dataset_editor"],
        )
        additional_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")
        assert not additional_roles

    @patch.object(DomainSyncUtil, "_domain_user_role_name")
    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_read_permission_gives_custom_domain_role(self, get_domain_access_mock, domain_user_role_name_mock):
        domain_user_role_name = "test-domain_user_1_read_only"
        domain_user_role_name_mock.return_value = domain_user_role_name

        security_manager = self.app.appbuilder.sm
        self._ensure_platform_roles_exist(security_manager)

        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=False,
            can_read=True,
            roles=[],
        )
        additional_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")
        assert len(additional_roles) == 1
        assert additional_roles[0].name == domain_user_role_name

    @patch.object(DomainSyncUtil, "_domain_user_role_name")
    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_permissions_change_updates_user_role(self, get_domain_access_mock, domain_user_role_name_mock):
        domain_user_role_name = "test-domain_user_1_read_only"
        domain_user_role_name_mock.return_value = domain_user_role_name

        security_manager = self.app.appbuilder.sm
        self._ensure_platform_roles_exist(security_manager)

        # user has maximum access
        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=False,
            can_read=True,
            roles=[],
        )
        additional_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")
        assert additional_roles[0].name == domain_user_role_name

        # user has no access
        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=False,
            can_read=False,
            roles=[],
        )
        additional_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")
        assert not additional_roles

    @patch('hq_superset.utils.datetime_utcnow_naive')
    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_sync_domain_role(self, get_domain_access_mock, utcnow_mock):
        client = self.app.test_client()
        self.login(client)

        utcnow_mock_return = "2024-11-01 14:30:04.323000+00:00"
        utcnow_mock.return_value = utcnow_mock_return
        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=False,
            can_read=True,
            roles=[],
        )
        security_manager = self.app.appbuilder.sm

        self.assertIsNone(session.get(SESSION_DOMAIN_ROLE_LAST_SYNCED_AT))
        DomainSyncUtil(security_manager).sync_domain_role("test-domain")
        self.assertEqual(session[SESSION_DOMAIN_ROLE_LAST_SYNCED_AT], utcnow_mock_return)
        self.logout(client)

    def _ensure_platform_roles_exist(self, sm):
        for role_name in self.PLATFORM_ROLE_NAMES:
            sm.add_role(role_name)

    @staticmethod
    def _to_permissions_response(can_write, can_read, roles):
        return {
            "can_write": can_write,
            "can_read": can_read,
        }, roles
