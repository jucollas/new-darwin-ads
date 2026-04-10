import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON

from shared.database.session import Base


class AdAccount(Base):
    __tablename__ = "ad_accounts"
    __table_args__ = {"schema": "publishing_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(index=True)
    meta_ad_account_id: Mapped[str]
    meta_page_id: Mapped[str]
    meta_business_id: Mapped[str | None] = mapped_column(default=None)
    whatsapp_phone_number: Mapped[str | None] = mapped_column(default=None)
    access_token_encrypted: Mapped[str]
    token_expires_at: Mapped[datetime | None] = mapped_column(default=None)
    token_scopes: Mapped[list] = mapped_column(JSON, default=["ads_management", "ads_read", "business_management", "pages_manage_ads", "pages_read_engagement", "pages_show_list", "whatsapp_business_management", "whatsapp_business_messaging"])
    token_last_verified_at: Mapped[datetime | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    publications: Mapped[list["Publication"]] = relationship(back_populates="ad_account")


class Publication(Base):
    __tablename__ = "publications"
    __table_args__ = {"schema": "publishing_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(index=True)
    proposal_id: Mapped[uuid.UUID]
    ad_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publishing_schema.ad_accounts.id"))
    meta_campaign_id: Mapped[str | None] = mapped_column(default=None)
    meta_adset_id: Mapped[str | None] = mapped_column(default=None)
    meta_adcreative_id: Mapped[str | None] = mapped_column(default=None)
    meta_ad_id: Mapped[str | None] = mapped_column(default=None)
    meta_image_hash: Mapped[str | None] = mapped_column(default=None)
    special_ad_categories: Mapped[list] = mapped_column(JSON, default=[])
    destination_type: Mapped[str] = mapped_column(default="WHATSAPP")
    campaign_objective: Mapped[str] = mapped_column(default="OUTCOME_ENGAGEMENT")
    status: Mapped[str] = mapped_column(default="queued")
    budget_daily_cents: Mapped[int]
    published_at: Mapped[datetime | None] = mapped_column(default=None)
    resolved_geo_locations: Mapped[dict | None] = mapped_column(JSON, default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)
    error_code: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    ad_account: Mapped["AdAccount"] = relationship(back_populates="publications")
