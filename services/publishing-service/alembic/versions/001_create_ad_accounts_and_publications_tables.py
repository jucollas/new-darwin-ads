"""create ad_accounts and publications tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-04-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ad_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("meta_ad_account_id", sa.String(), nullable=False),
        sa.Column("meta_page_id", sa.String(), nullable=False),
        sa.Column("meta_business_id", sa.String(), nullable=True),
        sa.Column("whatsapp_phone_number", sa.String(), nullable=True),
        sa.Column("access_token_encrypted", sa.String(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "token_scopes",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("token_last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="publishing_schema",
    )
    op.create_index(
        op.f("ix_publishing_schema_ad_accounts_user_id"),
        "ad_accounts",
        ["user_id"],
        unique=False,
        schema="publishing_schema",
    )

    op.create_table(
        "publications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("ad_account_id", sa.Uuid(), nullable=False),
        sa.Column("meta_campaign_id", sa.String(), nullable=True),
        sa.Column("meta_adset_id", sa.String(), nullable=True),
        sa.Column("meta_adcreative_id", sa.String(), nullable=True),
        sa.Column("meta_ad_id", sa.String(), nullable=True),
        sa.Column("meta_image_hash", sa.String(), nullable=True),
        sa.Column(
            "special_ad_categories",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("destination_type", sa.String(), nullable=False),
        sa.Column("campaign_objective", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("budget_daily_cents", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("error_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ad_account_id"],
            ["publishing_schema.ad_accounts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="publishing_schema",
    )
    op.create_index(
        op.f("ix_publishing_schema_publications_campaign_id"),
        "publications",
        ["campaign_id"],
        unique=False,
        schema="publishing_schema",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_publishing_schema_publications_campaign_id"),
        table_name="publications",
        schema="publishing_schema",
    )
    op.drop_table("publications", schema="publishing_schema")
    op.drop_index(
        op.f("ix_publishing_schema_ad_accounts_user_id"),
        table_name="ad_accounts",
        schema="publishing_schema",
    )
    op.drop_table("ad_accounts", schema="publishing_schema")
