import doctest
import json

from hq_superset.utils import get_column_dtypes


def test_get_column_dtypes():
    datasource_defn = json.loads(datasource_defn_str)
    column_dtypes, date_columns, _ = get_column_dtypes(datasource_defn)
    assert column_dtypes == {
        'doc_id': 'string',
        'data_visit_comment_fb984fda': 'string',
        'data_visit_number_33d63739': 'Int64'
    }
    assert set(date_columns) == {
        'inserted_at',
        'data_lmp_date_5e24b993',
        'data_visit_date_eaece89e'
    }


def test_doctests():
    import hq_superset.utils
    results = doctest.testmod(hq_superset.utils)
    assert results.failed == 0


datasource_defn_str = """{
  "configured_filter": {
    "filters": [
      {
        "comment": null,
        "expression": {
          "datatype": null,
          "property_name": "xmlns",
          "type": "property_name"
        },
        "operator": "eq",
        "property_value": "http://openrosa.org/formdesigner/B7F9A7EA-E310-4673-B7DA-423BE63A34AA",
        "type": "boolean_expression"
      },
      {
        "comment": null,
        "expression": {
          "datatype": null,
          "property_name": "app_id",
          "type": "property_name"
        },
        "operator": "eq",
        "property_value": "2cb1a465c85644b8a21756c450c3e886",
        "type": "boolean_expression"
      }
    ],
    "type": "and"
  },
  "configured_indicators": [
    {
      "column_id": "data_visit_date_eaece89e",
      "comment": null,
      "create_index": false,
      "datatype": "date",
      "display_name": "visit_date",
      "expression": {
        "datatype": null,
        "property_path": [
          "form",
          "visit_date"
        ],
        "type": "property_path"
      },
      "is_nullable": true,
      "is_primary_key": false,
      "transform": {},
      "type": "expression"
    },
    {
      "column_id": "data_visit_number_33d63739",
      "comment": null,
      "create_index": false,
      "datatype": "integer",
      "display_name": "visit_number",
      "expression": {
        "datatype": null,
        "property_path": [
          "form",
          "visit_number"
        ],
        "type": "property_path"
      },
      "is_nullable": true,
      "is_primary_key": false,
      "transform": {},
      "type": "expression"
    },
    {
      "column_id": "data_lmp_date_5e24b993",
      "comment": null,
      "create_index": false,
      "datatype": "date",
      "display_name": "lmp_date",
      "expression": {
        "datatype": null,
        "property_path": [
          "form",
          "lmp_date"
        ],
        "type": "property_path"
      },
      "is_nullable": true,
      "is_primary_key": false,
      "transform": {},
      "type": "expression"
    },
    {
      "column_id": "data_visit_comment_fb984fda",
      "comment": null,
      "create_index": false,
      "datatype": "string",
      "display_name": "visit_comment",
      "expression": {
        "datatype": null,
        "property_path": [
          "form",
          "visit_comment"
        ],
        "type": "property_path"
      },
      "is_nullable": true,
      "is_primary_key": false,
      "transform": {},
      "type": "expression"
    }
  ],
  "display_name": "ANC visit (v3) 2020-12-16 04:49:22",
  "id": "52a134da12c9b801bd85d2122901b30c",
  "resource_uri": "/a/demo/api/v0.5/ucr_data_source/52a134da12c9b801bd85d2122901b30c/"
}"""