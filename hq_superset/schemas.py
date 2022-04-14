from datetime import timezone

from marshmallow import Schema, fields


class HQDataSourceConfigSchema(Schema):
    domain = fields.Str(required=True)
    id = fields.Str(required=True)
    display_name = fields.Str(required=True, allow_none=True)
    retrieved_at = fields.NaiveDateTime(
        format='iso',
        timezone=timezone.utc,
        required=True,
    )
