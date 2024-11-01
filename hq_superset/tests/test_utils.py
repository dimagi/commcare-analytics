import doctest
from unittest.mock import patch

from hq_superset.utils import get_column_dtypes, DomainSyncUtil
from .base_test import SupersetTestCase
from .const import TEST_DATASOURCE
from hq_superset.const import GAMMA_ROLE


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


class TestDomainSyncUtil(SupersetTestCase):
    PLATFORM_ROLE_NAMES = ["sql_lab", "dataset_editor"]

    @patch.object(DomainSyncUtil, "_domain_user_role_name")
    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_gamma_role_assigned_for_edit_permissions(self, get_domain_access_mock, domain_user_role_name_mock):
        self._ensure_gamma_role_exists()

        domain_user_role_name = "test-domain_user_1"
        domain_user_role_name_mock.return_value = domain_user_role_name

        security_manager = self.app.appbuilder.sm
        self._ensure_platform_roles_exist(security_manager)

        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=True,
            can_read=True,
            roles=[],
        )
        additional_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")
        assert len(additional_roles) == 1
        new_role = additional_roles[0]

        assert new_role.name == domain_user_role_name
        gamma_role = security_manager.find_role(GAMMA_ROLE)
        assert gamma_role.permissions == new_role.permissions


    @patch.object(DomainSyncUtil, "_domain_user_role_name")
    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_no_roles_assigned_without_at_least_read_permission(self, get_domain_access_mock, domain_user_role_name_mock):
        domain_user_role_name = "test-domain_user_1"
        domain_user_role_name_mock.return_value = domain_user_role_name

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
        domain_user_role_name = "test-domain_user_1"
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
        assert additional_roles[0].permissions

    @patch.object(DomainSyncUtil, "_domain_user_role_name")
    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_permissions_change_updates_user_role(self, get_domain_access_mock, domain_user_role_name_mock):
        domain_user_role_name = "test-domain_user_1"
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

    def _ensure_platform_roles_exist(self, sm):
        for role_name in self.PLATFORM_ROLE_NAMES:
            sm.add_role(role_name)

    @staticmethod
    def _to_permissions_response(can_write, can_read, roles):
        return {
            "can_write": can_write,
            "can_read": can_read,
        }, roles

    def _ensure_gamma_role_exists(self):
        """
        This method mocks the gamma role if one does not exist
        """
        security_manager = self.app.appbuilder.sm
        gamma_role = security_manager.find_role(GAMMA_ROLE)

        if not gamma_role:
            gamma_role = security_manager.add_role(GAMMA_ROLE)
            permission = security_manager.add_permission_view_menu(
                "can_write", "dashboard",
            )
            security_manager.add_permission_role(gamma_role, permission)