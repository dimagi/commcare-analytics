# Configuring Superset
# ====================
#
# Set the `SUPERSET_CONFIG_PATH` environment variable to allow Superset
# to find this config file. e.g.
#
#     $ export SUPERSET_CONFIG_PATH=$HOME/src/dimagi/hq_superset/superset_config.py
#
import sentry_sdk
from cachelib.redis import RedisCache
from celery.schedules import crontab
from flask_appbuilder.security.manager import AUTH_OAUTH
from sentry_sdk.integrations.flask import FlaskIntegration

from hq_superset import flask_app_mutator, oauth

# Use a tool to generate a sufficiently random string, e.g.
#     $ openssl rand -base64 42
# SECRET_KEY = ...

AUTH_TYPE = AUTH_OAUTH  # Authenticate with CommCare HQ
# AUTH_TYPE = AUTH_DB  # Authenticate with Superset user DB

# Override this to reflect your local Postgres DB
SQLALCHEMY_DATABASE_URI = (
    'postgresql://postgres:postgres@localhost:5433/superset_meta'
)

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
            'client_kwargs': {'scope': 'reports:view access_apis'},
        },
    }
]

# Will allow user self registration, allowing to create Flask users from
# Authorized User
AUTH_USER_REGISTRATION = True

# The default user self registration role
AUTH_USER_REGISTRATION_ROLE = 'Gamma'

# Any other additional roles to be assigned to the user on top of the base role
# Note: by design we cannot use AUTH_USER_REGISTRATION_ROLE to
# specify more than one role
AUTH_USER_ADDITIONAL_ROLES = ['sql_lab']

# This is where async UCR imports are stored temporarily
SHARED_DIR = 'shared_dir'

# If this is enabled, UCRs larger than
#   hq_superset.views.ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES
#   are imported via Celery/Redis.
ENABLE_ASYNC_UCR_IMPORTS = False

# Enable below for sentry integration
sentry_sdk.init(
    dsn='',
    integrations=[FlaskIntegration()],
    environment='test',
    send_default_pii=True,
)

_REDIS_URL = 'redis://localhost:6379/0'

CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_URL': _REDIS_URL,
}

RESULTS_BACKEND = RedisCache(
    host='localhost', port=6379, key_prefix='superset_results'
)


class CeleryConfig:
    broker_url = _REDIS_URL
    imports = (
        'superset.sql_lab',
        'superset.tasks',
        'hq_superset.tasks',
    )
    result_backend = _REDIS_URL
    worker_log_level = 'DEBUG'
    worker_prefetch_multiplier = 10
    task_acks_late = True
    task_annotations = {
        'sql_lab.get_sql_results': {
            'rate_limit': '100/s',
        },
        'email_reports.send': {
            'rate_limit': '1/s',
            'time_limit': 120,
            'soft_time_limit': 150,
            'ignore_result': True,
        },
    }
    beat_schedule = {
        'email_reports.schedule_hourly': {
            'task': 'email_reports.schedule_hourly',
            'schedule': crontab(minute='1', hour='*'),
        },
    }


CELERY_CONFIG = CeleryConfig

LANGUAGES = {
    'en': {'flag': 'us', 'name': 'English'},
    'pt': {'flag': 'pt', 'name': 'Portuguese'},
}

OAUTH2_TOKEN_EXPIRES_IN = {
    'client_credentials': 86400,
}
BASE_URL = 'http://localhost:5000'

# CommCare Analytics extensions
FLASK_APP_MUTATOR = flask_app_mutator
CUSTOM_SECURITY_MANAGER = oauth.CommCareSecurityManager
