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

    def create_custom_role_perms(self, domains):
        for domain_name in domains.items():
            role_created = self.create_custom_role(domain_name)
            if not role_created:
                continue
            self.create_schema(domain_name)
            pv = self.create_custom_permission(domain_name)
            sesh = self.get_session
            role_created.permissions = pv
            sesh.merge(role_created)
            sesh.commit()

    def create_custom_permission(self, domain_name):
        schema_access_perm_name = "schema_access"
        schema_access_view_menu_name = "[{}].[{}]".format("superset", domain_name)
        return self.add_permission_view_menu(schema_access_perm_name, schema_access_view_menu_name)

    def create_custom_role(self, role_name):
        is_role_present = self.find_role(role_name)
        if is_role_present:
            logging.debug("Role {} already exists".format(role_name))
            return
        logging.info("Creating role {}".format(role_name))
        return self.add_role(role_name)

    def create_schema(self, schema_name):
        # TODO: use schema creation util, diff. PR for it
        pass

