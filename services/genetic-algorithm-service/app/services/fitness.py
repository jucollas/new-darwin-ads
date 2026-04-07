import uuid

import numpy as np
import structlog

from app.models.genetic import GeneticConfig
from app.schemas.genetic import (
    CampaignClassification,
    CampaignEvaluation,
    CampaignFitnessResult,
)

logger = structlog.get_logger()


class FitnessService:
    """
    Calculates fitness scores using min-max normalization and weighted sums.
    Two weight profiles: early-stage and full.
    Normalization is relative to the active portfolio — self-calibrating.
    """

    INVERSE_METRICS = {"cost_per_conversion", "cpc"}

    def calculate_fitness(
        self,
        evaluations: list[CampaignEvaluation],
        classifications: dict[uuid.UUID, CampaignClassification],
        config: GeneticConfig,
    ) -> list[CampaignFitnessResult]:
        """Calculate fitness results for all non-IMMATURE campaigns."""
        evaluable = [
            e
            for e in evaluations
            if classifications.get(e.campaign_id) != CampaignClassification.IMMATURE
        ]

        if not evaluable:
            return []

        # Compute min/max bounds from all evaluable campaigns
        all_metrics_keys = set()
        all_metrics_keys.update(config.fitness_weights.keys())
        all_metrics_keys.update(config.early_stage_weights.keys())

        metric_vectors = {
            e.campaign_id: self._get_metric_vector(e, all_metrics_keys)
            for e in evaluable
        }

        # Compute min/max per metric
        bounds: dict[str, tuple[float, float]] = {}
        for key in all_metrics_keys:
            values = [mv[key] for mv in metric_vectors.values() if key in mv]
            if values:
                bounds[key] = (float(np.min(values)), float(np.max(values)))

        results: list[CampaignFitnessResult] = []

        for evaluation in evaluable:
            classification = classifications[evaluation.campaign_id]
            raw_scores = metric_vectors[evaluation.campaign_id]

            # Normalize
            normalized: dict[str, float] = {}
            for key, value in raw_scores.items():
                if key in bounds:
                    min_val, max_val = bounds[key]
                    inverse = key in self.INVERSE_METRICS
                    normalized[key] = self._normalize_metric(
                        value, min_val, max_val, inverse=inverse
                    )

            # Select weight profile
            if classification == CampaignClassification.EARLY_STAGE:
                weights = config.early_stage_weights
            else:
                weights = config.fitness_weights

            weighted_score = self._compute_weighted_score(normalized, weights)
            confidence = self._compute_confidence_factor(evaluation, config)
            final_score = weighted_score * confidence

            results.append(
                CampaignFitnessResult(
                    campaign_id=evaluation.campaign_id,
                    classification=classification,
                    raw_scores=raw_scores,
                    normalized_scores=normalized,
                    weighted_score=round(weighted_score, 6),
                    confidence_factor=round(confidence, 6),
                    final_score=round(final_score, 6),
                )
            )

            logger.debug(
                "fitness_calculated",
                campaign_id=str(evaluation.campaign_id),
                classification=classification.value,
                weighted_score=round(weighted_score, 4),
                confidence=round(confidence, 4),
                final_score=round(final_score, 4),
            )

        return results

    def _normalize_metric(
        self, value: float, min_val: float, max_val: float, inverse: bool = False
    ) -> float:
        """Min-max normalization to [0, 1]."""
        if max_val == min_val:
            return 0.5

        norm = (value - min_val) / (max_val - min_val)
        if inverse:
            norm = 1.0 - norm

        return float(np.clip(norm, 0.0, 1.0))

    def _compute_weighted_score(
        self, normalized: dict[str, float], weights: dict[str, float]
    ) -> float:
        """Weighted sum of normalized metrics."""
        total_weight = 0.0
        total_score = 0.0

        for key, weight in weights.items():
            if key in normalized:
                total_score += weight * normalized[key]
                total_weight += weight

        if total_weight == 0:
            return 0.0

        # Re-normalize if some metrics were missing
        if abs(total_weight - 1.0) > 0.01:
            return total_score / total_weight

        return total_score

    def _compute_confidence_factor(
        self, evaluation: CampaignEvaluation, config: GeneticConfig
    ) -> float:
        """
        Confidence discount for immature data.
        confidence = min(1, impressions/min_impressions)
                   * min(1, days_active/7)
                   * min(1, spend/(target_cpa * min_spend_cpa_multiplier))
        """
        impression_factor = min(
            1.0, evaluation.total_impressions / max(1, config.min_impressions_to_evaluate)
        )
        days_factor = min(1.0, evaluation.days_active / 7.0)

        spend_threshold = config.target_cpa_cents * config.min_spend_cpa_multiplier
        spend_factor = min(
            1.0,
            evaluation.total_spend_cents / max(1, spend_threshold),
        )

        return impression_factor * days_factor * spend_factor

    def _get_metric_vector(
        self, evaluation: CampaignEvaluation, keys: set[str]
    ) -> dict[str, float]:
        """Map weight profile keys to actual evaluation fields."""
        mapping = {
            "roas": evaluation.roas,
            "conversion_rate": evaluation.conversion_rate,
            "cost_per_conversion": evaluation.cost_per_conversion_cents,
            "ctr": evaluation.ctr,
            "cpc": evaluation.cpc_cents,
            "impressions": float(evaluation.total_impressions),
        }
        return {k: v for k, v in mapping.items() if k in keys}
