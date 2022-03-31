import psycopg2

from hq_superset.service.db.db_manager import DbManager


class PostgresDbManager(DbManager):

    CREATE_SCHEMA_TEMPLATE = "CREATE SCHEMA IF NOT EXISTS {schema};"

    def connect(self):
        connection = psycopg2.connect(host=self.db_info.db_host,
                                      port=self.db_info.db_port,
                                      database=self.db_info.database_name,
                                      user=self.db_info.db_user,
                                      password=self.db_info.db_password
                                      )
        return connection

    def schema_exists(self, schema_name: str) -> bool:
        # Usage during explicit schema check
        raise NotImplementedError

    def create_schema(self, schema_name: str) -> bool:
        with self.connect() as conn:
            with conn.cursor() as cursor:
                return bool(cursor.execute(PostgresDbManager.CREATE_SCHEMA_TEMPLATE.format(schema=schema_name)))
