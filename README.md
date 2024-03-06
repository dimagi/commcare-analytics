CommCare HQ Superset Integration
================================

This is a Python package that integrates Superset and CommCare HQ.

Local Development
-----------------

### Preparing CommCare HQ

The 'User configurable reports UI' feature flag must be enabled for the
domain in CommCare HQ, even if the data sources to be imported were
created by Report Builder, not a UCR.


### Setting up a dev environment

While doing development on top of this integration, it's useful to
install this via `pip -e` option so that any changes made get reflected
directly without another `pip install`.

- Set up a virtual environment.
- Clone this repo and change into the directory of this repo.
- Run `cp superset_config.example.py superset_config.py` and override
  the config appropriately.
- Run `pip install -e .`

### CommCare HQ OAuth Integration

- Create an OAuth application on CommCare HQ using Django Admin at the URL
  `<hq_host>/admin/oauth2_provider/application/` with the following settings:

  - Redirect URIs: `<superset_host>/oauth-authorized/commcare`

  - Leave "Post logout redirect URIs" empty.

  - Client type: Confidential

  - Authorization grant type: Authorization code

  - Give your OAuth application a name that users would recognize,
    like "CommCare Analytics" or "HQ Superset". This name will appear
    in CommCare HQ's dialog box requesting authorization from the
    user.

  - Leave "Skip authorization" unchecked

  - Algorithm: No OIDC support

- Update `OAUTH_PROVIDERS` setting in `superset_config.py` with OAuth
  client credentials obtained from HQ.


### Initialize Superset

Read through the initialization instructions at
https://superset.apache.org/docs/installation/installing-superset-from-scratch/#installing-and-initializing-superset.

Create a database for Superset, and a database for storing data from
CommCare HQ. Adapt the username and database names to suit your
environment.
```bash
$ createdb -h localhost -p 5432 -U postgres superset
$ createdb -h localhost -p 5432 -U postgres superset_hq_data
```

Set the following environment variables:
```bash
$ export FLASK_APP=superset
$ export SUPERSET_CONFIG_PATH=/path/to/superset_config.py
```

Set this environment variable to allow OAuth 2.0 authentication with
CommCare HQ over insecure HTTP. (DO NOT USE THIS IN PRODUCTION.)
```bash
$ export AUTHLIB_INSECURE_TRANSPORT=1
```

Initialize the databases. Create an administrator. Create default roles
and permissions:
```bash
$ superset db upgrade
$ superset db upgrade --directory hq_superset/migrations/
$ superset fab create-admin
$ superset load_examples  # (Optional)
$ superset init
```
You may skip `superset load_examples`, although they could be useful.

You should now be able to run superset using the `superset run` command:
```bash
$ superset run -p 8088 --with-threads --reload --debugger
```

You can now log in as a CommCare HQ web user.

In order for CommCare HQ to sync data source changes, you will need to
allow OAuth 2.0 authentication over insecure HTTP. (DO NOT USE THIS IN
PRODUCTION.) Set this environment variable in your CommCare HQ Django
server. (Yes, it's "OAUTHLIB" this time, not "AUTHLIB" as before.)
```bash
$ export OAUTHLIB_INSECURE_TRANSPORT=1
```


### Logging in as a local admin user

There might be situations where you need to log into Superset as a local
admin user, for example, to add a database connection. To enable local
user authentication, in `superset_config.py`, set
`AUTH_TYPE = AUTH_DB`.

Doing this will prevent CommCare HQ users from logging in, so it should
only be done in production environments when CommCare Analytics is not
in use.

To return to allowing CommCare HQ users to log in, set it back to
`AUTH_TYPE = AUTH_OAUTH`.


### Importing UCRs using Redis and Celery

Celery is used to import UCRs that are larger than
`hq_superset.views.ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES`. If you need
to import UCRs larger than this, you need to run Celery to import them.
Here is how celery can be run locally.

- Install and run Redis
- Add Redis and Celery config sections from
  `superset_config.example.py` to your local `superset_config.py`.
- Run
  `celery --app=superset.tasks.celery_app:app worker --pool=prefork -O fair -c 4`
  in the Superset virtualenv.


### Overwriting templates
Superset provides a way to update HTML templates by adding a file called
`tail_js_custom_extra.html`.
This file can be used to insert HTML or script for all pages.
This isn't documented in superset but can be seen in the superset's 
[basic template](https://github.com/apache/superset/blob/f453d5d7e75cfd403b5552d6719b8ebc1f121d9e/superset/templates/superset/basic.html#L131).


### Testing

Tests use pytest, which is included in `requirements_dev.txt`:

    $ pip install -r requirements_test.txt
    $ pytest

The test runner can only run tests that do not import from Superset. The
code you want to test will need to be in a module whose dependencies
don't include Superset.


### Creating a migration

You will need to create an Alembic migration for any new SQLAlchemy
models that you add. The Superset CLI should allow you to do this:

```shell
$ superset db revision --autogenerate -m "Add table for Foo model"
```

However, problems with this approach have occurred in the past. You
might have more success by using Alembic directly. You will need to
modify the configuration a little to do this:

1. Copy the "HQ_DATA" database URI from `superset_config.py`.

2. Paste it as the value of `sqlalchemy.url` in
   `hq_superset/migrations/alembic.ini`.

3. Edit `env.py` and comment out the following lines:
   ```
   hq_data_uri = current_app.config['SQLALCHEMY_BINDS'][HQ_DATA]
   decoded_uri = urllib.parse.unquote(hq_data_uri)
   config.set_main_option('sqlalchemy.url', decoded_uri)
   ```

Those changes will allow Alembic to connect to the "HD Data" database
without the need to instantiate Superset's Flask app. You can now
autogenerate your new table with:

```shell
$ cd hq_superset/migrations/
$ alembic revision --autogenerate -m "Add table for Foo model"
```


Upgrading Superset
------------------

`dimagi-superset` is a requirement of this `hq_superset` package. It is
a fork of `apache-superset`, and adds important features to it,
necessary for `hq_superset`. For more information about how to upgrade
`dimagi-superset`, see [Dimagi Superset Fork](apache-superset.md).
