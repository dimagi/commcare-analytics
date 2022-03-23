## CommCareHQ Superset Integration

This is a python package that can be installed alongside of `apache-superset` to integrate Superset and CommCareHQ. 

## Local Development

While doing development on top of this integration, it's useful to install this via `pip -e` option so that any changes made get reflected directly without another `pip install`.

- Setup a virtual environment.
- Clone this repo and cd into the directory of this repo.
- Run `pip install -e .`

## CommCareHQ OAuth Integration

- Create an OAuth application on CommCareHQ using Django Admin `<hq_host>/admin/oauth2_provider/application/`. Use `<superset_host>/oauth-authorized/commcare` as the redirect URL.
- Update `OAUTH_PROVIDERS` setting in `superset_config.py` with OAuth client credentials obtained from HQ.
