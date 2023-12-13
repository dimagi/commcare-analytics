"""
Setup.py for superset-patchup
"""
from setuptools import setup, find_packages

setup(
    name='hq_superset',
    version='0.2.0',
    description='CommCareHQ Superset Integration',
    license='Apache2',
    author='Dimagi Inc',
    author_email='sreddy@dimagi.com',
    url='https://github.com/dimagi/hq_superset',
    packages=find_packages(exclude=['docs', 'tests']),
    include_package_data=True,
    install_requires=[
        # 'dimagi-superset==2.0.1',
        # 'apache-superset==2.1.2',
        'apache-superset @ git+ssh://git@github.com/apache/superset@master#egg=apache-superset'

        'Werkzeug',  # 2.3.8 (Superset uses "werkzeug>=2.3.3, <3")
        'Jinja2',  # Superset dependency installs 3.1.2
        'authlib',
        'requests',  # Superset dependency installs 2.31.0
        'psycopg2',  # Superset uses psycopg2-binary==2.9.1
        'WTForms',  # Superset dependency installs 2.3.3
        'cryptography',  # Superset: "cryptography>=41.0.2, <41.1.0"
        'sentry-sdk',
        'celery',  # Superset: "celery>=5.2.2, <6.0.0"
    ],
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
        'Programming Language :: Python :: 3.8'
    ],
)
