## CommCareHQ Superset Integration

This is a python package that can be installed alongside of `apache-superset` to integrate Superset and CommCareHQ. 

## Local Development

Follow below instructions.

### Setup env

While doing development on top of this integration, it's useful to install this via `pip -e` option so that any changes made get reflected directly without another `pip install`.

- Setup a virtual environment.
- Clone this repo and cd into the directory of this repo.
- Run `cp superset_config.example.py superset_config.py` and override the config appropriately.
- Run `pip install -e .`

### CommCareHQ OAuth Integration

- Create an OAuth application on CommCareHQ using Django Admin `<hq_host>/admin/oauth2_provider/application/`. Use `<superset_host>/oauth-authorized/commcare` as the redirect URL.
- Update `OAUTH_PROVIDERS` setting in `superset_config.py` with OAuth client credentials obtained from HQ.


### Initialize Superset

Run through the initialization instructions at https://superset.apache.org/docs/installation/installing-superset-from-scratch/#installing-and-initializing-superset. You may skip `superset load_examples`. 

You should now be able to run superset using the `superset run` command from the above docs. However OAuth login does not work yet as hq-superset needs a postgres database created to store CommCare HQ data.


### Create a Postgres Database Connection for storing HQ data

- Create a Postgres database
- Login to superset as the admin user created in the Superset installation and initialization. Note that you will need to update `AUTH_TYPE = AUTH_DB` to login as admin user. `AUTH_TYPE` should be otherwise set to `AUTH_OAUTH`.
- Go to 'Data' -> 'Databases' or http://127.0.0.1:8088/databaseview/list/
- Create a Database connection by clicking '+ DATABASE' button at the top.
- The name of the DISPLAY NAME should be 'HQ Data' exactly, as this is the name by which this codebase refers to the postgres DB.

OAuth integration should now start working.


### Importing UCRs using Redis and Celery


Celery is used to import UCRs that are larger than
`hq_superset.views.ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES`. If you need
to import UCRs larger than this, you need to run celery to import them.
Here is how celery can be run locally.

- Install and run Redis
- Add Redis and celery config sections from `superset_config.example.py` to your local `superset_config.py`.
- Run `celery --app=superset.tasks.celery_app:app worker --pool=prefork -O fair -c 4` in the superset virtualenv.


### Testing

Tests use pytest, which is included in `requirements_dev.txt`:

    $ pip install -r requirements_dev.txt
    $ pytest

The test runner can only run tests that do not import from Superset. The
code you want to test will need to be in a module whose dependencies
don't include Superset.
