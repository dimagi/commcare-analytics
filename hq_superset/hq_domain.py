from datetime import timedelta

import superset
from flask import flash, g, redirect, request, session, url_for
from superset.config import USER_DOMAIN_ROLE_EXPIRY

from hq_superset.const import (
    SESSION_DOMAIN_ROLE_LAST_SYNCED_AT,
    SESSION_USER_DOMAINS_KEY,
)
from hq_superset.utils import DomainSyncUtil, datetime_utcnow


def before_request_hook():
    """
    Call all hooks functions set in sequence and
    if any hook returns a response,
    break the chain and return that response
    """
    hooks = [
        ensure_domain_selected,
        sync_user_domain_role
    ]
    for _function in hooks:
        response = _function()
        if response:
            return response


def after_request_hook(response):
    # On logout clear domain cookie
    logout_views = [
        "AuthDBView.login",
        "AuthOAuthView.logout",
    ]
    if request.url_rule and (request.url_rule.endpoint in logout_views):
        response.set_cookie('hq_domain', '', expires=0)
    return response


DOMAIN_EXCLUDED_VIEWS = [
    'AuthDBView.login',
    'AuthDBView.logout',
    'AuthOAuthView.login',
    'AuthOAuthView.logout',
    'AuthOAuthView.oauth_authorized',
    'CurrentUserRestApi.get_me',
    'DataSetChangeAPI.post_dataset_change',
    'OAuth.issue_access_token',
    'SelectDomainView.list',
    'SelectDomainView.select',
    'appbuilder.static',
    'static',
]


def is_user_admin():
    from superset import security_manager
    return security_manager.is_admin()


def ensure_domain_selected():
    # Check if a hq_domain cookie is set
    #   Ensure necessary roles, permissions and DB schemas are created for the domain
    if is_user_admin() or (
        request.url_rule
        and request.url_rule.endpoint in DOMAIN_EXCLUDED_VIEWS
    ):
        return
    hq_domain = request.cookies.get('hq_domain')
    valid_domains = user_domains()
    if is_valid_user_domain(hq_domain):
        g.hq_domain = hq_domain
    else:
        flash('Please select a domain to access this page.', 'warning')
        return redirect(url_for('SelectDomainView.list', next=request.url))


def sync_user_domain_role():
    if is_user_admin() or (
        request.url_rule
        and request.url_rule.endpoint in DOMAIN_EXCLUDED_VIEWS
    ):
        return
    if _domain_role_expired():
        _sync_domain_role()


def _domain_role_expired():
    if not session.get(SESSION_DOMAIN_ROLE_LAST_SYNCED_AT):
        return True

    time_since_last_sync = datetime_utcnow() - session[SESSION_DOMAIN_ROLE_LAST_SYNCED_AT]
    return time_since_last_sync >= timedelta(minutes=USER_DOMAIN_ROLE_EXPIRY)


def _sync_domain_role():
    DomainSyncUtil(superset.appbuilder.sm).sync_domain_role(g.hq_domain)


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
    for domain in domains:
        superset.appbuilder.menu.add_link(domain, category=active_domain, href=url_for('SelectDomainView.select', hq_domain=domain))

