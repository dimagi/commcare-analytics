from urllib.parse import urljoin

import hq_superset
from flask_appbuilder.security.manager import AUTH_OAUTH
from superset import config as superset_config

hq_superset.patch_superset_config(superset_config)


HQ_BASE_URL = 'http://127.0.0.1:8000/'
AUTH_TYPE = AUTH_OAUTH
OAUTH_PROVIDERS = [
    {
        'name': 'commcare',
        'token_key':'access_token',
        'remote_app': {
            'client_id': '',
            'client_secret': '',
            'api_base_url': HQ_BASE_URL,
            'access_token_url': urljoin(HQ_BASE_URL, '/oauth/token/'),
            'authorize_url': urljoin(HQ_BASE_URL, '/oauth/authorize/'),
            'client_kwargs':{
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
