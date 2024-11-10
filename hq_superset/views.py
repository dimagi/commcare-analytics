import logging
import os

import requests
import superset
from flask import Response, abort, flash, g, redirect, request, url_for
from flask_appbuilder import expose
from flask_appbuilder.security.decorators import has_access, permission_name
from superset import db
from superset.commands.dataset.delete import (
    DatasetDeleteFailedError,
    DatasetForbiddenError,
    DatasetNotFoundError,
    DeleteDatasetCommand,
)
from superset.connectors.sqla.models import SqlaTable
from superset.views.base import BaseSupersetView

from hq_superset.exceptions import HQAPIException
from hq_superset.hq_domain import user_domains
from hq_superset.hq_requests import HQRequest
from hq_superset.hq_url import datasource_list
from hq_superset.services import (
    AsyncImportHelper,
    download_and_subscribe_to_datasource,
    get_datasource_defn,
    refresh_hq_datasource,
    unsubscribe_from_hq_datasource,
)
from hq_superset.tasks import refresh_hq_datasource_task
from hq_superset.utils import (
    DomainSyncUtil,
    get_hq_database,
    get_schema_name_for_domain,
)

ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES = 5_000_000  # ~5MB

logger = logging.getLogger(__name__)


class HQDatasourceView(BaseSupersetView):
    class_permission_name = "ExploreFormDataRestApi"

    def __init__(self):
        self.route_base = "/hq_datasource/"
        self.default_view = "list_hq_datasources"
        super().__init__()

    def _ucr_id_to_pks(self):
        tables = db.session.query(SqlaTable).filter_by(
            schema=get_schema_name_for_domain(g.hq_domain),
            database_id=get_hq_database().id,
        )
        return {table.table_name: table.id for table in tables.all()}

    def _ucr_id_from_pk(self, datasource_pk):
        datasource_pk_int = int(datasource_pk)
        # The table name is the UCR datasource id
        try:
            return next(
                (ds_name for ds_name, ds_pk in self._ucr_id_to_pks().items() if ds_pk == datasource_pk_int)
            )
        except StopIteration:
            return None

    @expose("/update/<datasource_id>", methods=["GET"])
    @has_access
    @permission_name("write")
    def create_or_update(self, datasource_id):
        # Fetches data for a datasource from HQ and creates/updates a
        # Superset table
        display_name = request.args.get("name")
        res = trigger_datasource_refresh(
            g.hq_domain, datasource_id, display_name
        )
        return res

    @expose("/list/", methods=["GET"])
    def list_hq_datasources(self):
        hq_request = HQRequest(url=datasource_list(g.hq_domain))
        try:
            response = hq_request.get()
        except requests.exceptions.ConnectionError:
            return Response(
                "Unable to connect to CommCare HQ "
                f"at {hq_request.absolute_url}",
                status=400
            )

        if response.status_code == 403:
            return Response(status=403)
        if response.status_code != 200:
            try:
                msg = response.json()['error']
            except:  # pylint: disable=E722
                msg = ''
            return Response(
                "There was an error in fetching datasources from CommCare HQ "
                f"at {hq_request.absolute_url}: {response.status_code} {msg}",
                status=400
            )
        hq_datasources = response.json()
        for ds in hq_datasources['objects']:
            ds['is_import_in_progress'] = AsyncImportHelper(
                g.hq_domain, ds['id']
            ).is_import_in_progress()
        return self.render_template(
            "hq_datasource_list.html",
            hq_datasources=hq_datasources,
            ucr_id_to_pks=self._ucr_id_to_pks(),
            hq_base_url=hq_request.api_base_url
        )

    @expose("/delete/<datasource_pk>", methods=["GET"])
    def delete(self, datasource_pk):
        datasource_id = self._ucr_id_from_pk(datasource_pk)

        try:
            DeleteDatasetCommand([datasource_pk]).run()
        except DatasetNotFoundError:
            return abort(404)
        except DatasetForbiddenError:
            return abort(403)
        except DatasetDeleteFailedError as ex:
            logger.error(
                "Error deleting model %s: %s",
                self.__class__.__name__,
                str(ex),
                exc_info=True,
            )
            return abort(400, description=str(ex))
        else:
            if datasource_id:
                unsubscribe_from_hq_datasource(g.hq_domain, datasource_id)
        return redirect("/tablemodelview/list/")


def trigger_datasource_refresh(domain, datasource_id, display_name):
    if AsyncImportHelper(domain, datasource_id).is_import_in_progress():
        flash(
            "The datasource is already being imported in the background. "
            "Please wait for it to finish before retrying.",
            "warning",
        )
        return redirect("/tablemodelview/list/")

    try:
        path, size = download_and_subscribe_to_datasource(domain, datasource_id)
    except HQAPIException as e:
        flash(
            f"The datasource refresh failed: {e}. "
            "Please try again or report if issue persists.",
            "danger"
        )
        return redirect("/tablemodelview/list/")

    datasource_defn = get_datasource_defn(domain, datasource_id)
    if size < ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES:
        try:
            refresh_hq_datasource(
                domain, datasource_id, display_name, path, datasource_defn, None
            )
        except Exception:
            flash(
                "The datasource refresh failed. "
                "Please try again or report if issue persists.",
                "danger",
            )
        finally:
            os.remove(path)
        return redirect("/tablemodelview/list/")
    else:
        limit_in_mb = int(ASYNC_DATASOURCE_IMPORT_LIMIT_IN_BYTES / 1000000)
        flash(
            "The datasource is being refreshed in the background as it is "
            f"larger than {limit_in_mb} MB. This may take a while, please "
            "wait for it to finish.",
            "info",
        )
        return queue_refresh_task(
            domain,
            datasource_id,
            display_name,
            path,
            datasource_defn,
            g.user.get_id(),
        )


def queue_refresh_task(
    domain,
    datasource_id,
    display_name,
    export_path,
    datasource_defn,
    user_id,
):
    task_id = refresh_hq_datasource_task.delay(
        domain,
        datasource_id,
        display_name,
        export_path,
        datasource_defn,
        g.user.get_id(),
    ).task_id
    AsyncImportHelper(domain, datasource_id).mark_as_in_progress(task_id)
    return redirect("/tablemodelview/list/")


class SelectDomainView(BaseSupersetView):
    """
    Select a Domain view, all roles that have 'profile' access on
    'core.Superset' view can access this
    """

    # re-use core.Superset view's permission name
    class_permission_name = "Superset"

    def __init__(self):
        self.route_base = "/domain"
        self.default_view = "list"
        super().__init__()

    @expose('/list/', methods=['GET'])
    @has_access
    @permission_name("profile")
    def list(self):
        return self.render_template(
            'select_domain.html',
            next=request.args.get('next'),
            domains=user_domains(),
        )

    @expose('/select/<hq_domain>/', methods=['GET'])
    @has_access
    @permission_name("profile")
    def select(self, hq_domain):
        response = redirect(
            request.args.get('next') or self.appbuilder.get_url_for_index
        )
        if hq_domain not in user_domains():
            flash(
                'Please select a valid domain to access this page.',
                'warning',
            )
            return redirect(url_for('SelectDomainView.list', next=request.url))
        response.set_cookie('hq_domain', hq_domain)
        if not DomainSyncUtil(superset.appbuilder.sm).sync_domain_role(hq_domain):
            flash(
                f"You don't have the necessary HQ permissions to access the domain '{hq_domain}'.",
                'warning',
            )
            return redirect(url_for('SelectDomainView.list', next=request.url))

        return response
