"""create campaign_metrics and campaign_owners tables

Revision ID: b1c2d3e4f5a6
Revises:
Create Date: 2026-04-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schema if not exists
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics_schema")

    op.create_table(
        "campaign_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("meta_ad_id", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("spend_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conversions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ctr", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("cpc_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("roas", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "collected_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meta_ad_id", "date", name="uq_campaign_metrics_ad_date"),
        schema="analytics_schema",
    )
    op.create_index(
        op.f("ix_analytics_schema_campaign_metrics_campaign_id"),
        "campaign_metrics",
        ["campaign_id"],
        unique=False,
        schema="analytics_schema",
    )
    op.create_index(
        op.f("ix_analytics_schema_campaign_metrics_meta_ad_id"),
        "campaign_metrics",
        ["meta_ad_id"],
        unique=False,
        schema="analytics_schema",
    )

    op.create_table(
        "campaign_owners",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("campaign_id"),
        schema="analytics_schema",
    )
    op.create_index(
        op.f("ix_analytics_schema_campaign_owners_user_id"),
        "campaign_owners",
        ["user_id"],
        unique=False,
        schema="analytics_schema",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_analytics_schema_campaign_owners_user_id"),
        table_name="campaign_owners",
        schema="analytics_schema",
    )
    op.drop_table("campaign_owners", schema="analytics_schema")
    op.drop_index(
        op.f("ix_analytics_schema_campaign_metrics_meta_ad_id"),
        table_name="campaign_metrics",
        schema="analytics_schema",
    )
    op.drop_index(
        op.f("ix_analytics_schema_campaign_metrics_campaign_id"),
        table_name="campaign_metrics",
        schema="analytics_schema",
    )
    op.drop_table("campaign_metrics", schema="analytics_schema")
