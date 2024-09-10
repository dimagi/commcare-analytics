"""
Functions that return URLs on CommCare HQ
"""


def datasource_details(domain, datasource_id):
    return f"a/{domain}/api/v0.5/ucr_data_source/{datasource_id}/"


def datasource_list(domain):
    return f"a/{domain}/api/v0.5/ucr_data_source/"


def datasource_export(domain, datasource_id):
    return (
        f"a/{domain}/configurable_reports/data_sources/export/{datasource_id}/"
        "?format=csv"
    )


def datasource_subscribe(domain, datasource_id):
    return (
        f"a/{domain}/configurable_reports/data_sources/subscribe/"
        f"{datasource_id}/"
    )


def datasource_unsubscribe(domain, datasource_id):
    return (
        f"a/{domain}/configurable_reports/data_sources/unsubscribe/"
        f"{datasource_id}/"
    )


def user_domain_roles(domain):
    return f"a/{domain}/api/v0.5/analytics-roles/"
