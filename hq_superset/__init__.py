import os
import jinja2
import click
from flask import Blueprint


def flask_app_mutator(app):
    # Import the views (which assumes the app is initialized) here
    # return
    from superset.extensions import appbuilder

    from . import api, hq_domain, oauth2_server, views

    appbuilder.add_view(views.HQDatasourceView, 'Update HQ Datasource', menu_cond=lambda *_: False)
    appbuilder.add_view(views.SelectDomainView, 'Select a Domain', menu_cond=lambda *_: False)
    appbuilder.add_api(api.OAuth)
    appbuilder.add_api(api.DataSetChangeAPI)
    oauth2_server.config_oauth2(app)

    app.before_request(hq_domain.before_request_hook)
    app.after_request(hq_domain.after_request_hook)
    app.strict_slashes = False
    override_jinja2_template_loader(app)

    # A proxy (maybe) is changing the URL scheme from "https" to "http"
    # on commcare-analytics-staging.dimagi.com, which breaks the OAuth
    # 2.0 secure transport check despite transport being over HTTPS. I
    # hate to do this, but werkzeug.contrib.fixers.ProxyFix didn't fix
    # it. So I've run out of better options. (Norman 2024-03-13)
    os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'

    register_commands(app)


def override_jinja2_template_loader(app):
    # Allow loading templates from the templates directory in this project as well

    template_path = os.sep.join((
        os.path.dirname(os.path.abspath(__file__)),
        'templates'
    ))
    my_loader = jinja2.ChoiceLoader([
            jinja2.FileSystemLoader([template_path]),
            app.jinja_loader,
        ])
    app.jinja_loader = my_loader

    images_path = os.sep.join((
        os.path.dirname(os.path.abspath(__file__)),
        'images'
    ))
    blueprint = Blueprint('Static', __name__, static_url_path='/static/images', static_folder=images_path)
    app.register_blueprint(blueprint)


def register_commands(app):
    @app.cli.command("subscribe-datasources")
    @click.argument("superset_base_url")
    @click.argument("hq_base_url")
    @click.argument("data_sources_file_path")
    @click.argument("username")
    @click.argument("apikey")
    def subscribe_data_sources(superset_base_url, hq_base_url, data_sources_file_path, username, apikey):
        """
        This command takes all data sources in the data_sources_file_path and subscribe to their changes on HQ.

        Parameters:
            superset_base_url: The base URL of the superset instance. This is used to construct the callback
                URL for publishing the changes to.
            hq_base_url: The base URL of the HQ server containing the data sources you'd like to subscribe to.
            data_sources_file_path: Path to file containing JSON formatted data source IDs by domain,
                e.g. {"domain": ["data_source_id"]}
            username: An HQ superuser username; used for authorization.
            apikey: An HQ superuser api key; used for authorization.
        """
        from hq_superset.commands import subscribe_data_sources
        subscribe_data_sources(superset_base_url, hq_base_url, data_sources_file_path, username, apikey)
