import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


# ---------------------------------------------------------------------------
# GeneticConfig schemas
# ---------------------------------------------------------------------------


class GeneticConfigUpdate(BaseModel):
    """Partial update — all fields optional. Used by PUT /config."""

    target_cpa_cents: int | None = None
    min_impressions_to_evaluate: int | None = None
    min_days_active: int | None = None
    min_spend_cpa_multiplier: float | None = None
    fitness_weights: dict | None = None
    early_stage_weights: dict | None = None
    emergency_kill_cpa_multiplier: float | None = None
    kill_percentile_bottom: float | None = None
    ctr_absolute_floor: float | None = None
    max_frequency_prospecting: float | None = None
    graduated_cpa_threshold: float | None = None
    duplicate_min_days_stable: int | None = None
    duplicate_min_weekly_conversions: int | None = None
    duplicate_max_cpa_ratio: float | None = None
    duplicate_min_roas: float | None = None
    max_budget_increase_pct: float | None = None
    budget_increase_interval_days: int | None = None
    duplicates_per_winner: int | None = None
    mutation_rate: float | None = None
    crossover_rate: float | None = None
    elitism_count: int | None = None
    max_active_campaigns: int | None = None
    mutation_priorities: list[str] | None = None

    @field_validator("target_cpa_cents")
    @classmethod
    def target_cpa_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("target_cpa_cents must be > 0")
        return v

    @field_validator("kill_percentile_bottom")
    @classmethod
    def kill_percentile_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 0.5):
            raise ValueError("kill_percentile_bottom must be between 0.0 and 0.5")
        return v

    @field_validator("mutation_rate")
    @classmethod
    def mutation_rate_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("mutation_rate must be between 0.0 and 1.0")
        return v

    @field_validator("crossover_rate")
    @classmethod
    def crossover_rate_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("crossover_rate must be between 0.0 and 1.0")
        return v

    @field_validator("max_budget_increase_pct")
    @classmethod
    def budget_increase_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("max_budget_increase_pct must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "GeneticConfigUpdate":
        for field_name in ("fitness_weights", "early_stage_weights"):
            weights = getattr(self, field_name)
            if weights is not None:
                total = sum(weights.values())
                if abs(total - 1.0) > 0.01:
                    raise ValueError(
                        f"{field_name} values must sum to 1.0 (got {total:.4f})"
                    )
        return self


class GeneticConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    target_cpa_cents: int
    min_impressions_to_evaluate: int
    min_days_active: int
    min_spend_cpa_multiplier: float
    fitness_weights: dict
    early_stage_weights: dict
    emergency_kill_cpa_multiplier: float
    kill_percentile_bottom: float
    ctr_absolute_floor: float
    max_frequency_prospecting: float
    graduated_cpa_threshold: float
    duplicate_min_days_stable: int
    duplicate_min_weekly_conversions: int
    duplicate_max_cpa_ratio: float
    duplicate_min_roas: float
    max_budget_increase_pct: float
    budget_increase_interval_days: int
    duplicates_per_winner: int
    mutation_rate: float
    crossover_rate: float
    elitism_count: int
    max_active_campaigns: int
    mutation_priorities: list[str]


# ---------------------------------------------------------------------------
# OptimizationRun schemas
# ---------------------------------------------------------------------------


class OptimizationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    generation_number: int
    campaigns_evaluated: int
    campaigns_duplicated: list
    campaigns_killed: list
    fitness_scores: dict
    ran_at: datetime


class OptimizationRunListResponse(BaseModel):
    items: list[OptimizationRunResponse]
    total: int
    page: int
    page_size: int


class OptimizationRunDetail(OptimizationRunResponse):
    """Extended detail — includes per-campaign breakdown."""
    pass


# ---------------------------------------------------------------------------
# Internal schemas (not exposed via API, used between service layers)
# ---------------------------------------------------------------------------


class CampaignClassification(str, Enum):
    IMMATURE = "immature"
    EARLY_STAGE = "early_stage"
    MATURE = "mature"


class CampaignEvaluation(BaseModel):
    """Internal: represents one campaign's aggregated data for evaluation."""

    campaign_id: uuid.UUID
    publication_id: uuid.UUID
    meta_ad_id: str
    days_active: int
    total_impressions: int
    total_clicks: int
    total_spend_cents: int
    total_conversions: int
    ctr: float
    cpc_cents: float
    cost_per_conversion_cents: float
    conversion_rate: float
    roas: float
    budget_daily_cents: int
    status: str
    published_at: datetime


class CampaignFitnessResult(BaseModel):
    """Internal: fitness score output for one campaign."""

    campaign_id: uuid.UUID
    classification: CampaignClassification
    raw_scores: dict
    normalized_scores: dict
    weighted_score: float
    confidence_factor: float
    final_score: float


class KillDecision(BaseModel):
    """Internal: kill decision for one campaign."""

    campaign_id: uuid.UUID
    publication_id: uuid.UUID
    tier: int
    reason: str
    action: str
    budget_daily_cents: int


class DuplicateDecision(BaseModel):
    """Internal: duplication decision for one winner campaign."""

    campaign_id: uuid.UUID
    proposal_id: uuid.UUID
    num_copies: int
    mutation_params: list[str]
    parent_budget_daily_cents: int
