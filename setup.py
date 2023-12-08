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
        # Werkzeug 2.1 doesn't work, so pin it
        'Werkzeug==2.0.0',
        'jinja2==3.0.3',
        'dimagi-superset==2.0.1',
        'authlib==1.0.1',
        'requests==2.28.1',
        'psycopg2==2.9.3',
        'WTForms==2.3.3',
        'cryptography==37.0.4',
        'sentry-sdk==1.9.10',
        'celery==5.2.7',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
        'Programming Language :: Python :: 3.8'
    ],
)
