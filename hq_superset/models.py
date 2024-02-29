import secrets
import string
import time
import uuid
from dataclasses import dataclass
from typing import Any

from authlib.integrations.sqla_oauth2 import (
    OAuth2ClientMixin,
    OAuth2TokenMixin,
)
from cryptography.fernet import MultiFernet
from sqlalchemy import update
from superset import db

from .const import OAUTH2_DATABASE_NAME
from .utils import cast_data_for_table, get_fernet_keys, get_hq_database


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

        with (
            database.get_sqla_engine_with_context() as engine,
            engine.connect() as connection,
            connection.begin()  # Commit on leaving context
        ):
            delete_stmt = table.delete().where(table.c.doc_id == self.doc_id)
            connection.execute(delete_stmt)
            if self.data:
                rows = list(cast_data_for_table(self.data, table))
                insert_stmt = table.insert().values(rows)
                connection.execute(insert_stmt)


class OAuth2Client(db.Model, OAuth2ClientMixin):
    __bind_key__ = OAUTH2_DATABASE_NAME
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
        revoked_at = int(time.time())
        stmt = (
            update(OAuth2Token)
            .where(OAuth2Token.client_id == self.client_id)
            .where(OAuth2Token.access_token_revoked_at == 0)
            .values(access_token_revoked_at=revoked_at)
        )
        db.session.execute(stmt)
        db.session.commit()

    @classmethod
    def get_by_domain(cls, domain):
        return db.session.query(OAuth2Client).filter_by(domain=domain).first()

    @classmethod
    def create_domain_client(cls, domain: str):
        alphabet = string.ascii_letters + string.digits
        client_secret = ''.join(secrets.choice(alphabet) for i in range(64))
        client = OAuth2Client(
            domain=domain,
            client_id=str(uuid.uuid4()),
        )
        client.set_client_secret(client_secret)
        client.set_client_metadata({"grant_types": ["client_credentials"]})
        db.session.add(client)
        db.session.commit()
        return client


class OAuth2Token(db.Model, OAuth2TokenMixin):
    __bind_key__ = OAUTH2_DATABASE_NAME
    __tablename__ = 'hq_oauth_token'

    id = db.Column(db.Integer, primary_key=True)

    @property
    def domain(self):
        client = OAuth2Client.get_by_client_id(self.client_id)
        return client.domain
