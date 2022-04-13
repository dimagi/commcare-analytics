from flask import redirect, request
from flask_appbuilder import BaseView, expose
from flask_appbuilder.security.decorators import has_access, permission_name
from flask_login import current_user
from superset.typing import FlaskResponse

from . import hq_domain


class SelectDomainView(BaseView):

    """
    Select a Domain view, all roles that have 'profile' access on 'core.Superset' view can access this
    """
    # re-use core.Superset view's permission name
    class_permission_name = "Superset"

    def __init__(self):
        self.route_base = "/domain"
        super().__init__()

    @has_access
    @permission_name("profile")
    @expose('/list/', methods=['GET'])
    def list(self):
        return self.render_template(
            'select_domain.html',
            next=request.args.get('next'),
            domains=hq_domain.user_domains(current_user)
        )

    @has_access
    @permission_name("profile")
    @expose('/select/<hq_domain>', methods=['GET'])
    def select(self, hq_domain):
        import pdb; pdb.set_trace()
        response = redirect(request.args.get('next') or self.appbuilder.get_url_for_index)
        # Todo validate domain permission
        response.set_cookie('hq_domain', hq_domain)
        return response


class HQDataSourceConfigView(BaseView):
    # TODO: Extend SupersetModelView instead
    # datamodel = SQLAInterface(HQDataSourceConfigModel)
    # TODO: On login, pull data sources and cache them in a Model.

    route_base = '/hq_data_source'
    class_permission_name = 'Superset'

    @has_access
    @expose('/list/', methods=['GET'])
    @permission_name("profile")  # TODO: What is this for?
    def list(self) -> FlaskResponse:
        # return super().render_app_template()

        # domain = 'demo'
        # data_source_configs = fetch_data_source_configs(domain)

        data_source_configs = ['foo', 'bar', 'baz']
        return self.render_template(
            'hq_data_source_config_list.html',
            data_source_configs=data_source_configs,
        )
