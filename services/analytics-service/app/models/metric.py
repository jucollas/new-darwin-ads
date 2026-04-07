import uuid
from datetime import date, datetime

from sqlalchemy import UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.session import Base


class CampaignMetric(Base):
    __tablename__ = "campaign_metrics"
    __table_args__ = (
        UniqueConstraint("meta_ad_id", "date", name="uq_campaign_metrics_ad_date"),
        {"schema": "analytics_schema"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(index=True)
    meta_ad_id: Mapped[str] = mapped_column(index=True)
    date: Mapped[date]
    impressions: Mapped[int] = mapped_column(default=0)
    clicks: Mapped[int] = mapped_column(default=0)
    spend_cents: Mapped[int] = mapped_column(default=0)
    conversions: Mapped[int] = mapped_column(default=0)
    ctr: Mapped[float] = mapped_column(default=0.0)
    cpc_cents: Mapped[int] = mapped_column(default=0)
    roas: Mapped[float] = mapped_column(default=0.0)
    collected_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


class CampaignOwner(Base):
    __tablename__ = "campaign_owners"
    __table_args__ = {"schema": "analytics_schema"}

    campaign_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(index=True)
