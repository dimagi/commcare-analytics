from dataclasses import dataclass
from typing import Any, Dict, Literal


@dataclass
class DataSetChange:
    action: Literal['upsert', 'delete']
    data_source_id: str
    data: Dict[str, Any]

    def __post_init__(self):
        if 'doc_id' not in self.data:
            raise TypeError("'data' missing required key: 'doc_id'")
