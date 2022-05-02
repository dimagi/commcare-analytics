import sqlalchemy

def get_datasource_export_url(domain, datasource_id):
    return f"a/{domain}/configurable_reports/data_sources/export/{datasource_id}?format=csv"


def get_ucr_database():
    # Todo; get actual DB once that's implemented
    return db.session.query(Database).filter_by(database_name="HQ Data").one()


def create_schema_if_not_exists(schema_name):
    # Create a schema in the database where HQ's UCR data is stored
    database = get_ucr_database()
    engine = database.get_sqla_engine()
    if not engine.dialect.has_schema(engine, schema_name):
        engine.execute(sqlalchemy.schema.CreateSchema(schema_name))
