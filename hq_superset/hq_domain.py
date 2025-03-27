from datetime import timedelta
import json

import superset
from flask import current_app, flash, g, redirect, request, session, url_for
from flask_login import logout_user
from superset.config import USER_DOMAIN_ROLE_EXPIRY
from superset.extensions import cache_manager

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
    response = error_check_after_request(response)
    return response


def oauth_session_expired(*arg, **kwargs):
    logout_user()
    flash(
        f"Your session has expired. Please log in again.",
        'warning',
    )
    return redirect(url_for("AuthOAuthView.login"))


def error_check_after_request(response_obj):
    """
    This gets used by the Flask app's after_request hook to check for
    endpoints that return false-positive 500 errors and change them to
    a more appropriate 400 error.
    """
    def should_update_status_code_for_errors(response):
        VALID_ERROR_TYPES = [
            'COLUMN_DOES_NOT_EXIST_ERROR',
            'GENERIC_DB_ENGINE_ERROR',
        ]
        response_dict = json.loads(response.decode('utf-8'))
        try:
            for error in response_dict['errors']:
                if error['error_type'] in VALID_ERROR_TYPES:
                    return True
        except KeyError:
            pass
        return False

    if (
        request.path.startswith("/api/v1/sqllab/execute/")
        and response_obj.status_code == 500
        and should_update_status_code_for_errors(response_obj.response[0])
    ):
        response_obj.status_code = 400
    return response_obj


DOMAIN_EXCLUDED_VIEWS = [
    'AuthDBView.login',
    'AuthDBView.logout',
    'AuthOAuthView.login',
    'AuthOAuthView.logout',
    'AuthOAuthView.oauth_authorized',
    'CurrentUserRestApi.get_me',
    'Superset.log',
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
        # only sync if another sync not in progress
        if not _sync_in_progress():
            return _perform_sync_domain_role()


def _domain_role_expired():
    if not session.get(SESSION_DOMAIN_ROLE_LAST_SYNCED_AT):
        return True

    time_since_last_sync = datetime_utcnow() - session[SESSION_DOMAIN_ROLE_LAST_SYNCED_AT]
    return time_since_last_sync >= timedelta(minutes=USER_DOMAIN_ROLE_EXPIRY)


def _sync_in_progress():
    return cache_manager.cache.get(_sync_domain_role_cache_key())


def _sync_domain_role_cache_key():
    return f"{g.user.id}_{g.hq_domain}_sync_domain_role"


def _perform_sync_domain_role():
    cache_key = _sync_domain_role_cache_key()

    # set cache for 30 seconds
    cache_manager.cache.set(cache_key, True, timeout=30)
    sync_domain_role_response = _sync_domain_role()
    cache_manager.cache.delete(cache_key)

    return sync_domain_role_response

def _sync_domain_role():
    if not DomainSyncUtil(superset.appbuilder.sm).sync_domain_role(g.hq_domain):
        error_message = (
            f"Either your permissions for the project '{g.hq_domain}' were revoked or "
            "your permissions failed to refresh. "
            "Please select the project space again or login again to resolve. "
            "If issue persists, please submit a support request."
        )
        return current_app.response_class(
            response=error_message,
            status=400,
        )


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

