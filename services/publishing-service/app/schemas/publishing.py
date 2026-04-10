import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


ODAX_OBJECTIVES = {"OUTCOME_ENGAGEMENT", "OUTCOME_LEADS", "OUTCOME_SALES", "OUTCOME_TRAFFIC"}
DESTINATION_TYPES = {"WHATSAPP", "WEBSITE", "APP"}


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AdAccountCreate(BaseModel):
    meta_ad_account_id: str
    meta_page_id: str
    access_token: str
    meta_business_id: str | None = None
    whatsapp_phone_number: str | None = None
    token_scopes: list[str] = ["ads_management", "ads_read"]

    @field_validator("meta_ad_account_id")
    @classmethod
    def must_start_with_act(cls, v: str) -> str:
        if not v.startswith("act_"):
            raise ValueError("meta_ad_account_id must start with 'act_'")
        return v

    @field_validator("whatsapp_phone_number")
    @classmethod
    def validate_e164(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^\+[1-9]\d{6,14}$", v):
            raise ValueError("whatsapp_phone_number must be in E.164 format (e.g. +573001234567)")
        return v

    @field_validator("access_token")
    @classmethod
    def token_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("access_token cannot be empty")
        return v.strip()


class SetWhatsAppNumberRequest(BaseModel):
    whatsapp_number: str

    @field_validator("whatsapp_number")
    @classmethod
    def validate_e164(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r'^\+[1-9]\d{9,14}$', v):
            raise ValueError("Phone number must be in E.164 format (e.g., +573001234567)")
        return v


class PublishRequest(BaseModel):
    campaign_id: str
    proposal_id: str
    ad_account_id: str
    budget_daily_cents: int

    @field_validator("campaign_id", "proposal_id", "ad_account_id")
    @classmethod
    def validate_uuid_format(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError(f"'{v}' is not a valid UUID")
        return v
    special_ad_categories: list[str] = []
    destination_type: str = "WHATSAPP"
    campaign_objective: str = "OUTCOME_ENGAGEMENT"
    name: str | None = None

    @field_validator("budget_daily_cents")
    @classmethod
    def budget_minimum(cls, v: int) -> int:
        if v < 100:
            raise ValueError("budget_daily_cents must be at least 100 ($1 USD)")
        return v

    @field_validator("campaign_objective")
    @classmethod
    def valid_objective(cls, v: str) -> str:
        if v not in ODAX_OBJECTIVES:
            raise ValueError(f"campaign_objective must be one of {ODAX_OBJECTIVES}")
        return v

    @field_validator("destination_type")
    @classmethod
    def valid_destination(cls, v: str) -> str:
        if v not in DESTINATION_TYPES:
            raise ValueError(f"destination_type must be one of {DESTINATION_TYPES}")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AdAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    meta_ad_account_id: str
    meta_page_id: str
    meta_business_id: str | None
    whatsapp_phone_number: str | None
    token_expires_at: datetime | None
    token_scopes: list
    token_last_verified_at: datetime | None
    is_active: bool
    created_at: datetime


class AdAccountListResponse(BaseModel):
    items: list[AdAccountResponse]
    total: int
    page: int
    page_size: int


class AdAccountVerifyResponse(BaseModel):
    is_valid: bool
    expires_at: datetime | None = None
    scopes: list[str] = []
    needs_reauth: bool = False
    message: str = ""


class PublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    proposal_id: uuid.UUID
    ad_account_id: uuid.UUID
    meta_campaign_id: str | None
    meta_adset_id: str | None
    meta_adcreative_id: str | None
    meta_ad_id: str | None
    meta_image_hash: str | None
    special_ad_categories: list
    destination_type: str
    campaign_objective: str
    status: str
    budget_daily_cents: int
    resolved_geo_locations: dict | None = None
    published_at: datetime | None
    error_message: str | None
    error_code: int | None
    created_at: datetime


class PublicationListResponse(BaseModel):
    items: list[PublicationResponse]
    total: int
    page: int
    page_size: int


class PublicationBudgetUpdate(BaseModel):
    budget_daily_cents: int

    @field_validator("budget_daily_cents")
    @classmethod
    def budget_minimum(cls, v: int) -> int:
        if v < 100:
            raise ValueError("budget_daily_cents must be at least 100 ($1 USD)")
        return v


class PublicationStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    meta_effective_status: str | None = None
    delivery_status: str | None = None
