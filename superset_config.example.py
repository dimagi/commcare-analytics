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
from flask_appbuilder.security.manager import AUTH_DB, AUTH_OAUTH
from sentry_sdk.integrations.flask import FlaskIntegration

from ddtrace import patch

from hq_superset import flask_app_mutator, oauth
from hq_superset.const import OAUTH2_DATABASE_NAME

# Use a tool to generate a sufficiently random string, e.g.
#     $ openssl rand -base64 42
# SECRET_KEY = ...

# [Fernet](https://cryptography.io/en/latest/fernet/) (symmetric
# encryption) is used to encrypt and decrypt client secrets so that the
# same credentials can be used to subscribe to many data sources.
#
# FERNET_KEYS is a list of keys where the first key is the current one,
# the second is the previous one, etc. Encryption uses the first key.
# Decryption is attempted with each key in turn.
#
# To generate a key:
#     >>> from cryptography.fernet import Fernet
#     >>> Fernet.generate_key()
# Keys can be bytes or strings.
# FERNET_KEYS = [...]

# Authentication backend
AUTH_TYPE = AUTH_OAUTH  # Authenticate with CommCare HQ (only)
# AUTH_TYPE = AUTH_DB  # Authenticate with Superset user DB (only)

# Override these for your databases for Superset and HQ Data
SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@localhost:5432/superset'
SQLALCHEMY_BINDS = {
    OAUTH2_DATABASE_NAME: 'postgresql://postgres:postgres@localhost:5432/superset_oauth2'
}

HQ_DATABASE_URI = "postgresql://commcarehq:commcarehq@localhost:5432/superset_cchq_data"

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

# override expiry time for a specific grant type by
# setting this config
OAUTH2_TOKEN_EXPIRES_IN = {
    # 'client_credentials': 3600  # seconds
}

# Will allow user self registration, allowing to create Flask users from
# Authorized User
AUTH_USER_REGISTRATION = True

# The default user self registration role
AUTH_USER_REGISTRATION_ROLE = "Gamma"

# This is where async UCR imports are stored temporarily for REMOVE_SHARED_FILES_AFTER days
SHARED_DIR = 'shared_dir'
REMOVE_SHARED_FILES_AFTER = 7 # days

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
      'CACHE_REDIS_URL': _REDIS_URL
}

RESULTS_BACKEND = RedisCache(
    host='localhost', port=6379, key_prefix='superset_results'
)

patch(redis=True)

class CeleryConfig:
    accept_content = ['pickle']
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
        # example:
        # 'email_reports.schedule_hourly': {
        #     'task': 'email_reports.schedule_hourly',
        #     'schedule': crontab(minute='1', hour='*'),
        # }
        'delete_redundant_shared_files': {
            'task': 'delete_redundant_shared_files',
            'schedule': crontab(hour='0', minute='0')
        }
    }


CELERY_CONFIG = CeleryConfig

LANGUAGES = {
   'en': {'flag':'us', 'name':'English'},
   'pt': {'flag':'pt', 'name':'Portuguese'}
}

# CommCare Analytics extensions
FLASK_APP_MUTATOR = flask_app_mutator
CUSTOM_SECURITY_MANAGER = oauth.CommCareSecurityManager

TALISMAN_CONFIG = {
    "content_security_policy": {
        "base-uri": ["'self'"],
        "default-src": ["'self'"],
        "img-src": [
            "'self'",
            "blob:",
            "data:",
            "https://apachesuperset.gateway.scarf.sh",
            "https://static.scarf.sh/",
            "*",
        ],
        "worker-src": ["'self'", "blob:"],
        "connect-src": [
            "'self'",
            "https://api.mapbox.com",
            "https://events.mapbox.com",
        ],
        "object-src": "'none'",
        "style-src": [
            "'self'",
            "'unsafe-inline'",
            "https://fonts.googleapis.com",
        ],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "script-src": ["'self'", "'unsafe-eval'"],
    },
    "content_security_policy_nonce_in": ["script-src"],
    "force_https": False,
    "session_cookie_secure": False,
}

USER_DOMAIN_ROLE_EXPIRY = 60 # minutes
SKIP_DATASET_CHANGE_FOR_DOMAINS = []

SERVER_ENVIRONMENT = 'changeme'  # staging, production, etc.