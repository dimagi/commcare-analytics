from flask import flash, g, redirect, request, session, url_for

from .utils import SESSION_USER_DOMAINS_KEY


def before_request_hook():
    return ensure_domain_selected()


def after_request_hook(response):
    # On logout clear domain cookie
    logout_views = [
        'AuthDBView.login',
        'AuthOAuthView.logout',
    ]
    if request.url_rule and request.url_rule.endpoint in logout_views:
        response.set_cookie('hq_domain', '', expires=0)
    return response


DOMAIN_EXCLUDED_VIEWS = [
    'AuthOAuthView.login',
    'AuthOAuthView.logout',
    'AuthOAuthView.oauth_authorized',
    'AuthDBView.logout',
    'AuthDBView.login',
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
        request.url_rule and request.url_rule.endpoint in DOMAIN_EXCLUDED_VIEWS
    ):
        return
    hq_domain = request.cookies.get('hq_domain')
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
    return [d['domain_name'] for d in session[SESSION_USER_DOMAINS_KEY]]


def add_domain_links(active_domain, domains):
    import superset

    for domain in domains:
        superset.appbuilder.menu.add_link(
            domain,
            category=active_domain,
            href=url_for('SelectDomainView.select', hq_domain=domain),
        )
