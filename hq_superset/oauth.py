import logging
from superset.security import SupersetSecurityManager

class CommCareSecurityManager(SupersetSecurityManager):

    def oauth_user_info(self, provider, response=None):
        logging.debug("Oauth2 provider: {0}.".format(provider))
        if provider == 'commcare':
            logging.debug("Getting user info from {}".format(provider))
            user = self.appbuilder.sm.oauth_remotes[provider].get("api/v0.5/identity/", token=response).json()
            logging.debug("user - {}".format(user))
            return user
