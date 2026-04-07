import uuid
from datetime import datetime, timezone

import pytest

from app.schemas.genetic import (
    CampaignClassification,
    CampaignEvaluation,
    CampaignFitnessResult,
)
from app.services.duplication_manager import DuplicationManager


def _make_eval(**kwargs) -> CampaignEvaluation:
    defaults = dict(
        campaign_id=uuid.uuid4(),
        publication_id=uuid.uuid4(),
        meta_ad_id="meta_123",
        days_active=14,
        total_impressions=10000,
        total_clicks=200,
        total_spend_cents=5000,
        total_conversions=80,
        ctr=0.02,
        cpc_cents=25.0,
        cost_per_conversion_cents=62.5,
        conversion_rate=0.4,
        roas=5.0,
        budget_daily_cents=500,
        status="published",
        published_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return CampaignEvaluation(**defaults)


def _make_fitness(
    campaign_id, final_score=0.8, classification=CampaignClassification.MATURE
) -> CampaignFitnessResult:
    return CampaignFitnessResult(
        campaign_id=campaign_id,
        classification=classification,
        raw_scores={"roas": 5.0, "ctr": 0.02},
        normalized_scores={"roas": 0.8, "ctr": 0.7},
        weighted_score=0.75,
        confidence_factor=1.0,
        final_score=final_score,
    )


def _make_config():
    """Create a config-like object without SQLAlchemy instrumentation."""

    class FakeConfig:
        target_cpa_cents = 140
        duplicate_min_days_stable = 7
        duplicate_min_weekly_conversions = 30
        duplicate_max_cpa_ratio = 1.2
        duplicate_min_roas = 3.0
        elitism_count = 2
        duplicates_per_winner = 3
        max_active_campaigns = 10
        mutation_rate = 0.15
        mutation_priorities = ["target_audience", "image_prompt", "copy_text"]

    return FakeConfig()


class TestDuplicationManager:
    def setup_method(self):
        self.dm = DuplicationManager()
        self.config = _make_config()

    def test_select_winners_all_criteria(self):
        ev = _make_eval()
        fr = _make_fitness(ev.campaign_id, final_score=0.9)
        # Need enough campaigns to exceed elitism
        ev2 = _make_eval()
        fr2 = _make_fitness(ev2.campaign_id, final_score=0.95)
        ev3 = _make_eval()
        fr3 = _make_fitness(ev3.campaign_id, final_score=0.85)

        decisions = self.dm.select_winners(
            [ev, ev2, ev3], [fr, fr2, fr3], set(), self.config, current_active_count=3
        )
        # elitism_count=2, so top 2 preserved, 3rd gets duplicated
        assert len(decisions) == 1
        assert decisions[0].campaign_id == ev3.campaign_id

    def test_exclude_killed_campaigns(self):
        ev = _make_eval()
        fr = _make_fitness(ev.campaign_id, final_score=0.9)
        ev2 = _make_eval()
        fr2 = _make_fitness(ev2.campaign_id, final_score=0.95)
        ev3 = _make_eval()
        fr3 = _make_fitness(ev3.campaign_id, final_score=0.85)

        kill_ids = {ev3.campaign_id}
        decisions = self.dm.select_winners(
            [ev, ev2, ev3], [fr, fr2, fr3], kill_ids, self.config, current_active_count=3
        )
        # ev3 killed, only ev and ev2 remain but both are elite
        assert len(decisions) == 0

    def test_elitism_preserves_top(self):
        evals = [_make_eval() for _ in range(5)]
        scores = [0.95, 0.90, 0.85, 0.80, 0.75]
        fitness = [
            _make_fitness(evals[i].campaign_id, final_score=scores[i])
            for i in range(5)
        ]

        decisions = self.dm.select_winners(
            evals, fitness, set(), self.config, current_active_count=5
        )
        # elitism_count=2, so top 2 preserved. 3 duplicated.
        duplicated_ids = {d.campaign_id for d in decisions}
        assert evals[0].campaign_id not in duplicated_ids  # top 1
        assert evals[1].campaign_id not in duplicated_ids  # top 2

    def test_max_active_campaigns_limit(self):
        evals = [_make_eval() for _ in range(5)]
        scores = [0.95, 0.90, 0.85, 0.80, 0.75]
        fitness = [
            _make_fitness(evals[i].campaign_id, final_score=scores[i])
            for i in range(5)
        ]
        # current_active=8, max=10, so only 2 slots
        self.config.max_active_campaigns = 10
        decisions = self.dm.select_winners(
            evals, fitness, set(), self.config, current_active_count=8
        )
        total_copies = sum(d.num_copies for d in decisions)
        assert total_copies <= 2

    def test_mutation_priority_assignment(self):
        evals = [_make_eval() for _ in range(4)]
        scores = [0.95, 0.90, 0.85, 0.80]
        fitness = [
            _make_fitness(evals[i].campaign_id, final_score=scores[i])
            for i in range(4)
        ]

        decisions = self.dm.select_winners(
            evals, fitness, set(), self.config, current_active_count=4
        )
        if decisions:
            assert decisions[0].mutation_params[0] == "target_audience"

    def test_no_winners_poor_portfolio(self):
        # All campaigns with ROAS below threshold
        evals = [_make_eval(roas=1.5) for _ in range(5)]
        fitness = [
            _make_fitness(evals[i].campaign_id, final_score=0.3)
            for i in range(5)
        ]
        decisions = self.dm.select_winners(
            evals, fitness, set(), self.config, current_active_count=5
        )
        assert len(decisions) == 0

    def test_low_roas_blocks_duplication(self):
        ev = _make_eval(roas=2.0)  # below 3.0 threshold
        fr = _make_fitness(ev.campaign_id, final_score=0.9)
        ev2 = _make_eval(roas=2.5)
        fr2 = _make_fitness(ev2.campaign_id, final_score=0.8)
        ev3 = _make_eval(roas=1.5)
        fr3 = _make_fitness(ev3.campaign_id, final_score=0.7)

        decisions = self.dm.select_winners(
            [ev, ev2, ev3], [fr, fr2, fr3], set(), self.config, current_active_count=3
        )
        assert len(decisions) == 0

    def test_low_weekly_conversions_blocks(self):
        # 80 conversions over 14 days = 40/week → passes
        # 10 conversions over 14 days = 5/week → fails
        ev = _make_eval(total_conversions=10, days_active=14)
        fr = _make_fitness(ev.campaign_id, final_score=0.9)
        ev2 = _make_eval(total_conversions=10, days_active=14)
        fr2 = _make_fitness(ev2.campaign_id, final_score=0.85)
        ev3 = _make_eval(total_conversions=10, days_active=14)
        fr3 = _make_fitness(ev3.campaign_id, final_score=0.8)

        decisions = self.dm.select_winners(
            [ev, ev2, ev3], [fr, fr2, fr3], set(), self.config, current_active_count=3
        )
        assert len(decisions) == 0
