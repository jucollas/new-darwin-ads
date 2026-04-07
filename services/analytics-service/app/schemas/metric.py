import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    meta_ad_id: str
    date: date
    impressions: int
    clicks: int
    spend_cents: int
    conversions: int
    ctr: float
    cpc_cents: int
    roas: float
    collected_at: datetime


class MetricListResponse(BaseModel):
    items: list[MetricResponse]
    total: int


class MetricSummary(BaseModel):
    total_impressions: int
    total_clicks: int
    total_spend_cents: int
    total_conversions: int
    avg_ctr: float
    avg_cpc_cents: float
    avg_roas: float
    active_campaigns: int
    date_range_start: date | None
    date_range_end: date | None


class TopPerformerResponse(BaseModel):
    campaign_id: uuid.UUID
    meta_ad_id: str
    impressions: int
    clicks: int
    ctr: float
    roas: float
    spend_cents: int


class CollectRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"lookback_days": 7}})

    lookback_days: int = 7


class MetricQueryParams(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
