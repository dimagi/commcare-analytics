import json
from http import HTTPStatus

from flask import request
from flask_appbuilder.api import BaseApi
from flask_appbuilder.baseviews import expose
from superset.superset_typing import FlaskResponse
from superset.views.base import (
    handle_api_exception,
    json_error_response,
    json_success,
)

from .models import DataSetChange


class DataSetChangeAPI(BaseApi):
    """
    Accepts changes to datasets from CommCare HQ data forwarding
    """

    MAX_REQUEST_LENGTH = 10 * 1024 * 1024  # reject JSON requests > 10MB

    def __init__(self):
        self.route_base = '/hq_webhook'
        self.default_view = 'post_dataset_change'
        super().__init__()

    @expose('/change/', methods=('POST',))
    @handle_api_exception
    def post_dataset_change(self) -> FlaskResponse:
        if request.content_length > self.MAX_REQUEST_LENGTH:
            return json_error_response(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE.description,
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE.value,
            )

        try:
            request_json = json.loads(request.get_data(as_text=True))
            change = DataSetChange(**request_json)
            change.update_dataset()
            return json_success('Dataset updated')
        except json.JSONDecodeError:
            return json_error_response(
                'Invalid JSON syntax',
                status=HTTPStatus.BAD_REQUEST.value,
            )
