from datetime import datetime

from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, field_serializer, model_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class CampaignCreate(BaseModel):
    user_prompt: str
    whatsapp_number: str | None = None

    @field_validator("user_prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_prompt cannot be empty")
        return v.strip()


class CampaignUpdate(BaseModel):
    user_prompt: str | None = None
    status: str | None = None
    selected_proposal_id: str | None = None


class ProposalUpdate(BaseModel):
    copy_text: str | None = None
    script: str | None = None
    image_prompt: str | None = None
    target_audience: dict | None = None
    cta_type: str | None = None
    whatsapp_number: str | None = None

    @model_validator(mode="after")
    def enforce_minimum_age_with_interests(self) -> Self:
        """Meta requires age_min >= 18 when using interest-based targeting."""
        if self.target_audience:
            interests = self.target_audience.get("interests", [])
            age_min = self.target_audience.get("age_min", 18)
            if interests and age_min < 18:
                self.target_audience["age_min"] = 18
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class ProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    copy_text: str
    script: str
    image_prompt: str
    target_audience: dict
    cta_type: str
    whatsapp_number: str | None
    is_selected: bool
    is_edited: bool
    image_url: str | None
    created_at: datetime

    @field_validator("id", "campaign_id", mode="before")
    @classmethod
    def uuid_to_str(cls, v):  # noqa: ANN001
        return str(v) if v is not None else v


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    user_prompt: str
    status: str
    selected_proposal_id: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "selected_proposal_id", mode="before")
    @classmethod
    def uuid_to_str(cls, v):  # noqa: ANN001
        return str(v) if v is not None else v


class CampaignDetailResponse(CampaignResponse):
    proposals: list[ProposalResponse] = []


class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]
    total: int
    page: int
    page_size: int
