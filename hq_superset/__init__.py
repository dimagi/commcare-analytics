import os

import jinja2
from flask import Blueprint


def flask_app_mutator(app):
    # Import the views (which assumes the app is initialized) here
    # return
    from superset.extensions import appbuilder

    from . import api, hq_domain, views

    appbuilder.add_view(
        views.HQDatasourceView,
        'Update HQ Datasource',
        menu_cond=lambda *_: False,
    )
    appbuilder.add_view(
        views.SelectDomainView, 'Select a Domain', menu_cond=lambda *_: False
    )
    appbuilder.add_api(api.OAuth)
    appbuilder.add_api(api.DataSetChangeAPI)
    app.before_request_funcs.setdefault(None, []).append(
        hq_domain.before_request_hook
    )
    app.after_request_funcs.setdefault(None, []).append(
        hq_domain.after_request_hook
    )
    app.strict_slashes = False
    override_jinja2_template_loader(app)


def override_jinja2_template_loader(app):
    # Allow loading templates from the templates directory in this project as well

    template_path = os.sep.join(
        (os.path.dirname(os.path.abspath(__file__)), 'templates')
    )
    my_loader = jinja2.ChoiceLoader(
        [
            jinja2.FileSystemLoader([template_path]),
            app.jinja_loader,
        ]
    )
    app.jinja_loader = my_loader

    images_path = os.sep.join(
        (os.path.dirname(os.path.abspath(__file__)), 'images')
    )
    blueprint = Blueprint(
        'Static',
        __name__,
        static_url_path='/static/images',
        static_folder=images_path,
    )
    app.register_blueprint(blueprint)
