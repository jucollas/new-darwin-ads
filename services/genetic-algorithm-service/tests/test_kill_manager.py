import uuid
from datetime import datetime, timezone

import pytest

from app.schemas.genetic import (
    CampaignClassification,
    CampaignEvaluation,
    CampaignFitnessResult,
)
from app.services.kill_manager import KillManager


def _make_eval(**kwargs) -> CampaignEvaluation:
    defaults = dict(
        campaign_id=uuid.uuid4(),
        publication_id=uuid.uuid4(),
        meta_ad_id="meta_123",
        days_active=10,
        total_impressions=5000,
        total_clicks=100,
        total_spend_cents=3000,
        total_conversions=20,
        ctr=0.02,
        cpc_cents=30.0,
        cost_per_conversion_cents=150.0,
        conversion_rate=0.2,
        roas=4.0,
        budget_daily_cents=500,
        status="published",
        published_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return CampaignEvaluation(**defaults)


def _make_config():
    """Create a config-like object without SQLAlchemy instrumentation."""

    class FakeConfig:
        target_cpa_cents = 140
        emergency_kill_cpa_multiplier = 3.0
        kill_percentile_bottom = 0.20
        ctr_absolute_floor = 0.005
        min_spend_cpa_multiplier = 2.0
        graduated_cpa_threshold = 1.2
        min_impressions_to_evaluate = 1000
        min_days_active = 3

    return FakeConfig()


def _make_fitness(campaign_id, classification=CampaignClassification.MATURE):
    return CampaignFitnessResult(
        campaign_id=campaign_id,
        classification=classification,
        raw_scores={},
        normalized_scores={},
        weighted_score=0.5,
        confidence_factor=1.0,
        final_score=0.5,
    )


class TestKillManager:
    def setup_method(self):
        self.km = KillManager()
        self.config = _make_config()

    def test_tier1_emergency_kill_high_cpa(self):
        ev = _make_eval(
            cost_per_conversion_cents=500,
            total_conversions=5,
            total_spend_cents=2500,
        )
        kills = self.km._tier1_emergency([ev], self.config)
        # threshold = 140 * 3 = 420. CPA=500 > 420
        assert len(kills) == 1
        assert kills[0].tier == 1
        assert kills[0].action == "pause"

    def test_tier1_emergency_kill_zero_clicks(self):
        ev = _make_eval(
            total_impressions=2500,
            total_clicks=0,
            ctr=0.0,
        )
        kills = self.km._tier1_emergency([ev], self.config)
        assert len(kills) == 1
        assert "0 clicks" in kills[0].reason

    def test_tier1_no_kill_immature(self):
        ev = _make_eval(
            total_impressions=100,
            total_clicks=0,
            ctr=0.0,
        )
        kills = self.km._tier1_emergency([ev], self.config)
        # 100 < 2000 impressions, so no zero-clicks kill
        assert len(kills) == 0

    def test_tier1_zero_conversions_high_spend(self):
        ev = _make_eval(
            total_conversions=0,
            cost_per_conversion_cents=0,
            total_spend_cents=500,  # > 140*3=420
        )
        kills = self.km._tier1_emergency([ev], self.config)
        assert len(kills) == 1
        assert "Zero conversions" in kills[0].reason

    def test_tier2_ctr_absolute_floor(self):
        ev = _make_eval(
            ctr=0.003,
            total_impressions=1500,
        )
        kills = self.km._tier2_early_creative([ev], self.config)
        assert len(kills) == 1
        assert "floor" in kills[0].reason

    def test_tier2_bottom_percentile(self):
        evals = []
        for i in range(10):
            evals.append(
                _make_eval(
                    ctr=0.005 + i * 0.002,  # 0.5% to 2.3%
                    total_impressions=2000,
                )
            )
        kills = self.km._tier2_early_creative(evals, self.config)
        # bottom 20% = 2 campaigns
        assert len(kills) == 2
        killed_ctrs = {k.campaign_id for k in kills}
        # The two lowest CTR campaigns should be killed
        assert evals[0].campaign_id in killed_ctrs
        assert evals[1].campaign_id in killed_ctrs

    def test_tier2_not_applied_under_1000_impressions(self):
        ev = _make_eval(
            ctr=0.001,
            total_impressions=800,
        )
        kills = self.km._tier2_early_creative([ev], self.config)
        assert len(kills) == 0

    def test_tier3_expensive_cpa(self):
        ev = _make_eval(
            cost_per_conversion_cents=250,
            total_conversions=10,
            total_clicks=60,
            total_spend_cents=500,  # > 140 * 2.0 = 280
            days_active=10,
        )
        kills = self.km._tier3_performance([ev], self.config)
        # threshold = 140 * 1.5 = 210. CPA=250 > 210, days=10 >= 7
        assert len(kills) == 1

    def test_tier3_gate_blocks_low_clicks(self):
        ev = _make_eval(
            cost_per_conversion_cents=500,
            total_clicks=30,  # < 50 gate
            total_spend_cents=500,
        )
        kills = self.km._tier3_performance([ev], self.config)
        assert len(kills) == 0

    def test_tier4_graduated_pause(self):
        ev = _make_eval(
            cost_per_conversion_cents=220,  # > 140*1.5=210
            total_conversions=60,
            days_active=14,
        )
        kills = self.km._tier4_graduated([ev], self.config)
        assert len(kills) == 1
        assert kills[0].action == "pause"

    def test_tier4_graduated_budget_reduction(self):
        ev = _make_eval(
            cost_per_conversion_cents=175,  # > 140*1.2=168, < 140*1.5=210
            total_conversions=60,
            days_active=14,
        )
        kills = self.km._tier4_graduated([ev], self.config)
        assert len(kills) == 1
        assert kills[0].action == "reduce_budget_20"

    def test_tiers_are_sequential(self):
        # A campaign killed by Tier 1 should not appear in Tier 2
        ev = _make_eval(
            total_impressions=2500,
            total_clicks=0,
            ctr=0.0,
        )
        fitness = [_make_fitness(ev.campaign_id)]
        kills = self.km.evaluate_kills([ev], fitness, self.config)
        tier_counts = {}
        for k in kills:
            tier_counts[k.tier] = tier_counts.get(k.tier, 0) + 1
        # Should only be killed once (Tier 1)
        assert len(kills) == 1
        assert kills[0].tier == 1

    def test_no_kills_healthy_portfolio(self):
        evals = [
            _make_eval(
                ctr=0.02,
                cost_per_conversion_cents=100,
                total_conversions=30,
                total_clicks=60,
                total_spend_cents=3000,
                days_active=5,
                total_impressions=3000,
            )
            for _ in range(5)
        ]
        fitness = [_make_fitness(e.campaign_id) for e in evals]
        kills = self.km.evaluate_kills(evals, fitness, self.config)
        assert len(kills) == 0
