from typing import Literal

from pydantic import BaseModel, field_validator


class BusinessContext(BaseModel):
    business_name: str | None = None
    industry: str | None = None
    whatsapp_number: str | None = None
    location: str | None = None
    extra_info: str | None = None


class GenerateProposalsRequest(BaseModel):
    user_prompt: str
    business_context: BusinessContext = BusinessContext()
    campaign_id: str | None = None

    @field_validator("user_prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_prompt cannot be empty")
        return v.strip()


class LocationCountry(BaseModel):
    type: Literal["country"] = "country"
    country_code: str


class LocationCity(BaseModel):
    type: Literal["city"] = "city"
    name: str
    region: str | None = None
    country_code: str


class TargetAudienceResponse(BaseModel):
    age_min: int
    age_max: int
    genders: list[str]
    interests: list[str]
    locations: list[LocationCountry | LocationCity | str]  # str for backward compat


class ProposalResponse(BaseModel):
    copy_text: str
    script: str
    image_prompt: str
    target_audience: TargetAudienceResponse
    cta_type: str
    whatsapp_number: str | None = None


class GenerateProposalsResponse(BaseModel):
    proposals: list[ProposalResponse]
    model_used: str
    prompt_tokens: int
    completion_tokens: int


class MutateProposalRequest(BaseModel):
    original_proposal: ProposalResponse
    mutation_rate: float = 0.15
    campaign_context: str | None = None


class MutateProposalResponse(BaseModel):
    mutated_proposal: ProposalResponse
    mutations_applied: list[str]
    model_used: str
