import uuid

import structlog

from app.models.genetic import GeneticConfig
from app.schemas.genetic import (
    CampaignClassification,
    CampaignEvaluation,
    CampaignFitnessResult,
    DuplicateDecision,
)

logger = structlog.get_logger()


class DuplicationManager:
    """
    Identifies winning campaigns eligible for duplication and
    prepares mutation parameters for each copy.
    """

    def select_winners(
        self,
        evaluations: list[CampaignEvaluation],
        fitness_results: list[CampaignFitnessResult],
        kill_ids: set[uuid.UUID],
        config: GeneticConfig,
        current_active_count: int | None = None,
    ) -> list[DuplicateDecision]:
        """
        Select campaigns eligible for duplication based on all criteria.
        """
        eval_map = {e.campaign_id: e for e in evaluations}
        fitness_map = {f.campaign_id: f for f in fitness_results}

        # Filter to candidates meeting all criteria
        candidates: list[CampaignFitnessResult] = []
        max_cpa = config.target_cpa_cents * config.duplicate_max_cpa_ratio

        for fr in fitness_results:
            if fr.campaign_id in kill_ids:
                continue
            if fr.classification != CampaignClassification.MATURE:
                continue

            ev = eval_map.get(fr.campaign_id)
            if not ev:
                continue

            # Days stable
            if ev.days_active < config.duplicate_min_days_stable:
                continue

            # Weekly conversions
            weekly_convs = (
                ev.total_conversions * 7 / max(1, ev.days_active)
            )
            if weekly_convs < config.duplicate_min_weekly_conversions:
                continue

            # CPA within ratio
            if (
                ev.total_conversions > 0
                and ev.cost_per_conversion_cents > max_cpa
            ):
                continue

            # ROAS threshold
            if ev.roas < config.duplicate_min_roas:
                continue

            candidates.append(fr)

        # Sort by final_score descending
        candidates.sort(key=lambda c: c.final_score, reverse=True)

        # Apply elitism — top N preserved, not duplicated
        if len(candidates) <= config.elitism_count:
            logger.info(
                "duplication_all_elite",
                candidates=len(candidates),
                elitism_count=config.elitism_count,
            )
            return []

        to_duplicate = candidates[config.elitism_count:]

        # Track active campaign count
        active_count = current_active_count or len(evaluations)
        decisions: list[DuplicateDecision] = []
        total_copies_planned = 0

        for fr in to_duplicate:
            ev = eval_map[fr.campaign_id]

            remaining_slots = (
                config.max_active_campaigns - active_count - total_copies_planned
            )
            copies_possible = min(config.duplicates_per_winner, remaining_slots)
            if copies_possible <= 0:
                logger.info(
                    "max_active_campaigns_reached",
                    max=config.max_active_campaigns,
                )
                break

            # Assign mutation params from priorities
            mutation_params = config.mutation_priorities[:copies_possible]

            decisions.append(
                DuplicateDecision(
                    campaign_id=fr.campaign_id,
                    proposal_id=ev.publication_id,  # will be resolved to actual proposal
                    num_copies=copies_possible,
                    mutation_params=mutation_params,
                )
            )
            total_copies_planned += copies_possible

            logger.info(
                "winner_selected_for_duplication",
                campaign_id=str(fr.campaign_id),
                final_score=fr.final_score,
                copies=copies_possible,
                mutations=mutation_params,
            )

        return decisions

    def prepare_mutation_payload(
        self,
        original_proposal: dict,
        mutation_param: str,
        config: GeneticConfig,
    ) -> dict:
        """Build mutation request body for the AI service."""
        return {
            "original_proposal": {
                "copy_text": original_proposal.get("copy_text", ""),
                "script": original_proposal.get("script", ""),
                "image_prompt": original_proposal.get("image_prompt", ""),
                "target_audience": original_proposal.get("target_audience", {}),
                "cta_type": original_proposal.get("cta_type", "whatsapp_chat"),
            },
            "mutate_field": mutation_param,
            "mutation_rate": config.mutation_rate,
            "context": {
                "market": "Colombia",
                "platform": "WhatsApp",
                "objective": "OUTCOME_ENGAGEMENT",
            },
        }
