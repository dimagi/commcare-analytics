import json
from authlib.oauth2.rfc6749.errors import InvalidScopeError
from sqlalchemy.orm.exc import NoResultFound
from datetime import datetime, timedelta
from flask_appbuilder.api import expose, BaseApi
from flask import jsonify
from superset import db
from authlib.integrations.flask_oauth2 import AuthorizationServer, ResourceProtector, current_token
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc6750 import BearerTokenValidator
from superset.extensions import appbuilder
from hq_superset.models import HQClient, Token

ONE_DAY_SECONDS = 60*60*24

require_oauth = ResourceProtector()
app = appbuilder.app


def query_client(client_id):
    return HQClient.get_by_client_id(client_id)


def save_token(token, request):
    client = request.client
    client.revoke_tokens()

    expires_at = datetime.utcnow() + timedelta(seconds=ONE_DAY_SECONDS)
    tok = Token(
        client_id=client.client_id,
        expires_at=expires_at,
        access_token=token['access_token'],
        token_type=token['token_type'],
        scope=client.domain,
    )
    db.session.add(tok)
    db.session.commit()


class HQAuthorizationServer(AuthorizationServer):
    def generate_token(self, *args, **kwargs):
        kwargs['expires_in'] = ONE_DAY_SECONDS
        return super().generate_token(*args, **kwargs)


class HQBearerTokenValidator(BearerTokenValidator):
    def authenticate_token(self, token_string):
        return db.session.query(Token).filter_by(access_token=token_string).first()


require_oauth.register_token_validator(HQBearerTokenValidator())

authorization = HQAuthorizationServer(
    app=app,
    query_client=query_client,
    save_token=save_token,
)
authorization.register_grant(grants.ClientCredentialsGrant)


class OAuth(BaseApi):

    def __init__(self):
        super().__init__()
        self.route_base = "/oauth"

    @expose("/token", methods=('POST',))
    def issue_access_token(self):
        try:
            response = authorization.create_token_response()
        except NoResultFound:
            return jsonify({"error": "Invalid client"}), 401

        if response.status_code >= 400:
            return response

        data = json.loads(response.data.decode("utf-8"))
        data['expires_in'] = ONE_DAY_SECONDS
        return jsonify(data)
