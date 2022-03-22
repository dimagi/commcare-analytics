from flask import Blueprint, g, redirect
from flask import url_for, request

import superset


bp = Blueprint('some', __name__, url_prefix='/a/<lang_code>')

@bp.url_defaults
def add_language_code(endpoint, values):
    values.setdefault('lang_code', g.lang_code)

@bp.url_value_preprocessor
def pull_lang_code(endpoint, values):
    g.lang_code = values.pop('lang_code')

@bp.route('/about')
def about():
    print("asdasdasdasdasdsd")
    print(g.lang_code)
    return superset.app.view_functions['Superset.welcome'](**request.view_args)
    # return 'welcome'
    return redirect(url_for('Superset.welcome'))

@bp.route('/ccharts')
def charts():
    return superset.app.view_functions['SliceModelView.list'](**request.view_args)

