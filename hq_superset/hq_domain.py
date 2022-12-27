from flask import flash, g, redirect, request, session, url_for
from superset.views.base import is_user_admin

from .utils import SESSION_USER_DOMAINS_KEY


def before_request_hook():
    return ensure_domain_selected()

def after_request_hook(response):
    # On logout clear domain cookie
    if (request.url_rule and request.url_rule.endpoint == "AuthOAuthView.logout"):
        response.set_cookie('hq_domain', '', expires=0)
    return response

DOMAIN_EXCLUDED_VIEWS = [
    "AuthOAuthView.login",
    "AuthOAuthView.logout",
    "AuthOAuthView.oauth_authorized",
    "AuthDBView.logout",
    "AuthDBView.login",
    "SelectDomainView.list",
    "SelectDomainView.select",
    "appbuilder.static",
    "static",
]

def ensure_domain_selected():
    # Check if a hq_domain cookie is set
    #   Ensure necessary roles, permissions and DB schemas are created for the domain
    if is_user_admin() or (request.url_rule and request.url_rule.endpoint in DOMAIN_EXCLUDED_VIEWS):
        return
    hq_domain = request.cookies.get('hq_domain')
    valid_domains = user_domains()
    if is_valid_user_domain(hq_domain):
        g.hq_domain = hq_domain
    else:
        flash('Please select a domain to access this page.', 'warning')
        return redirect(url_for('SelectDomainView.list', next=request.url))


def is_valid_user_domain(hq_domain):
    # Admins have access to all domains
    return is_user_admin() or hq_domain in user_domains()


def user_domains():
    # This should be set by oauth_user_info after OAuth
    if is_user_admin() or SESSION_USER_DOMAINS_KEY not in session:
        return []
    return [
        d["domain_name"]
        for d in session[SESSION_USER_DOMAINS_KEY]
    ]


def add_domain_links(active_domain, domains):
    import superset
    for domain in domains:
        superset.appbuilder.menu.add_link(domain, category=active_domain, href=url_for('SelectDomainView.select', hq_domain=domain))


class DomainSyncUtil:

    def __init__(self, security_manager):
        self.sm = security_manager

    def _ensure_domain_role_created(self, domain):
        # This inbuilt method creates only if the role doesn't exist.
        return self.sm.add_role(get_role_name_for_domain(domain))

    def _ensure_schema_perm_created(self, domain):
        menu_name = self.sm.get_schema_perm(get_ucr_database(), get_schema_name_for_domain(domain))
        permission = self.sm.find_permission_view_menu("schema_access", menu_name)
        if not permission:
            permission = self.sm.add_permission_view_menu("schema_access", menu_name)
        return permission

    def _ensure_schema_created(self, domain):
        create_schema_if_not_exists(domain)

    def sync_domain_role(self, domain):
        from superset_config import AUTH_USER_ADDITIONAL_ROLES
        # This creates DB schema, role and schema permissions for the domain and
        #   assigns the role to the current_user
        self.sm._ensure_schema_created(domain)
        permission = self.sm._ensure_schema_perm_created(domain)
        role = self.sm._ensure_domain_role_created(domain)
        self.sm.add_permission_role(role, permission)
        # Filter out other domain roles
        filtered_roles = [
            r
            for r in current_user.roles
            if not r.name.startswith(DOMAIN_PREFIX)
        ]
        additional_roles = [
            self.sm.add_role(r)
            for r in AUTH_USER_ADDITIONAL_ROLES
        ]
        # Add the domain's role
        current_user.roles = filtered_roles + [role] + additional_roles
        self.sm.get_session.add(current_user)
        self.sm.get_session.commit()
