import logging
import time

import superset
from flask import flash, session
from requests.exceptions import HTTPError
from superset.security import SupersetSecurityManager

from .utils import (
    SESSION_OAUTH_RESPONSE_KEY,
    SESSION_USER_DOMAINS_KEY,
)

logger = logging.getLogger(__name__)


class CommCareSecurityManager(SupersetSecurityManager):
    def oauth_user_info(self, provider, response=None):
        logger.debug('Oauth2 provider: {0}.'.format(provider))
        if provider == 'commcare':
            logger.debug('Getting user info from {}'.format(provider))
            user = self._get_hq_response(
                'api/v0.5/identity/', provider, response
            )
            domains = self._get_hq_response(
                'api/v0.5/user_domains?feature_flag=superset-analytics&can_view_reports=true',
                provider,
                response,
            )
            session[SESSION_USER_DOMAINS_KEY] = domains['objects']
            logger.debug(f'user - {user}, domain - {domains}')
            return user

    def _get_hq_response(self, endpoint, provider, token):
        response = self.appbuilder.sm.oauth_remotes[provider].get(
            endpoint, token=token
        )
        if response.status_code != 200:
            url = f'{self.appbuilder.sm.oauth_remotes[provider].api_base_url}{endpoint}'
            message = f'There was an error accessing the CommCareHQ endpoint at {url}'
            logger.exception(message)
            flash(message, 'danger')
            raise HTTPError(message)
        else:
            return response.json()

    def set_oauth_session(self, provider, oauth_response):
        super().set_oauth_session(provider, oauth_response)
        # The default FAB implementation only stores the access_token and disregards
        #   other part of the oauth_response such as `refresh_token` and `expires_at`
        #   keep a track of full response so that refresh_token is not lost for latter use
        #
        # Sample oauth_response
        # {
        #     'access_token': 'AcLBaXPC7HvJiefUYECBWOd4rCN6L9',
        #     'expires_in': 900,
        #     'token_type': 'Bearer',
        #     'scope': 'view',
        #     'reports:view access_apis',
        #     'refresh_token': 'kXU2Xo4RLn1UCYJMX2KWaic1kxI0PP',
        #     'expires_at': 1650872906
        # }
        session[SESSION_OAUTH_RESPONSE_KEY] = oauth_response


class OAuthSessionExpired(Exception):
    pass


def get_valid_cchq_oauth_token():
    # Returns a valid working oauth access_token and also saves it on session
    #   May raise `OAuthSessionExpired`, if a valid working token is not found
    #   The user needs to re-auth using CommCareHQ to get valid tokens
    oauth_response = session.get(SESSION_OAUTH_RESPONSE_KEY, {})
    if 'access_token' not in oauth_response:
        raise OAuthSessionExpired(
            'access_token not found in oauth_response, possibly because '
            "the user didn't do an OAuth Login yet"
        )

    # If token hasn't expired yet, return it
    expires_at = oauth_response.get('expires_at')
    # TODO: RFC-6749 specifies "expires_in", not "expires_at".
    #       https://www.rfc-editor.org/rfc/rfc6749#section-5.1
    if expires_at is None or expires_at > int(time.time()):
        return oauth_response

    # If the token has expired, get a new token using refresh_token
    refresh_token = oauth_response.get('refresh_token')
    if not refresh_token:
        raise OAuthSessionExpired(
            'access_token is expired but a refresh_token is not found in oauth_response'
        )
    refresh_response = refresh_and_fetch_token(refresh_token)
    superset.appbuilder.sm.set_oauth_session('commcare', refresh_response)
    return refresh_response


def refresh_and_fetch_token(refresh_token):
    try:
        provider = superset.appbuilder.sm.oauth_remotes['commcare']
        refresh_response = provider._get_oauth_client().refresh_token(
            provider.access_token_url, refresh_token=refresh_token
        )
        return refresh_response
    except HTTPError:
        # If the refresh token too expired raise exception.
        raise OAuthSessionExpired(
            'OAuth refresh token has expired. User need to re-authorize the OAuth Application'
        )
