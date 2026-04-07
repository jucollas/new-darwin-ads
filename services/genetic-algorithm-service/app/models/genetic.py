import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from shared.database.session import Base


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    __table_args__ = {"schema": "genetic_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(index=True)
    generation_number: Mapped[int]
    campaigns_evaluated: Mapped[int]
    campaigns_duplicated: Mapped[list] = mapped_column(JSON)
    campaigns_killed: Mapped[list] = mapped_column(JSON)
    fitness_scores: Mapped[dict] = mapped_column(JSON)
    ran_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


class GeneticConfig(Base):
    __tablename__ = "genetic_configs"
    __table_args__ = {"schema": "genetic_schema"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(unique=True)

    # --- Evaluation gates ---
    min_impressions_to_evaluate: Mapped[int] = mapped_column(default=1000)
    min_days_active: Mapped[int] = mapped_column(default=3)
    min_spend_cpa_multiplier: Mapped[float] = mapped_column(default=2.0)
    target_cpa_cents: Mapped[int] = mapped_column(default=140)

    # --- Fitness function weights (full evaluation) ---
    fitness_weights: Mapped[dict] = mapped_column(JSON, default={
        "roas": 0.30,
        "conversion_rate": 0.25,
        "cost_per_conversion": 0.20,
        "ctr": 0.15,
        "cpc": 0.10,
    })

    # --- Early-stage weights ---
    early_stage_weights: Mapped[dict] = mapped_column(JSON, default={
        "ctr": 0.35,
        "cpc": 0.25,
        "cost_per_conversion": 0.20,
        "impressions": 0.20,
    })

    # --- Kill thresholds ---
    emergency_kill_cpa_multiplier: Mapped[float] = mapped_column(default=3.0)
    kill_percentile_bottom: Mapped[float] = mapped_column(default=0.20)
    ctr_absolute_floor: Mapped[float] = mapped_column(default=0.005)
    max_frequency_prospecting: Mapped[float] = mapped_column(default=3.0)
    graduated_cpa_threshold: Mapped[float] = mapped_column(default=1.2)

    # --- Duplicate/scale thresholds ---
    duplicate_min_days_stable: Mapped[int] = mapped_column(default=7)
    duplicate_min_weekly_conversions: Mapped[int] = mapped_column(default=30)
    duplicate_max_cpa_ratio: Mapped[float] = mapped_column(default=1.2)
    duplicate_min_roas: Mapped[float] = mapped_column(default=3.0)
    max_budget_increase_pct: Mapped[float] = mapped_column(default=0.20)
    budget_increase_interval_days: Mapped[int] = mapped_column(default=3)
    duplicates_per_winner: Mapped[int] = mapped_column(default=3)

    # --- GA parameters ---
    mutation_rate: Mapped[float] = mapped_column(default=0.15)
    crossover_rate: Mapped[float] = mapped_column(default=0.80)
    elitism_count: Mapped[int] = mapped_column(default=2)
    max_active_campaigns: Mapped[int] = mapped_column(default=10)

    # --- Mutation priorities ---
    mutation_priorities: Mapped[list] = mapped_column(JSON, default=[
        "target_audience",
        "image_prompt",
        "copy_text",
        "welcome_message",
    ])
