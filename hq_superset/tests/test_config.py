import hq_superset

from flask_appbuilder.security.manager import AUTH_OAUTH
from superset import config as superset_config

superset_config.WTF_CSRF_ENABLED = False
superset_config.TESTING = True
superset_config.SECRET_KEY = 'abc'

hq_superset.patch_superset_config(superset_config)

SECRET_KEY = superset_config.SECRET_KEY

AUTH_TYPE = AUTH_OAUTH

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

SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
SQLALCHEMY_TRACK_MODIFICATIONS = False

AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Gamma"
AUTH_USER_ADDITIONAL_ROLES = ["sql_lab"]
