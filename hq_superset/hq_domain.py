import os

import jinja2

from flask import flash, g, redirect, request, url_for, session
from flask_login import current_user

def before_request_hook():
    override_jinja2_template_loader()
    # Check if a hq_domain cookie is set
    # If not redirect to domain_list view
    return redirect_to_select_domain_view()


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
]

def redirect_to_select_domain_view():
    if request.url_rule.endpoint in DOMAIN_EXCLUDED_VIEWS:
        return
    hq_domain = request.cookies.get('hq_domain')
    valid_domains = user_domains(current_user)
    # Todo; Handle no superset enabled domains case
    if hq_domain in valid_domains:
        g.hq_domain = hq_domain
    elif len(valid_domains) == 1:
        g.hq_domain = valid_domains[0]
    else:
        flash('You need to select a domain to access this page', 'error')
        return redirect(url_for('SelectDomainView.list', next=request.url))


def is_valid_user_domain(hq_domain):
    # Todo; implement based on domains returned from HQ user_info API endpoint
    return True


def user_domains(user):
    # This should be set by oauth_user_info after OAuth
    return [
        d["domain_name"]
        for d in session["user_hq_domains"]["objects"]
    ]


def add_domain_links(active_domain, domains):
    import superset
    for domain in domains:
        superset.appbuilder.menu.add_link(domain, category=active_domain, href=url_for('SelectDomainView.select', hq_domain=domain))
