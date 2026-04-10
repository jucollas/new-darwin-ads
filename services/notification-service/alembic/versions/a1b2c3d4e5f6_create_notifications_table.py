"""create_notifications_table

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-04-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS notification_schema")
    op.create_table('notifications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('body', sa.String(), nullable=True),
    sa.Column('data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='notification_schema'
    )
    op.create_index(
        op.f('ix_notification_schema_notifications_user_id'),
        'notifications', ['user_id'], unique=False, schema='notification_schema'
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_notification_schema_notifications_user_id'),
        table_name='notifications', schema='notification_schema'
    )
    op.drop_table('notifications', schema='notification_schema')
