from dataclasses import dataclass


@dataclass
class DbInfo(object):
    database_name: str
    db_user: str
    db_password: str
    db_host: str = "localhost"
    db_port: str = "5432"
