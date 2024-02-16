import json
from datetime import datetime, timedelta
from http import HTTPStatus

from authlib.integrations.flask_oauth2 import (
    AuthorizationServer,
    ResourceProtector,
)
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc6750 import BearerTokenValidator
from flask import jsonify, request
from flask_appbuilder.api import BaseApi, expose
from flask_appbuilder.baseviews import expose_api
from sqlalchemy.orm.exc import NoResultFound
from superset import db
from superset.extensions import appbuilder, csrf
from superset.superset_typing import FlaskResponse
from superset.views.base import handle_api_exception, json_error_response

from .models import DataSetChange, HQClient, Token
from .utils import update_dataset

require_oauth = ResourceProtector()
app = appbuilder.app


def query_client(client_id):
    return HQClient.get_by_client_id(client_id)


def save_token(token, request):
    client = request.client
    client.revoke_tokens()

    expires_at = datetime.utcnow() + timedelta(days=1)
    tok = Token(
        client_id=client.client_id,
        expires_at=expires_at,
        access_token=token['access_token'],
        token_type=token['token_type'],
        scope=client.domain,
    )
    db.session.add(tok)
    db.session.commit()


class HQBearerTokenValidator(BearerTokenValidator):
    def authenticate_token(self, token_string):
        return (
            db.session.query(Token)
            .filter_by(access_token=token_string)
            .first()
        )


require_oauth.register_token_validator(HQBearerTokenValidator())

authorization = AuthorizationServer(
    app=app,
    query_client=query_client,
    save_token=save_token,
)
authorization.register_grant(grants.ClientCredentialsGrant)


class OAuth(BaseApi):
    def __init__(self):
        super().__init__()
        self.route_base = '/oauth'

    @expose('/token', methods=('POST',))
    def issue_access_token(self):
        try:
            response = authorization.create_token_response()
        except NoResultFound:
            return jsonify({'error': 'Invalid client'}), 401

        if response.status_code >= 400:
            return response

        data = json.loads(response.data.decode('utf-8'))
        return jsonify(data)


class DataSetChangeAPI(BaseApi):
    """
    Accepts changes to datasets from CommCare HQ data forwarding
    """

    MAX_REQUEST_LENGTH = 10_485_760  # reject >10MB JSON requests

    def __init__(self):
        self.route_base = '/hq_webhook'
        self.default_view = 'post_dataset_change'
        super().__init__()

    # http://localhost:8088/hq_webhook/change/
    @expose_api(url='/change/', methods=('POST',))
    @handle_api_exception
    @csrf.exempt
    @require_oauth
    def post_dataset_change(self) -> FlaskResponse:
        if request.content_length > self.MAX_REQUEST_LENGTH:
            return json_error_response(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE.description,
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE.value,
            )

        try:
            request_json = json.loads(request.get_data(as_text=True))
            change = DataSetChange(**request_json)
            update_dataset(change)
            return self.json_response(
                'Request accepted; updating dataset',
                status=HTTPStatus.ACCEPTED.value,
            )
        except json.JSONDecodeError:
            return json_error_response(
                'Invalid JSON syntax',
                status=HTTPStatus.BAD_REQUEST.value,
            )
        except (TypeError, ValueError) as err:
            return json_error_response(
                str(err),
                status=HTTPStatus.BAD_REQUEST.value,
            )
        # `@handle_api_exception` will return other exceptions as JSON
        # with status code 500, e.g.
        #     {"error": "CommCare HQ database missing"}
