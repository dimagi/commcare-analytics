import logging
import time

import superset
from flask import flash, session
from flask_login import current_user
from requests.exceptions import HTTPError
from superset.security import SupersetSecurityManager

from .utils import (
    DOMAIN_PREFIX,
    SESSION_OAUTH_RESPONSE_KEY,
    SESSION_USER_DOMAINS_KEY,
    create_schema_if_not_exists,
    get_role_name_for_domain,
    get_schema_name_for_domain,
    get_ucr_database,
)

logger = logging.getLogger(__name__)


class CommCareSecurityManager(SupersetSecurityManager):

    def oauth_user_info(self, provider, response=None):
        logger.debug("Oauth2 provider: {0}.".format(provider))
        if provider == 'commcare':
            logger.debug("Getting user info from {}".format(provider))
            user = self._get_hq_response("api/v0.5/identity/", provider, response)
            domains = self._get_hq_response("api/v0.5/user_domains?feature_flag=superset-analytics&can_view_reports=true", provider, response)
            session[SESSION_USER_DOMAINS_KEY] = domains["objects"]
            logger.debug(f"user - {user}, domain - {domains}")
            return user

    def _get_hq_response(self, endpoint, provider, token):
        response = self.appbuilder.sm.oauth_remotes[provider].get(endpoint, token=token)
        if response.status_code != 200:
            url = f"{self.appbuilder.sm.oauth_remotes[provider].api_base_url}{endpoint}"
            message = f"There was an error accessing the CommCareHQ endpoint at {url}"
            logger.exception(message)
            flash(message, "danger")
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

    def ensure_domain_role_created(self, domain):
        # This inbuilt method creates only if the role doesn't exist.
        return self.add_role(get_role_name_for_domain(domain))

    def ensure_schema_perm_created(self, domain):
        menu_name = self.get_schema_perm(get_ucr_database(), get_schema_name_for_domain(domain))
        permission = self.find_permission_view_menu("schema_access", menu_name)
        if not permission:
            permission = self.add_permission_view_menu("schema_access", menu_name)
        return permission

    def ensure_schema_created(self, domain):
        create_schema_if_not_exists(domain)

    def sync_domain_role(self, domain):
        from superset_config import AUTH_USER_ADDITIONAL_ROLES
        # This creates DB schema, role and schema permissions for the domain and
        #   assigns the role to the current_user
        self.ensure_schema_created(domain)
        permission = self.ensure_schema_perm_created(domain)
        role = self.ensure_domain_role_created(domain)
        self.add_permission_role(role, permission)
        # Filter out other domain roles
        filtered_roles = [
            r
            for r in current_user.roles
            if not r.name.startswith(DOMAIN_PREFIX)
        ]
        additional_roles = [
            self.add_role(r)
            for r in AUTH_USER_ADDITIONAL_ROLES
        ]
        # Add the domain's role
        current_user.roles = filtered_roles + [role] + additional_roles
        self.get_session.add(current_user)
        self.get_session.commit()


class OAuthSessionExpired(Exception):
    pass


def get_valid_cchq_oauth_token():
    # Returns a valid working oauth access_token
    #   May raise `OAuthSessionExpired`, if a valid working token is not found
    #   The user needs to re-auth using CommCareHQ to get valid tokens
    oauth_response = session[SESSION_OAUTH_RESPONSE_KEY]
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
        superset.appbuilder.sm.set_oauth_session("commcare", refresh_response)
        return refresh_response
    except HTTPError:
        # If the refresh token too expired raise exception.
        raise OAuthSessionExpired(
            "OAuth refresh token has expired. User need to re-authorize the OAuth Application"
        )
