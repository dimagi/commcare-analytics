import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from authlib.integrations.sqla_oauth2 import OAuth2ClientMixin
from cryptography.fernet import MultiFernet
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from superset import db

from .const import HQ_DATA
from .utils import get_fernet_keys, get_hq_database


@dataclass
class DataSetChange:
    data_source_id: str
    doc_id: str
    data: list[dict[str, Any]]

    def update_dataset(self):
        # Import here so that this module does not require an
        # application context, and can be used by the Alembic CLI.
        from superset.connectors.sqla.models import SqlaTable

        def excluded_to_dict(excl):
            assert self.data[0]  # We know data has at least one row
            return {
                k: getattr(excl, k)
                for k in self.data[0].keys()
                if k != 'doc_id'
            }

        database = get_hq_database()
        sqla_table: SqlaTable = (
            db.session.query(SqlaTable)
            .filter_by(
                table_name=self.data_source_id,
                database_id=database.id,
            )
            .one_or_none()
        )
        if sqla_table is None:
            raise ValueError(f'{self.data_source_id} table not found.')
        sqla_table_obj = sqla_table.get_sqla_table_object()

        if self.data:
            # upsert
            insert_stmt = pg_insert(sqla_table_obj).values(self.data)
            stmt = insert_stmt.on_conflict_do_update(
                index_elements=['doc_id'],
                set_=excluded_to_dict(insert_stmt.excluded)
            )
        else:
            # delete
            stmt = (
                delete(sqla_table_obj)
                .where(sqla_table_obj.c.doc_id == self.doc_id)
            )

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
