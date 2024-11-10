import json
from http import HTTPStatus

from flask import jsonify, request
from flask_appbuilder.api import BaseApi, expose
from sqlalchemy.orm.exc import NoResultFound
from superset.superset_typing import FlaskResponse
from superset.views.base import (
    handle_api_exception,
    json_error_response,
    json_success,
)

from hq_superset.models import DataSetChange
from hq_superset.oauth2_server import authorization, require_oauth
from hq_superset.tasks import process_dataset_change


class OAuth(BaseApi):

    def __init__(self):
        super().__init__()
        self.route_base = "/oauth"

    @expose("/token", methods=('POST',))
    def issue_access_token(self):
        try:
            response = authorization.create_token_response()
        except NoResultFound:
            return jsonify({"error": "Invalid client"}), 401

        if response.status_code >= 400:
            return response

        data = json.loads(response.data.decode("utf-8"))
        return jsonify(data)


class DataSetChangeAPI(BaseApi):
    """
    Accepts changes to datasets from CommCare HQ data forwarding
    """

    MAX_REQUEST_LENGTH = 10 * 1024 * 1024  # reject JSON requests > 10MB

    def __init__(self):
        self.route_base = '/commcarehq_dataset'
        self.default_view = 'post_dataset_change'
        super().__init__()

    @expose('/change/', methods=('POST',))
    @handle_api_exception
    @require_oauth()
    def post_dataset_change(self) -> FlaskResponse:
        if request.content_length > self.MAX_REQUEST_LENGTH:
            return json_error_response(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE.description,
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE.value,
            )

        try:
            request_json = json.loads(request.get_data(as_text=True))
        except json.JSONDecodeError:
            return json_error_response(
                'Invalid JSON syntax',
                status=HTTPStatus.BAD_REQUEST.value,
            )

        try:
            # ensure change request is parsable
            DataSetChange(**request_json)
        except:
            return json_error_response(
                'Could not parse change request',
                status=HTTPStatus.BAD_REQUEST.value,
            )

        process_dataset_change.delay(request_json)
        return json_success(
            'Dataset change accepted',
            status=HTTPStatus.ACCEPTED.value,
        )
