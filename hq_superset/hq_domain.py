import os

import jinja2

from flask import flash, g, redirect, request, url_for, session
from flask_login import current_user
from superset.views.base import is_user_admin
from .utils import SESSION_USER_DOMAINS_KEY

def before_request_hook():
    override_jinja2_template_loader()
    return ensure_domain_selected()


def override_jinja2_template_loader():
    # Allow loading templates from the templates directory in this project as well
    from superset import app

    template_path = os.sep.join((
        os.path.dirname(os.path.abspath(__file__)),
        'templates'
    ))
    my_loader = jinja2.ChoiceLoader([
            jinja2.FileSystemLoader([template_path]),
            app.jinja_loader,
        ])
    app.jinja_loader = my_loader


DOMAIN_EXCLUDED_VIEWS = [
    "AuthOAuthView.login",
    "AuthOAuthView.logout",
    "AuthOAuthView.oauth_authorized",
    "AuthDBView.logout",
    "AuthDBView.login",
    "SelectDomainView.list",
    "appbuilder.static",
    "static",
]

def ensure_domain_selected():
    # Check if a hq_domain cookie is set
    #   Ensure necessary roles, permissions and DB schemas are created for the domain
    import superset
    if is_user_admin() or (request.url_rule and request.url_rule.endpoint in DOMAIN_EXCLUDED_VIEWS):
        return
    hq_domain = request.cookies.get('hq_domain')
    valid_domains = user_domains(current_user)
    if is_valid_user_domain(hq_domain):
        g.hq_domain = hq_domain
    elif len(valid_domains) == 1:
        g.hq_domain = valid_domains[0]
    else:
        flash('You need to select a domain to access this page', 'error')
        return redirect(url_for('SelectDomainView.list', next=request.url))


def is_valid_user_domain(hq_domain):
    # Admins have access to all domains
    return is_user_admin() or hq_domain in user_domains(current_user)


def user_domains(user):
    # This should be set by oauth_user_info after OAuth
    if is_user_admin() or SESSION_USER_DOMAINS_KEY not in session:
        return []
    return [
        d["domain_name"]
        for d in session[SESSION_USER_DOMAINS_KEY]["objects"]
    ]


def add_domain_links(active_domain, domains):
    import superset
    for domain in domains:
        superset.appbuilder.menu.add_link(domain, category=active_domain, href=url_for('SelectDomainView.select', hq_domain=domain))
