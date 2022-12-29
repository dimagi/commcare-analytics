from functools import wraps
from sqlalchemy.orm.exc import NoResultFound
from hq_superset.utils import get_ucr_database, HQ_DB_CONNECTION_NAME

# @pytest.fixture(scope="session", autouse=True)
# def manage_ucr_db(request):
#     # setup_ucr_db()
#     request.addfinalizer(clear_ucr_db)

def unit_testing_only(fn):
    import superset

    @wraps(fn)
    def inner(*args, **kwargs):
        if not superset.app.config.get('TESTING'):
            raise UnitTestingRequired(
                'You may only call {} during unit testing'.format(fn.__name__))
        return fn(*args, **kwargs)
    return inner


@unit_testing_only
def setup_hq_db():
    from superset.databases.commands.create import CreateDatabaseCommand
    import superset
    try:
        get_ucr_database()
    except NoResultFound:
        CreateDatabaseCommand(
            None, 
            {
                'sqlalchemy_uri': superset.app.config.get('HQ_DATA_DB'),
                'engine': 'PostgreSQL', 
                'database_name': HQ_DB_CONNECTION_NAME
            }
        ).run()
