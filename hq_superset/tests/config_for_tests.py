import hq_superset

from flask_appbuilder.security.manager import AUTH_OAUTH
from superset import config as superset_config

superset_config.WTF_CSRF_ENABLED = False
superset_config.TESTING = True
superset_config.SECRET_KEY = 'abc'

# Any other additional roles to be assigned to the user on top of the base role
# Note: by design we cannot use AUTH_USER_REGISTRATION_ROLE to
# specify more than one role
superset_config.AUTH_USER_ADDITIONAL_ROLES = ["sql_lab"]

# Todo; add to github workflow
superset_config.HQ_DATA_DB = "postgresql://commcarehq:commcarehq@localhost:5432/test_superset_hq"

superset_config.AUTH_TYPE = AUTH_OAUTH

superset_config.OAUTH_PROVIDERS = [
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

# This is set by 
superset_config.SQLALCHEMY_DATABASE_URI = "sqlite:///test.db"


superset_config.AUTH_USER_REGISTRATION = True
superset_config.AUTH_USER_REGISTRATION_ROLE = "Gamma"

hq_superset.patch_superset_config(superset_config)
