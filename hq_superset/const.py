# The name of the database for storing data related to CommCare HQ
HQ_DATABASE_NAME = "HQ Data"

OAUTH2_DATABASE_NAME = "oauth2-server-data"

HQ_USER_ROLE_NAME = "hq_user"

HQ_ROLE_NAME_MAPPING = {
    "gamma": "Gamma",
    "dataset_editor": "dataset_editor",
    "sql_lab": "sql_lab",
}

HQ_CONFIGURABLE_VIEW_MENUS = [
    "Chart",
    "Dashboard",
    "Dataset",
    "Datasource",
    "Database",
]

MENU_ACCESS_VIEW_MENUS = [
    "Select a Domain",
    "Home",
    "Data",
    "Dashboards",
    "Charts",
    "Datasets",
]

SCHEMA_ACCESS_PERMISSION = "schema_access"
MENU_ACCESS_PERMISSIONS = "menu_access"
CAN_READ_PERMISSION = "can_read"
CAN_WRITE_PERMISSION = "can_write"
CAN_EDIT_PERMISSION = "can_edit"
CAN_ADD_PERMISSION = "can_add"
CAN_DELETE_PERMISSIONS = "can_delete"

WRITE_PERMISSIONS = [
    CAN_WRITE_PERMISSION,
    CAN_ADD_PERMISSION,
    CAN_DELETE_PERMISSIONS,
    CAN_EDIT_PERMISSION,
]
