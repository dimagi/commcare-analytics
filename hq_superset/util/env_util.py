from os import environ

from hq_superset.model.db_info import DbInfo


def get_env(key: str, default_value: str = None) -> str:
    return environ.get(key, default_value)


def get_db_connection_info() -> DbInfo:
    return DbInfo(database_name=get_env("db_database"),
                  db_user=get_env("db_user"),
                  db_password=get_env("db_password"),
                  db_host=get_env("db_host"),
                  db_port=get_env("db_port"))
