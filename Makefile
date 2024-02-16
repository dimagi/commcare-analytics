export SUPERSET_CONFIG_PATH := superset_config.py
export FLASK_APP := superset

all: setup

setup:
	pip install -e .
	pip install -r dev-requirements.txt
	superset db upgrade
	superset init

load-examples:
	superset load_examples

create-admin:
	superset fab create-admin

runserver:
	superset run -p 8088 --with-threads --reload --debugger