from abc import abstractmethod
from typing import Any

from hq_superset.model.db_info import DbInfo


class DbManager(object):

    def __init__(self, db_info: DbInfo) -> None:
        self.db_info = db_info

    @abstractmethod
    def connect(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def create_schema(self, schema_name: str) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def schema_exists(self, schema_name: str) -> bool:
        raise NotImplementedError()
