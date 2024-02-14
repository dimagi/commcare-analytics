from functools import wraps

from hq_superset.utils import (
    HQ_DB_CONNECTION_NAME,
    CCHQApiException,
    get_hq_database,
)


class UnitTestingRequired(Exception):
    pass


def unit_testing_only(fn):
    import superset

    @wraps(fn)
    def inner(*args, **kwargs):
        if not superset.app.config.get('TESTING'):
            raise UnitTestingRequired(
                'You may only call {} during unit testing'.format(fn.__name__)
            )
        return fn(*args, **kwargs)

    return inner


@unit_testing_only
def setup_hq_db():
    import superset
    from superset.commands.database.create import CreateDatabaseCommand

    try:
        get_hq_database()
    except CCHQApiException:
        CreateDatabaseCommand(
            {
                'sqlalchemy_uri': superset.app.config.get('HQ_DATA_DB'),
                'engine': 'PostgreSQL',
                'database_name': HQ_DB_CONNECTION_NAME,
            }
        ).run()


TEST_DATASOURCE = {
    'configured_filter': {
        'filters': [
            {
                'comment': None,
                'expression': {
                    'datatype': None,
                    'property_name': 'xmlns',
                    'type': 'property_name',
                },
                'operator': 'eq',
                'property_value': 'http://openrosa.org/formdesigner/B7F9A7EA-E310-4673-B7DA-423BE63A34AA',
                'type': 'boolean_expression',
            },
            {
                'comment': None,
                'expression': {
                    'datatype': None,
                    'property_name': 'app_id',
                    'type': 'property_name',
                },
                'operator': 'eq',
                'property_value': '2cb1a465c85644b8a21756c450c3e886',
                'type': 'boolean_expression',
            },
        ],
        'type': 'and',
    },
    'configured_indicators': [
        {
            'column_id': 'data_visit_date_eaece89e',
            'comment': None,
            'create_index': False,
            'datatype': 'date',
            'display_name': 'visit_date',
            'expression': {
                'datatype': None,
                'property_path': ['form', 'visit_date'],
                'type': 'property_path',
            },
            'is_Noneable': True,
            'is_primary_key': False,
            'transform': {},
            'type': 'expression',
        },
        {
            'column_id': 'data_visit_number_33d63739',
            'comment': None,
            'create_index': False,
            'datatype': 'integer',
            'display_name': 'visit_number',
            'expression': {
                'datatype': None,
                'property_path': ['form', 'visit_number'],
                'type': 'property_path',
            },
            'is_Noneable': True,
            'is_primary_key': False,
            'transform': {},
            'type': 'expression',
        },
        {
            'column_id': 'data_lmp_date_5e24b993',
            'comment': None,
            'create_index': False,
            'datatype': 'date',
            'display_name': 'lmp_date',
            'expression': {
                'datatype': None,
                'property_path': ['form', 'lmp_date'],
                'type': 'property_path',
            },
            'is_Noneable': True,
            'is_primary_key': False,
            'transform': {},
            'type': 'expression',
        },
        {
            'column_id': 'data_visit_comment_fb984fda',
            'comment': None,
            'create_index': False,
            'datatype': 'string',
            'display_name': 'visit_comment',
            'expression': {
                'datatype': None,
                'property_path': ['form', 'visit_comment'],
                'type': 'property_path',
            },
            'is_Noneable': True,
            'is_primary_key': False,
            'transform': {},
            'type': 'expression',
        },
    ],
    'display_name': 'ANC visit (v3) 2020-12-16 04:49:22',
    'id': 'test1_ucr1',
    'resource_uri': '/a/demo/api/v0.5/ucr_data_source/52a134da12c9b801bd85d2122901b30c/',
}

TEST_UCR_CSV = """\
doc_id,inserted_at,data_visit_date_eaece89e,data_visit_number_33d63739,data_lmp_date_5e24b993,data_visit_comment_fb984fda
a1, 2021-12-20, 2022-01-19, 100, 2022-02-20, some_text
a2, 2021-12-22, 2022-02-19, 10, 2022-03-20, some_other_text
"""
