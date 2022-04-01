from flask import url_for, render_template, redirect, request
from flask_appbuilder import expose, BaseView
from flask_appbuilder.security.decorators import has_access, permission_name
from flask_login import current_user
import superset
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
