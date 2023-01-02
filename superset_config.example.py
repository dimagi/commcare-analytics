from flask_appbuilder.security.manager import AUTH_OAUTH
from superset import config as superset_config

import hq_superset


# Any other additional roles to be assigned to the user on top of the base role
# Note: by design we cannot use AUTH_USER_REGISTRATION_ROLE to
# specify more than one role
superset_config.AUTH_USER_ADDITIONAL_ROLES = ["sql_lab"]

hq_superset.patch_superset_config(superset_config)


AUTH_TYPE = AUTH_OAUTH

# Override this to reflect your local Postgres DB
SQLALCHEMY_DATABASE_URI = 'postgresql://commcarehq:commcarehq@localhost:5432/superset_meta'

# Populate with oauth credentials from your local CommCareHQ
OAUTH_PROVIDERS = [
    {
        'name': 'commcare',
        'token_key': 'access_token',
        'remote_app': {
            'client_id': '',
            'client_secret': '',
            'api_base_url': 'http://127.0.0.1:8000/',
            'access_token_url': 'http://127.0.0.1:8000/oauth/token/',
            'authorize_url': 'http://127.0.0.1:8000/oauth/authorize/',
            'client_kwargs': {
                'scope': 'reports:view access_apis'
            },
        }
    }
]

# Will allow user self registration, allowing to create Flask users from
# Authorized User
AUTH_USER_REGISTRATION = True

# The default user self registration role
AUTH_USER_REGISTRATION_ROLE = "Gamma"

