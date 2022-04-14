import os
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urljoin

import jinja2
import requests
from sqlalchemy.orm import Session

from flask import flash, g, redirect, request, url_for
from superset_config import HQ_BASE_URL

from .models import HQDataSourceConfigModel
from .schemas import HQDataSourceConfigSchema

DOMAIN_REQUIRED_VIEWS = [
    'TableModelView.list'
]


def before_request_hook():
    # Check URL is one of DOMAIN_REQUIRED_VIEWS
    # Check if a hq_domain cookie is set
    # If not redirect to domain_list view
    _override_jinja2_template_loader()
    _validate_domain()


def _override_jinja2_template_loader():
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


def _validate_domain():
    if not request.url_rule.endpoint in DOMAIN_REQUIRED_VIEWS:
        return
    else:
        hq_domain = request.cookies.get('hq_domain')
        if hq_domain and is_valid_user_domain(hq_domain):
            import pdb; pdb.set_trace()
            g.hq_domain = hq_domain
            # add_domain_links(hq_domain, user_domains('todo'))
        else:
            flash('You need to select a domain to access this page', 'error')
            return redirect(url_for('SelectDomainView.list', next=request.url))


def is_valid_user_domain(hq_domain):
    # Todo; implement based on domains returned from HQ user_info API endpoint
    return True


def user_domains(user):
    # Todo Implement based on persisted user domain membership data
    return ['a', 'b']


def add_domain_links(active_domain, domains):
    import superset
    for domain in domains:
        superset.appbuilder.menu.add_link(domain, category=active_domain, href=url_for('SelectDomainView.select', hq_domain=domain))


# TODO: Import data source configs on login
def import_data_source_configs(
    session: Session,
    hq_domain: str,
) -> None:
    """
    Imports or refreshes an HQ domain's data source configs
    """
    (session.query(HQDataSourceConfigModel)
            .filter(HQDataSourceConfigModel.domain == hq_domain)
            .delete())
    # TODO: Delete after upserting, not before
    for dict_ in fetch_data_source_configs(hq_domain):
        model = HQDataSourceConfigModel(**dict_)
        session.add(model)
    session.commit()


def fetch_data_source_configs(hq_domain: str) -> List[Dict[str, Any]]:
    schema = HQDataSourceConfigSchema()
    retrieved_at = datetime.utcnow()

    # https://www.commcarehq.org/a/[PROJECT]/api/v0.5/ucr_data_source/?format=json -- 404
    url = urljoin(HQ_BASE_URL, f'/a/{hq_domain}/api/v0.5/ucr_data_source/')
    headers = {'Accept': 'application/json'}
    # TODO: Auth
    response = requests.get(url, headers=headers)
    return [
        schema.load({
            'domain': hq_domain,
            'id': item['id'],
            'display_name': item['display_name'],
            'retrieved_at': retrieved_at,
        }) for item in response.json()['objects']
    ]
