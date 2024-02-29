from datetime import timedelta

from authlib.integrations.flask_oauth2 import (
    AuthorizationServer,
    ResourceProtector,
)
from authlib.integrations.sqla_oauth2 import (
    create_bearer_token_validator,
    create_query_client_func,
    create_revocation_endpoint,
)
from authlib.oauth2.rfc6749 import grants

from .models import OAuth2Client, OAuth2Token, db


def save_token(token, request):
    client = request.client
    client.revoke_tokens()

    one_day = 24 * 60 * 60
    token = OAuth2Token(
        client_id=client.client_id,
        token_type=token['token_type'],
        access_token=token['access_token'],
        scope=client.domain,
        expires_in=one_day,
    )
    db.session.add(token)
    db.session.commit()


query_client = create_query_client_func(db.session, OAuth2Client)
authorization = AuthorizationServer(
    query_client=query_client,
    save_token=save_token,
)
require_oauth = ResourceProtector()


def config_oauth2(app):
    authorization.init_app(app)
    authorization.register_grant(grants.ClientCredentialsGrant)

    # support revocation
    revocation_cls = create_revocation_endpoint(db.session, OAuth2Token)
    authorization.register_endpoint(revocation_cls)

    # protect resource
    bearer_cls = create_bearer_token_validator(db.session, OAuth2Token)
    require_oauth.register_token_validator(bearer_cls())
