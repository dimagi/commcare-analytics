import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Literal

from authlib.integrations.sqla_oauth2 import OAuth2ClientMixin
from superset import db
from werkzeug.security import check_password_hash, generate_password_hash


@dataclass
class DataSetChange:
    action: Literal['upsert', 'delete']
    data_source_id: str
    data: Dict[str, Any]

    def __post_init__(self):
        if 'doc_id' not in self.data:
            raise TypeError("'data' missing required key: 'doc_id'")


class HQClient(db.Model, OAuth2ClientMixin):
    __tablename__ = 'hq_oauth_client'

    domain = db.Column(db.String(255), primary_key=True)

    def check_client_secret(self, client_secret):
        return check_password_hash(self.client_secret, client_secret)

    def revoke_tokens(self):
        tokens = db.session.execute(
            db.select(Token).filter_by(client_id=self.client_id, revoked=False)
        ).all()
        for (token,) in tokens:
            token.revoked = True
            db.session.add(token)
        db.session.commit()

    @classmethod
    def get_by_domain(cls, domain):
        return db.session.query(HQClient).filter_by(domain=domain).first()

    @classmethod
    def get_by_client_id(cls, client_id):
        return (
            db.session.query(HQClient).filter_by(client_id=client_id).first()
        )

    @classmethod
    def create_domain_client(cls, domain: str):
        alphabet = string.ascii_letters + string.digits
        client_secret = ''.join(secrets.choice(alphabet) for i in range(64))

        client = HQClient(
            domain=domain,
            client_id=str(uuid.uuid4()),
            client_secret=generate_password_hash(client_secret),
        )
        client.set_client_metadata({'grant_types': ['client_credentials']})

        db.session.add(client)
        db.session.commit()

        return client.client_id, client_secret


class Token(db.Model):
    __tablename__ = 'hq_oauth_token'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_id = db.Column(db.String(40), nullable=False, index=True)
    token_type = db.Column(db.String(40))
    access_token = db.Column(db.String(255), nullable=False, unique=True)
    revoked = db.Column(db.Boolean, default=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    scope = db.Column(db.String(255))

    @property
    def domain(self):
        client = HQClient.get_by_client_id(self.client_id)
        return client.domain

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def is_revoked(self):
        """
        The require_oauth ResourceProtector needs this method to be defined
        """
        return self.revoked

    def get_scope(self):
        """
        The require_oauth ResourceProtector needs this method to be defined
        """
        return self.scope
