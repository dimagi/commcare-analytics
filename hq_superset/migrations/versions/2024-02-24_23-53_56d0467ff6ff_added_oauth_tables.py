"""Added OAuth tables

Revision ID: 56d0467ff6ff
Revises:
Create Date: 2024-02-24 23:53:10.289606
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '56d0467ff6ff'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'hq_oauth_client',
        sa.Column('client_id', sa.String(length=48), nullable=True),
        sa.Column('client_id_issued_at', sa.Integer(), nullable=False),
        sa.Column('client_secret_expires_at', sa.Integer(), nullable=False),
        sa.Column('client_metadata', sa.Text(), nullable=True),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('client_secret', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('domain'),
        info={'bind_key': 'oauth2-server-data'},
    )
    op.create_index(
        op.f('ix_hq_oauth_client_client_id'),
        'hq_oauth_client',
        ['client_id'],
        unique=False,
    )
    op.create_table(
        'hq_oauth_token',
        sa.Column('client_id', sa.String(length=48), nullable=True),
        sa.Column('token_type', sa.String(length=40), nullable=True),
        sa.Column('access_token', sa.String(length=255), nullable=False),
        sa.Column('refresh_token', sa.String(length=255), nullable=True),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('issued_at', sa.Integer(), nullable=False),
        sa.Column('access_token_revoked_at', sa.Integer(), nullable=False),
        sa.Column('refresh_token_revoked_at', sa.Integer(), nullable=False),
        sa.Column('expires_in', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('access_token'),
        info={'bind_key': 'oauth2-server-data'},
    )
    op.create_index(
        op.f('ix_hq_oauth_token_refresh_token'),
        'hq_oauth_token',
        ['refresh_token'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table('hq_oauth_token')
    op.drop_index(
        op.f('ix_hq_oauth_client_client_id'), table_name='hq_oauth_client'
    )
    op.drop_table('hq_oauth_client')
