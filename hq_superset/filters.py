from sqlalchemy.orm.query import Query

from superset.views.base import BaseFilter

from .models import HQDataSourceConfigModel


class HQDataSourceConfigDomainFilter(BaseFilter):

    def apply(self, query: Query, value: str) -> Query:
        return query.filter(HQDataSourceConfigModel.domain == value)
