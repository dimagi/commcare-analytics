from superset_config import SERVER_ENVIRONMENT


def get_tags(tag_values: dict[str, str]) -> list[str]:
    tag_values.update({"env": SERVER_ENVIRONMENT})

    return [
        f'{name}:{value}' for name, value in tag_values.items()
    ]
