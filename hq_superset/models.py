from dataclasses import dataclass
from sqlalchemy.dialects.postgresql import insert
from typing import Any

from authlib.integrations.sqla_oauth2 import (
    OAuth2ClientMixin,
    OAuth2TokenMixin,
)
from cryptography.fernet import MultiFernet
from superset import db

from hq_superset.const import OAUTH2_DATABASE_NAME
from hq_superset.exceptions import TableMissing
from hq_superset.utils import (
    cast_data_for_table,
    get_fernet_keys,
    get_hq_database,
)


@dataclass
class DataSetChange:
    data_source_id: str
    doc_id: str
    data: list[dict[str, Any]]

    def update_dataset(self):
        """
        Updates a dataset with ``self.data``.

        ``self.data`` represents the current state of a UCR data source
        for a form or a case, which is identified by ``self.doc_id``. If
        the form or case has been deleted, then the list will be empty.
        """
        database = get_hq_database()
        try:
            sqla_table = next((
                table for table in database.tables
                if table.table_name == self.data_source_id
            ))
        except StopIteration:
            raise TableMissing(f'{self.data_source_id} table not found.')
        table = sqla_table.get_sqla_table_object()

        with (
            database.get_sqla_engine_with_context() as engine,
            engine.connect() as connection,
            connection.begin()  # Commit on leaving context
        ):
            if self.data:
                rows = list(cast_data_for_table(self.data, table))
                upsert = insert(table).values(rows)
                upsert.on_conflict_do_update(
                    constraint=table.primary_key,
                    set_={
                        col.name: col for col in upsert.excluded if not col.primary_key
                    }
                )
            else:
                delete_stmt = table.delete().where(table.c.doc_id == self.doc_id)
                connection.execute(delete_stmt)


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


class OAuth2Token(db.Model, OAuth2TokenMixin):
    __bind_key__ = OAUTH2_DATABASE_NAME
    __tablename__ = 'hq_oauth_token'

    id = db.Column(db.Integer, primary_key=True)

    @property
    def domain(self):
        client = OAuth2Client.get_by_client_id(self.client_id)
        return client.domain
