from typing import Dict, List
from superset_config import SERVER_ENVIRONMENT


def get_tags(tag_values: Dict[str, str]) -> List[str]:
    tag_values.update({"env": SERVER_ENVIRONMENT})

    return [
        f'{name}:{value}' for name, value in tag_values.items()
    ]
