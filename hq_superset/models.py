import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Literal

from authlib.integrations.sqla_oauth2 import OAuth2ClientMixin
from cryptography.fernet import MultiFernet
from superset import db

from .const import HQ_DATA
from .utils import get_explore_database, get_fernet_keys, get_hq_database


@dataclass
class DataSetChange:
    action: Literal['upsert', 'delete']
    data_source_id: str
    data: Dict[str, Any]

    def __post_init__(self):
        if 'doc_id' not in self.data:
            raise TypeError("'data' missing required key: 'doc_id'")

    def update_dataset(self):
        # Import here so that this module does not require an
        # application context, and can be used by the Alembic CLI.
        from superset.connectors.sqla.models import SqlaTable

        database = get_hq_database()
        explore_database = get_explore_database(database)  # TODO: Necessary?
        sqla_table = (
            db.session.query(SqlaTable)
            .filter_by(
                table_name=self.data_source_id,
                database_id=explore_database.id,
            )
            .one_or_none()
        )
        if sqla_table is None:
            raise ValueError(f'{self.data_source_id} table not found.')

        if self.action == 'delete':
            stmt = (
                sqla_table
                .delete()
                .where(sqla_table.doc_id == self.data['doc_id'])
            )
        elif self.action == 'upsert':
            stmt = (
                sqla_table
                .insert()
                .values(self.data)  # TODO: Do we need to cast anything?
                .on_conflict_do_update(
                    index_elements=['doc_id'],
                    set_=self.data,
                )
            )
        else:
            raise ValueError(f'Invalid DataSetChange action {self.action!r}')
        try:
            db.session.execute(stmt)
            db.session.commit()
        except Exception:  # pylint: disable=broad-except
            db.session.rollback()
            raise


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
