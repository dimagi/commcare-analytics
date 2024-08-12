import doctest

from hq_superset.utils import get_column_dtypes

from .utils import TEST_DATASOURCE


def test_get_column_dtypes():
    datasource_defn = TEST_DATASOURCE
    column_dtypes, date_columns, _ = get_column_dtypes(datasource_defn)
    assert column_dtypes == {
        'doc_id': 'string',
        'data_visit_comment_fb984fda': 'string',
        'data_visit_number_33d63739': 'Int64',
    }
    assert set(date_columns) == {
        'inserted_at',
        'data_lmp_date_5e24b993',
        'data_visit_date_eaece89e',
    }


def test_doctests():
    import hq_superset.utils

    results = doctest.testmod(hq_superset.utils)
    assert results.failed == 0
