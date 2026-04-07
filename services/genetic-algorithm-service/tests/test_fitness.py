import uuid
from datetime import datetime, timezone

import pytest

from app.schemas.genetic import (
    CampaignClassification,
    CampaignEvaluation,
)
from app.services.fitness import FitnessService


def _make_eval(
    ctr=0.01,
    cpc_cents=50.0,
    cost_per_conversion_cents=200.0,
    conversion_rate=0.05,
    roas=3.0,
    total_impressions=5000,
    total_clicks=50,
    total_spend_cents=2500,
    total_conversions=10,
    days_active=10,
    budget_daily_cents=500,
    **kwargs,
) -> CampaignEvaluation:
    return CampaignEvaluation(
        campaign_id=kwargs.get("campaign_id", uuid.uuid4()),
        publication_id=uuid.uuid4(),
        meta_ad_id="meta_123",
        days_active=days_active,
        total_impressions=total_impressions,
        total_clicks=total_clicks,
        total_spend_cents=total_spend_cents,
        total_conversions=total_conversions,
        ctr=ctr,
        cpc_cents=cpc_cents,
        cost_per_conversion_cents=cost_per_conversion_cents,
        conversion_rate=conversion_rate,
        roas=roas,
        budget_daily_cents=budget_daily_cents,
        status="published",
        published_at=datetime.now(timezone.utc),
    )


def _make_config():
    """Create a config-like object without SQLAlchemy instrumentation."""

    class FakeConfig:
        target_cpa_cents = 140
        min_impressions_to_evaluate = 1000
        min_days_active = 3
        min_spend_cpa_multiplier = 2.0
        fitness_weights = {
            "roas": 0.30,
            "conversion_rate": 0.25,
            "cost_per_conversion": 0.20,
            "ctr": 0.15,
            "cpc": 0.10,
        }
        early_stage_weights = {
            "ctr": 0.35,
            "cpc": 0.25,
            "cost_per_conversion": 0.20,
            "impressions": 0.20,
        }

    return FakeConfig()


class TestFitnessService:
    def setup_method(self):
        self.service = FitnessService()
        self.config = _make_config()

    def test_normalize_metric_higher_is_better(self):
        result = self.service._normalize_metric(0.008, 0.002, 0.012, inverse=False)
        assert abs(result - 0.6) < 0.001

    def test_normalize_metric_lower_is_better(self):
        result = self.service._normalize_metric(50, 20, 100, inverse=True)
        assert abs(result - 0.625) < 0.001

    def test_normalize_metric_equal_min_max(self):
        result = self.service._normalize_metric(5.0, 5.0, 5.0)
        assert result == 0.5

    def test_weighted_score_full_evaluation(self):
        evals = [
            _make_eval(roas=5.0, conversion_rate=0.08, cost_per_conversion_cents=100, ctr=0.012, cpc_cents=30),
            _make_eval(roas=2.0, conversion_rate=0.03, cost_per_conversion_cents=300, ctr=0.006, cpc_cents=80),
            _make_eval(roas=3.5, conversion_rate=0.05, cost_per_conversion_cents=200, ctr=0.009, cpc_cents=55),
        ]
        classifications = {e.campaign_id: CampaignClassification.MATURE for e in evals}

        results = self.service.calculate_fitness(evals, classifications, self.config)
        assert len(results) == 3

        scores = {str(r.campaign_id): r.final_score for r in results}
        best_campaign = max(scores, key=scores.get)
        assert best_campaign == str(evals[0].campaign_id)

    def test_weighted_score_early_stage(self):
        evals = [
            _make_eval(ctr=0.015, cpc_cents=25, cost_per_conversion_cents=100, total_impressions=3000, days_active=5),
            _make_eval(ctr=0.005, cpc_cents=70, cost_per_conversion_cents=300, total_impressions=1500, days_active=5),
            _make_eval(ctr=0.010, cpc_cents=45, cost_per_conversion_cents=200, total_impressions=2000, days_active=5),
        ]
        classifications = {
            e.campaign_id: CampaignClassification.EARLY_STAGE for e in evals
        }

        results = self.service.calculate_fitness(evals, classifications, self.config)
        scores = {str(r.campaign_id): r.weighted_score for r in results}
        best = max(scores, key=scores.get)
        # Highest CTR should win in early stage (CTR weight = 0.35)
        assert best == str(evals[0].campaign_id)

    def test_confidence_factor_immature(self):
        ev = _make_eval(
            total_impressions=500,
            days_active=2,
            total_spend_cents=20,
        )
        confidence = self.service._compute_confidence_factor(ev, self.config)
        # 500/1000=0.5, 2/7=0.286, 20/280=0.071
        expected = 0.5 * (2 / 7) * (20 / 280)
        assert abs(confidence - expected) < 0.01

    def test_confidence_factor_mature(self):
        ev = _make_eval(
            total_impressions=5000,
            days_active=10,
            total_spend_cents=5000,
        )
        confidence = self.service._compute_confidence_factor(ev, self.config)
        assert confidence == 1.0

    def test_empty_portfolio(self):
        results = self.service.calculate_fitness([], {}, self.config)
        assert results == []

    def test_single_campaign(self):
        ev = _make_eval()
        classifications = {ev.campaign_id: CampaignClassification.MATURE}
        results = self.service.calculate_fitness([ev], classifications, self.config)
        assert len(results) == 1
        # Single campaign: all normalized to 0.5 (min == max)
        for v in results[0].normalized_scores.values():
            assert v == 0.5

    def test_immature_campaigns_excluded(self):
        evals = [
            _make_eval(days_active=1, total_impressions=100),
            _make_eval(days_active=10, total_impressions=5000),
        ]
        classifications = {
            evals[0].campaign_id: CampaignClassification.IMMATURE,
            evals[1].campaign_id: CampaignClassification.MATURE,
        }
        results = self.service.calculate_fitness(evals, classifications, self.config)
        assert len(results) == 1
        assert results[0].campaign_id == evals[1].campaign_id
