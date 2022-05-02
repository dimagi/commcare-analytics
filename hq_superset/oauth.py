import logging
import superset
import time
from flask import session
from requests.exceptions import HTTPError
from superset.security import SupersetSecurityManager

class CommCareSecurityManager(SupersetSecurityManager):

    def oauth_user_info(self, provider, response=None):
        logging.debug("Oauth2 provider: {0}.".format(provider))
        if provider == 'commcare':
            logging.debug("Getting user info from {}".format(provider))
            user = self.appbuilder.sm.oauth_remotes[provider].get("api/v0.5/identity/", token=response).json()
            domains = self.appbuilder.sm.oauth_remotes[provider].get("api/v0.5/user_domains/", token=response).json()
            session["user_hq_domains"] = domains
            logging.debug("user - {}".format(user))
            return user

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
        session["oauth_response"] = oauth_response


class OAuthSessionExpired(Exception):
    pass


def get_valid_cchq_oauth_token():
    # Returns a valid working oauth access_token
    #   May raise `OAuthSessionExpired`, if a valid working token is not found
    #   The user needs to re-auth using CommCareHQ to get valid tokens
    oauth_response = session["oauth_response"]
    if "access_token" not in oauth_response:
        raise OAuthSessionExpired(
            "access_token not found in oauth_response, possibly because "
            "the user didn't do an OAuth Login yet"
        )

    # If token hasn't expired yet, return it
    expires_at = oauth_response.get("expires_at")
    if expires_at > int(time.time()):
        return oauth_response
    provider = superset.appbuilder.sm.oauth_remotes["commcare"]

    # If the token has expired, get a new token using refresh_token
    refresh_token = oauth_response.get("refresh_token")
    if not refresh_token:
        raise OAuthSessionExpired(
            "access_token is expired but a refresh_token is not found in oauth_response"
        )
    try:
        refresh_response = provider._get_oauth_client().refresh_token(
            provider.access_token_url,
            refresh_token=refresh_token
        )
        superset.appbuilder.sm.set_oauth_session(provider, refresh_response)
        return refresh_response
    except HTTPError:
        # If the refresh token too expired raise exception.
        raise OAuthSessionExpired(
            "OAuth refresh token has expired. User need to re-authorize the OAuth Application"
        )
