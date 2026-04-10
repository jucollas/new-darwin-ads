import uuid

import numpy as np
import structlog

from app.models.genetic import GeneticConfig
from app.schemas.genetic import (
    CampaignEvaluation,
    CampaignFitnessResult,
    KillDecision,
)

logger = structlog.get_logger()


class KillManager:
    """
    Four-tier kill framework. Tiers applied in order (1->2->3->4).
    A campaign killed by an earlier tier is not re-evaluated by later tiers.
    """

    def evaluate_kills(
        self,
        evaluations: list[CampaignEvaluation],
        fitness_results: list[CampaignFitnessResult],
        config: GeneticConfig,
    ) -> list[KillDecision]:
        all_kills: list[KillDecision] = []
        killed_ids: set[uuid.UUID] = set()

        # Tier 1 — Emergency (any campaign, any maturity)
        tier1 = self._tier1_emergency(evaluations, config)
        all_kills.extend(tier1)
        killed_ids.update(k.campaign_id for k in tier1)

        remaining = [e for e in evaluations if e.campaign_id not in killed_ids]

        # Tier 2 — Early Creative (1000+ impressions)
        tier2 = self._tier2_early_creative(remaining, config)
        all_kills.extend(tier2)
        killed_ids.update(k.campaign_id for k in tier2)

        remaining = [e for e in remaining if e.campaign_id not in killed_ids]

        # Tier 3 — Performance (50+ clicks, sufficient spend)
        tier3 = self._tier3_performance(remaining, config)
        all_kills.extend(tier3)
        killed_ids.update(k.campaign_id for k in tier3)

        remaining = [e for e in remaining if e.campaign_id not in killed_ids]

        # Tier 4 — Graduated Response (mature, 7+ days)
        tier4 = self._tier4_graduated(remaining, config)
        all_kills.extend(tier4)

        logger.info(
            "kill_evaluation_complete",
            tier1=len(tier1),
            tier2=len(tier2),
            tier3=len(tier3),
            tier4=len(tier4),
            total=len(all_kills),
        )
        return all_kills

    def _tier1_emergency(
        self, evaluations: list[CampaignEvaluation], config: GeneticConfig
    ) -> list[KillDecision]:
        """Tier 1 — Emergency Kill: extreme CPA or zero clicks with high impressions."""
        kills: list[KillDecision] = []
        threshold_cpa = config.target_cpa_cents * config.emergency_kill_cpa_multiplier
        target_dollars = config.target_cpa_cents / 100

        for e in evaluations:
            reason = None

            # Zero conversions but spent more than emergency threshold
            if e.total_conversions == 0 and e.total_spend_cents > threshold_cpa:
                spend_dollars = e.total_spend_cents / 100
                reason = (
                    f"Zero conversions with ${spend_dollars:.2f} spend "
                    f"(exceeds {config.emergency_kill_cpa_multiplier:.0f}x "
                    f"target ${target_dollars:.2f})"
                )
            # CPA exceeds emergency multiplier
            elif (
                e.total_conversions > 0
                and e.cost_per_conversion_cents > threshold_cpa
            ):
                cpa_dollars = e.cost_per_conversion_cents / 100
                reason = (
                    f"CPA ${cpa_dollars:.2f} exceeds "
                    f"{config.emergency_kill_cpa_multiplier:.0f}x "
                    f"target ${target_dollars:.2f}"
                )
            # 2000+ impressions with zero clicks
            elif e.total_impressions >= 2000 and e.total_clicks == 0:
                reason = (
                    f"{e.total_impressions} impressions with 0 clicks"
                )

            if reason:
                kills.append(
                    KillDecision(
                        campaign_id=e.campaign_id,
                        publication_id=e.publication_id,
                        tier=1,
                        reason=reason,
                        action="pause",
                        budget_daily_cents=e.budget_daily_cents,
                    )
                )
                logger.info(
                    "tier1_emergency_kill",
                    campaign_id=str(e.campaign_id),
                    reason=reason,
                )

        return kills

    def _tier2_early_creative(
        self, evaluations: list[CampaignEvaluation], config: GeneticConfig
    ) -> list[KillDecision]:
        """Tier 2 — Early Creative Kill: CTR below floor or bottom percentile."""
        kills: list[KillDecision] = []

        eligible = [e for e in evaluations if e.total_impressions >= 1000]
        if not eligible:
            return kills

        ctrs = [e.ctr for e in eligible]

        # Percentile threshold
        percentile_threshold = float(
            np.percentile(ctrs, config.kill_percentile_bottom * 100)
        )

        for e in eligible:
            reason = None

            if e.ctr < config.ctr_absolute_floor:
                reason = (
                    f"CTR {e.ctr*100:.1f}% below "
                    f"{config.ctr_absolute_floor*100:.1f}% floor"
                )
            elif e.ctr < percentile_threshold:
                reason = (
                    f"CTR {e.ctr*100:.1f}% in bottom "
                    f"{config.kill_percentile_bottom*100:.0f}% "
                    f"(threshold: {percentile_threshold*100:.1f}%)"
                )

            if reason:
                kills.append(
                    KillDecision(
                        campaign_id=e.campaign_id,
                        publication_id=e.publication_id,
                        tier=2,
                        reason=reason,
                        action="pause",
                        budget_daily_cents=e.budget_daily_cents,
                    )
                )
                logger.info(
                    "tier2_creative_kill",
                    campaign_id=str(e.campaign_id),
                    reason=reason,
                )

        return kills

    def _tier3_performance(
        self, evaluations: list[CampaignEvaluation], config: GeneticConfig
    ) -> list[KillDecision]:
        """Tier 3 — Performance Kill: expensive CPA or outlier CPC."""
        kills: list[KillDecision] = []
        min_spend = config.target_cpa_cents * config.min_spend_cpa_multiplier

        eligible = [
            e
            for e in evaluations
            if e.total_clicks >= 50 and e.total_spend_cents >= min_spend
        ]

        if not eligible:
            return kills

        # Portfolio medians
        cpcs = [e.cpc_cents for e in eligible]
        conv_rates = [e.conversion_rate for e in eligible]
        median_cpc = float(np.median(cpcs))
        median_conv_rate = float(np.median(conv_rates))

        cpa_threshold = config.target_cpa_cents * 1.5
        target_dollars = config.target_cpa_cents / 100

        for e in eligible:
            reason = None

            # CPA > 1.5x target for 7+ days
            if (
                e.cost_per_conversion_cents > cpa_threshold
                and e.days_active >= 7
                and e.total_conversions > 0
            ):
                cpa_dollars = e.cost_per_conversion_cents / 100
                reason = (
                    f"CPA ${cpa_dollars:.2f} > 1.5x target "
                    f"${target_dollars:.2f} for {e.days_active} days"
                )
            # CPC > 2x median AND conversion rate below median
            elif (
                e.cpc_cents > 2 * median_cpc
                and e.conversion_rate < median_conv_rate
                and median_cpc > 0
            ):
                reason = (
                    f"CPC ${e.cpc_cents/100:.2f} > 2x median "
                    f"${median_cpc/100:.2f} with conversion rate "
                    f"{e.conversion_rate*100:.1f}% below median "
                    f"{median_conv_rate*100:.1f}%"
                )

            if reason:
                kills.append(
                    KillDecision(
                        campaign_id=e.campaign_id,
                        publication_id=e.publication_id,
                        tier=3,
                        reason=reason,
                        action="pause",
                        budget_daily_cents=e.budget_daily_cents,
                    )
                )
                logger.info(
                    "tier3_performance_kill",
                    campaign_id=str(e.campaign_id),
                    reason=reason,
                )

        return kills

    def _tier4_graduated(
        self, evaluations: list[CampaignEvaluation], config: GeneticConfig
    ) -> list[KillDecision]:
        """Tier 4 — Graduated Response: budget reduction or pause for mature campaigns."""
        kills: list[KillDecision] = []

        eligible = [
            e
            for e in evaluations
            if e.days_active >= 7 and e.total_conversions >= 50
        ]

        target_dollars = config.target_cpa_cents / 100

        for e in eligible:
            if e.cost_per_conversion_cents <= 0:
                continue

            recent_cpa = e.cost_per_conversion_cents
            pause_threshold = config.target_cpa_cents * 1.5
            reduce_threshold = (
                config.target_cpa_cents * config.graduated_cpa_threshold
            )

            if recent_cpa > pause_threshold:
                cpa_dollars = recent_cpa / 100
                kills.append(
                    KillDecision(
                        campaign_id=e.campaign_id,
                        publication_id=e.publication_id,
                        tier=4,
                        reason=(
                            f"CPA ${cpa_dollars:.2f} > 1.5x target "
                            f"${target_dollars:.2f} (persistent)"
                        ),
                        action="pause",
                        budget_daily_cents=e.budget_daily_cents,
                    )
                )
            elif recent_cpa > reduce_threshold:
                cpa_dollars = recent_cpa / 100
                kills.append(
                    KillDecision(
                        campaign_id=e.campaign_id,
                        publication_id=e.publication_id,
                        tier=4,
                        reason=(
                            f"CPA ${cpa_dollars:.2f} > "
                            f"{config.graduated_cpa_threshold:.1f}x target "
                            f"${target_dollars:.2f}"
                        ),
                        action="reduce_budget_20",
                        budget_daily_cents=e.budget_daily_cents,
                    )
                )

        return kills
