from flask import Blueprint, g, redirect
from superset.initialization import SupersetAppInitializer
from flask_appbuilder import BaseView

def add_ketchup(config):
    config.FLASK_APP_MUTATOR = flask_app_mutator
    # patch_create_blueprint()

def flask_app_mutator(app):
    # Import the views (which assumes the app is initialized) here
    # return
    import superset
    from . import views
    from . import blueprint

    blueprint.bp.add_url_rule('/awelcome', view_func=superset.views.core.Superset.welcome)
    blueprint.bp.static_url_path = app.static_url_path
    blueprint.bp.static_folder = app.static_folder
    app.register_blueprint(blueprint.bp)
    superset.appbuilder.add_view_no_menu(views.SupersetKetchupApiView)

def patch_create_blueprint():
    original = BaseView.create_blueprint

    def patched_blueprint(self, appbuilder, endpoint=None, static_folder=None):
        bp = original(self, appbuilder, endpoint=endpoint, static_folder=static_folder)
        bp.url_prefix = '/a/<lang_code>' + bp.url_prefix

        @bp.url_defaults
        def add_language_code(endpoint, values):
            values.setdefault('lang_code', g.lang_code)

        @bp.url_value_preprocessor
        def pull_lang_code(endpoint, values):
            g.lang_code = values.pop('lang_code')

        return bp

    BaseView.create_blueprint = patched_blueprint

class HQSupersetInitializer(SupersetAppInitializer):

    def post_init(self):
        # import pdb; pdb.set_trace()
        super().post_init()
