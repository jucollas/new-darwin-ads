"""add resolved_geo_locations to publications

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "publications",
        sa.Column(
            "resolved_geo_locations",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
        schema="publishing_schema",
    )


def downgrade() -> None:
    op.drop_column("publications", "resolved_geo_locations", schema="publishing_schema")
