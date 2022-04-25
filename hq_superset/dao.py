from superset.dao.base import BaseDAO

from .filters import HQDataSourceConfigDomainFilter
from .models import HQDataSourceConfigModel


class HQAPIDataSourceConfigurationDAO(BaseDAO):
    model_cls = HQDataSourceConfigModel
    base_filter = HQDataSourceConfigDomainFilter
