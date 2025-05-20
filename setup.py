from setuptools import find_packages, setup

setup(
    name='commcare-analytics',
    version='1.3.1',
    description='CommCare HQ Superset Integration',
    license='Apache2',
    author='Dimagi Inc.',
    author_email='sreddy@dimagi.com',
    url='https://github.com/dimagi/commcare-analytics',
    packages=find_packages(exclude=['docs', 'tests']),
    include_package_data=True,
    install_requires=[
        'dimagi-superset==4.1.1',
        # Dependencies based on Superset 3.1.0 where applicable
        'Authlib==1.3.0',
        'celery==5.3.6',
        'cryptography==42.0.4',
        'jinja2==3.1.2',
        'psycopg2==2.9.6',
        'requests==2.31.0',
        'sentry-sdk[flask]==1.39.2',
        'Werkzeug==2.3.3',
        'WTForms==2.3.3',
        'ddtrace==2.17.0rc2',
        'datadog==0.50.2',
    ],
    extras_require={
        'dev': [
            'git-build-branch',
        ],
        'test': [
            'pytest==7.3.1',
            'Flask-Testing==0.8.1',
        ]
    },
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
