APP_NAME = "Superset HQ"

import hq_superset
from flask_appbuilder import expose
from superset import config as superset_config

hq_superset.add_ketchup(superset_config)
APP_INITIALIZER = hq_superset.HQSupersetInitializer