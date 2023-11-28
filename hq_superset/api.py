import json
from authlib.oauth2.rfc6749.errors import InvalidScopeError
from sqlalchemy.orm.exc import NoResultFound
from datetime import datetime, timedelta
from flask_appbuilder.api import expose, BaseApi
from flask import jsonify
from superset import db
from authlib.integrations.flask_oauth2 import AuthorizationServer
from authlib.oauth2.rfc6749 import grants
from superset.extensions import appbuilder
from werkzeug.security import check_password_hash
from authlib.integrations.sqla_oauth2 import OAuth2ClientMixin

ONE_DAY_SECONDS = 60*60*24
app = appbuilder.app


class HQClient(db.Model, OAuth2ClientMixin):
    __tablename__ = 'hq_oauth_client'

    domain = db.Column(db.String(255), primary_key=True)

    def check_client_secret(self, client_secret):
        return check_password_hash(self.client_secret, client_secret)

    def revoke_tokens(self):
        tokens = db.session.execute(
            db.select(Token).filter_by(client_id=self.client_id, revoked=False)
        ).all()
        for token, in tokens:
            token.revoked = True
            db.session.add(token)
        db.session.commit()


class Token(db.Model):
    __tablename__ = 'hq_oauth_token'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_id = db.Column(db.String(40), nullable=False, index=True)
    token_type = db.Column(db.String(40))
    access_token = db.Column(db.String(255), nullable=False, unique=True)
    scope = db.Column(db.String(255))  # could be the domain data sources
    revoked = db.Column(db.Boolean, default=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)


def query_client(client_id):
    return db.session.execute(
        db.select(HQClient).filter_by(client_id=client_id)
    ).scalar_one()


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


class HQClientCredentialsGrant(grants.ClientCredentialsGrant):

    def validate_requested_scope(self, *args, **kwargs):
        if not self.request.scope == self.client.domain:
            raise InvalidScopeError()


authorization = AuthorizationServer(
    app=app,
    query_client=query_client,
    save_token=save_token,
)
authorization.register_grant(HQClientCredentialsGrant)


class OAuth(BaseApi):

    @expose("/token", methods=('POST',))
    def issue_access_token(self):
        try:
            response = authorization.create_token_response()
        except NoResultFound:
            return jsonify({"error": "Invalid credentials"}), 401

        if response.status_code >= 400:
            return response

        data = json.loads(response.data.decode("utf-8"))
        data['expires_in'] = ONE_DAY_SECONDS
        return jsonify(data)
