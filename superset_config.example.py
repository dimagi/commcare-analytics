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

# Any other additional roles to be assigned to the user on top of the base role
# Note: by design we cannot use AUTH_USER_REGISTRATION_ROLE to
# specify more than one role
AUTH_USER_ADDITIONAL_ROLES = ["sql_lab"]

SHARED_DIR = 'shared_dir'

# Enable below for sentry integration
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
sentry_sdk.init(
    dsn='',
    integrations=[FlaskIntegration()],
    environment='test',
    send_default_pii=True,
)

CACHE_CONFIG = {
      'CACHE_TYPE': 'RedisCache',
      'CACHE_DEFAULT_TIMEOUT': 300,
      'CACHE_KEY_PREFIX': 'superset_',
      'CACHE_REDIS_URL': 'redis://localhost:6279/0'
}

from cachelib.redis import RedisCache
RESULTS_BACKEND = RedisCache(
    host='localhost', port=6279, key_prefix='superset_results'
)

from celery.schedules import crontab

class CeleryConfig(object):
    broker_url = 'redis://localhost:6279/0'
    imports = (
        'superset.sql_lab',
        'superset.tasks',
        'hq_superset.tasks',
    )
    result_backend = 'redis://localhost:6279/0'
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
            'schedule': crontab(minute=1, hour='*'),
        },
    }

CELERY_CONFIG = CeleryConfig