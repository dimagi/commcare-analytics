import jinja2, os
from flask import request, g, flash, redirect, url_for

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
	my_loader = jinja2.ChoiceLoader([
	        jinja2.FileSystemLoader([os.path.dirname(os.path.abspath(__file__)) + '/templates']),
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
