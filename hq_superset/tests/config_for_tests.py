# Running tests
# =============
#
# If you are using PostgreSQL for `SQLALCHEMY_DATABASE_URI` and/or
# `HQ_DATA_DB` then you need to create test databases. The test runner
# does not do this for you. e.g.
#
#     $ psql -h localhost -p 5433 -U postgres
#     # CREATE DATABASE superset_test;
#     # CREATE DATABASE superset_test_hq;
#
# Run tests with `pytest`. e.g.
#
#     $ pytest hq_superset/tests/test_hq_domain.py
#
from flask_appbuilder.security.manager import AUTH_OAUTH

from hq_superset import flask_app_mutator, oauth

WTF_CSRF_ENABLED = False
TESTING = True
SECRET_KEY = 'abc'

# Any other additional roles to be assigned to the user on top of the base role
# Note: by design we cannot use AUTH_USER_REGISTRATION_ROLE to
# specify more than one role
AUTH_USER_ADDITIONAL_ROLES = ['sql_lab']

HQ_DATA_DB = (
    'postgresql://commcarehq:commcarehq@localhost:5432/test_superset_hq'
)

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
            'client_kwargs': {'scope': 'reports:view access_apis'},
        },
    }
]

SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
SHARED_DIR = 'shared_dir'
ENABLE_ASYNC_UCR_IMPORTS = True
CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_URL': 'redis://localhost:6379/0',
}

AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = 'Gamma'

# CommCare Analytics extensions
FLASK_APP_MUTATOR = flask_app_mutator
CUSTOM_SECURITY_MANAGER = oauth.CommCareSecurityManager
