import sqlalchemy

def get_datasource_export_url(domain, datasource_id):
    return f"a/{domain}/configurable_reports/data_sources/export/{datasource_id}?format=csv"


def get_ucr_database():
    from superset import db
    from superset.models.core import Database
    # Todo; get actual DB once that's implemented
    return db.session.query(Database).filter_by(database_name="HQ Data").one()


def create_schema_if_not_exists(domain):
    # Create a schema in the database where HQ's UCR data is stored
    schema_name = get_schema_name_for_domain(domain)
    database = get_ucr_database()
    engine = database.get_sqla_engine()
    if not engine.dialect.has_schema(engine, schema_name):
        engine.execute(sqlalchemy.schema.CreateSchema(schema_name))


DOMAIN_PREFIX = "hqdomain_"


def get_schema_name_for_domain(domain):
    # Prefix in-case domain name matches with know schemas such as public
    return f"{DOMAIN_PREFIX}{domain}"


def get_role_name_for_domain(domain):
    # Prefix in-case domain name matches with known role names such as admin
    # Same prefix pattern as schema only by coincidence, not a must.
    return f"{DOMAIN_PREFIX}{domain}"
