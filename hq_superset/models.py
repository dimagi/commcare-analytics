from dataclasses import dataclass
from typing import Any

from .utils import cast_data_for_table, get_hq_database


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
