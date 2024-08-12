# -*- coding: utf-8 -*-
"""
Base TestCase class
"""

import os
import shutil

from flask_testing import TestCase
from sqlalchemy.sql import text
from superset.app import create_app

from hq_superset.utils import DOMAIN_PREFIX, get_hq_database

from .utils import setup_hq_db

superset_test_home = os.path.join(os.path.dirname(__file__), '.test_superset')
shutil.rmtree(superset_test_home, ignore_errors=True)
os.environ['SUPERSET_HOME'] = superset_test_home
os.environ['SUPERSET_CONFIG_PATH'] = 'hq_superset/tests/config_for_tests.py'
test_app = create_app()


class SupersetTestCase(TestCase):
    """The base TestCase class for all tests relying on Flask app context"""

    def create_app(self):
        return test_app

    def setUp(self):
        import superset

        superset.db.create_all()


class HQDBTestCase(SupersetTestCase):
    def setUp(self):
        super(HQDBTestCase, self).setUp()
        setup_hq_db()
        self.hq_db = get_hq_database()

    def tearDown(self):
        # Drop HQ DB Schemas
        with self.hq_db.get_sqla_engine_with_context() as engine:
            with engine.connect() as connection:
                results = connection.execute(
                    text('SELECT schema_name FROM information_schema.schemata')
                )
                domain_schemas = []
                for (schema,) in results.fetchall():
                    if schema.startswith(DOMAIN_PREFIX):
                        domain_schemas.append(
                            f'DROP SCHEMA IF EXISTS "{schema}" CASCADE; COMMIT;'
                        )
                if domain_schemas:
                    sql = '; '.join(domain_schemas) + ';'
                    connection.execute(text(sql))
        super(HQDBTestCase, self).tearDown()
