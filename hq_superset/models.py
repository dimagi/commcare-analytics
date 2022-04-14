from sqlalchemy import Column, DateTime, String

from flask_appbuilder import Model


class HQDataSourceConfigModel(Model):
    __tablename__ = 'hq_data_source_configs'

    domain = Column(String, index=True)
    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=True)
    retrieved_at = Column(DateTime)
