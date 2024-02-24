import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from authlib.integrations.sqla_oauth2 import OAuth2ClientMixin
from cryptography.fernet import MultiFernet
from superset import db

from .const import HQ_DATA
from .utils import get_fernet_keys, get_hq_database


@dataclass
class DataSetChange:
    data_source_id: str
    doc_id: str
    data: list[dict[str, Any]]

    def update_dataset(self):
        database = get_hq_database()
        try:
            sqla_table = next((
                table for table in database.tables
                if table.table_name == self.data_source_id
            ))
        except StopIteration:
            raise ValueError(f'{self.data_source_id} table not found.')

        table = sqla_table.get_sqla_table_object()
        delete_stmt = table.delete().where(table.c.doc_id == self.doc_id)
        insert_stmt = table.insert().values(self.data) if self.data else None

        with (
            database.get_sqla_engine_with_context() as engine,
            engine.connect() as connection,
            connection.begin()  # Commit on leaving context
        ):
            connection.execute(delete_stmt)
            if insert_stmt:
                connection.execute(insert_stmt)


class HQClient(db.Model, OAuth2ClientMixin):
    __bind_key__ = HQ_DATA
    __tablename__ = 'hq_oauth_client'

    domain = db.Column(db.String(255), primary_key=True)
    client_secret = db.Column(db.String(255))  # more chars for encryption

    def get_client_secret(self):
        keys = get_fernet_keys()
        fernet = MultiFernet(keys)

        ciphertext_bytes = self.client_secret.encode('utf-8')
        plaintext_bytes = fernet.decrypt(ciphertext_bytes)
        return plaintext_bytes.decode('utf-8')

    def set_client_secret(self, plaintext):
        keys = get_fernet_keys()
        fernet = MultiFernet(keys)

        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext_bytes = fernet.encrypt(plaintext_bytes)
        self.client_secret = ciphertext_bytes.decode('utf-8')

    def check_client_secret(self, plaintext):
        return self.get_client_secret() == plaintext

    def revoke_tokens(self):
        tokens = db.session.execute(
            db.select(Token).filter_by(client_id=self.client_id, revoked=False)
        ).all()
        for token, in tokens:
            token.revoked = True
            db.session.add(token)
        db.session.commit()

    @classmethod
    def get_by_domain(cls, domain):
        return db.session.query(HQClient).filter_by(domain=domain).first()

    @classmethod
    def create_domain_client(cls, domain: str):
        alphabet = string.ascii_letters + string.digits
        client_secret = ''.join(secrets.choice(alphabet) for i in range(64))
        client = HQClient(
            domain=domain,
            client_id=str(uuid.uuid4()),
        )
        client.set_client_secret(client_secret)
        client.set_client_metadata({"grant_types": ["client_credentials"]})
        db.session.add(client)
        db.session.commit()
        return client


class Token(db.Model):
    __bind_key__ = HQ_DATA
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
