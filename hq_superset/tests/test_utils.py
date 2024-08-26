import doctest
from unittest.mock import patch

from hq_superset.utils import get_column_dtypes, DomainSyncUtil
from hq_superset.const import USER_VIEW_MENU_NAMES
from .base_test import SupersetTestCase
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


class TestDomainSyncUtil(SupersetTestCase):
    PLATFORM_ROLE_NAMES = ["Gamma", "sql_lab", "dataset_editor"]

    @patch.object(DomainSyncUtil, "_domain_user_role_name")
    def test_get_user_domain_role_for_permissions(self, domain_user_role_name_mock):
        role_name = "test-domain_user_1"
        domain_user_role_name_mock.return_value = role_name

        permissions_test_cases = [
            {"can_write": True, "can_read": True},
            {"can_write": True, "can_read": False},
            {"can_write": False, "can_read": False},
            {"can_write": False, "can_read": True},
        ]
        security_manager = self.app.appbuilder.sm

        for permissions in permissions_test_cases:
            role = DomainSyncUtil(security_manager)._get_user_domain_role_for_permissions(
                "test-domain", permissions
            )

            for view_menu_name in USER_VIEW_MENU_NAMES:
                for permission_name in ["can_write", "can_read"]:
                    pv = security_manager.find_permission_view_menu(permission_name, view_menu_name)
                    if permissions[permission_name]:
                        assert pv in role.permissions
                    else:
                        assert pv not in role.permissions

    @patch.object(DomainSyncUtil, "_domain_user_role_name")
    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_admin_additional_domain_roles(self, get_domain_access_mock, domain_user_role_name_mock):
        domain_user_role_name = "test-domain_user_1"
        domain_user_role_name_mock.return_value = domain_user_role_name

        security_manager = self.app.appbuilder.sm
        self._ensure_platform_roles_exist(security_manager)

        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=True,
            can_read=True,
            roles=["Gamma", "sql_lab", "dataset_editor"],
        )
        domain_user_role, platform_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")

        assert domain_user_role.name == "test-domain_user_1"
        assert sorted([role.name for role in platform_roles]) == sorted(self.PLATFORM_ROLE_NAMES)

    @patch.object(DomainSyncUtil, "_domain_user_role_name")
    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_limited_additional_domain_roles(self, get_domain_access_mock, domain_user_role_name_mock):
        domain_user_role_name = "test-domain_user_1"
        domain_user_role_name_mock.return_value = domain_user_role_name

        security_manager = self.app.appbuilder.sm
        self._ensure_platform_roles_exist(security_manager)

        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=False,
            can_read=True,
            roles=["sql_lab"],
        )
        _, platform_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")

        assert len(platform_roles) == 1
        assert platform_roles[0].name == "sql_lab"

    @patch.object(DomainSyncUtil, "_domain_user_role_name")
    @patch.object(DomainSyncUtil, "_get_domain_access")
    def test_no_access_domain_roles(self, get_domain_access_mock, domain_user_role_name_mock):
        domain_user_role_name = "test-domain_user_1"
        domain_user_role_name_mock.return_value = domain_user_role_name

        security_manager = self.app.appbuilder.sm
        self._ensure_platform_roles_exist(security_manager)

        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=False,
            can_read=False,
            roles=[],
        )
        domain_user_role, platform_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")
        assert domain_user_role is None
        assert platform_roles == []

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
            roles=["sql_lab"],
        )
        _, platform_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")

        assert platform_roles[0].name == "sql_lab"

        # user has no access
        get_domain_access_mock.return_value = self._to_permissions_response(
            can_write=False,
            can_read=False,
            roles=[],
        )
        domain_user_role, platform_roles = DomainSyncUtil(security_manager)._get_additional_user_roles("test-domain")
        assert domain_user_role is None
        assert platform_roles == []

    def _ensure_platform_roles_exist(self, sm):
        for role_name in self.PLATFORM_ROLE_NAMES:
            sm.add_role(role_name)

    @staticmethod
    def _to_permissions_response(can_write, can_read, roles):
        return {
            "can_write": can_write,
            "can_read": can_read,
        }, roles
