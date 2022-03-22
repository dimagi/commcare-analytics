from flask import url_for
from flask_appbuilder import expose
import superset


def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)


class SupersetKetchupApiView(superset.views.base.BaseSupersetView):

    """
    Extensions to Superset API
    """

    def __init__(self):
        self.route_base = "/hq-superset"
        super().__init__()

    @superset.views.base.api
    @expose('/version/', methods=['GET'])
    def version(self):
        links = []
        for rule in superset.app.url_map.iter_rules():
                # Filter out rules we can't navigate to in a browser
                # and rules that require parameters
                if "GET" in rule.methods and has_no_empty_params(rule):
                    url = url_for(rule.endpoint, **(rule.defaults or {}), _external=True)
                    links.append((url, rule.endpoint))
        return self.json_response(
            {'version': 1, 'links': links})
