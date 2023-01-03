# -*- coding: utf-8 -*-
"""
Base TestCase class
"""

import os
import shutil

from sqlalchemy.sql import text
from flask_appbuilder import SQLA
from flask_testing import TestCase
from superset.app import create_app
from hq_superset.utils import get_hq_database, DOMAIN_PREFIX

superset_test_home = os.path.join(os.path.dirname(__file__), ".test_superset")
shutil.rmtree(superset_test_home, ignore_errors=True)
os.environ["SUPERSET_HOME"] = superset_test_home
os.environ["SUPERSET_CONFIG"] = "hq_superset.tests.config_for_tests.superset_config"
app = create_app()


class SupersetTestCase(TestCase):
    """The base TestCase class for all tests relying on Flask app context"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.maxDiff = None
        self.db = SQLA()

    def create_app(self):
        return app

    def setUp(self):
        self.db.create_all()


class HQDBTestCase(SupersetTestCase):

    def setUp(self):
        super(HQDBTestCase, self).setUp()
        self.hq_db = get_hq_database()

    def tearDown(self):
        engine = self.hq_db.get_sqla_engine()
        with engine.connect() as connection:
            results = connection.execute(text("SELECT schema_name FROM information_schema.schemata"))
            domain_schemas = []
            for schema, in results.fetchall():
                if schema.startswith(DOMAIN_PREFIX):
                    domain_schemas.append(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE; COMMIT;')
            if domain_schemas:
                sql = "; ".join(domain_schemas) + ";"
                connection.execute(text(sql))
        super(HQDBTestCase, self).tearDown()
