import random
import uuid

import httpx
import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.genetic import GeneticConfig, OptimizationRun
from app.schemas.genetic import CampaignClassification
from app.services.crossover import CrossoverService
from app.services.duplication_manager import DuplicationManager
from app.services.evaluation import EvaluationService
from app.services.fitness import FitnessService
from app.services.kill_manager import KillManager
from app.services.mutation import MutationService
from shared.celery_app.config import celery_app

logger = structlog.get_logger()


class OptimizationOrchestrator:
    """
    Main entry point for the optimization cycle.
    Coordinates all services in the correct sequence.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.evaluation_service = EvaluationService()
        self.fitness_service = FitnessService()
        self.kill_manager = KillManager()
        self.duplication_manager = DuplicationManager()
        self.crossover_service = CrossoverService()
        self.mutation_service = MutationService()

    async def run_optimization(
        self, user_id: str, token: str = ""
    ) -> OptimizationRun:
        """Complete optimization cycle — 10 steps."""

        # Step 1: Load or auto-create GeneticConfig
        config = await self._get_or_create_config(user_id)

        # Step 2: Fetch and build evaluations
        evaluations = await self.evaluation_service.build_evaluations(
            user_id, token
        )

        if not evaluations:
            logger.info("optimization_no_campaigns", user_id=user_id)
            return await self._store_run(
                user_id=user_id,
                generation_number=await self._next_generation(user_id),
                campaigns_evaluated=0,
                campaigns_killed=[],
                campaigns_duplicated=[],
                fitness_scores={},
            )

        # Step 3: Classify each campaign
        classifications = {}
        counts = {"immature": 0, "early_stage": 0, "mature": 0}
        for ev in evaluations:
            c = self.evaluation_service.classify_campaign(ev, config)
            classifications[ev.campaign_id] = c
            counts[c.value] += 1

        logger.info("classification_complete", **counts)

        # Step 4: Calculate fitness scores
        fitness_results = self.fitness_service.calculate_fitness(
            evaluations, classifications, config
        )

        campaigns_evaluated = len(
            [
                c
                for c in classifications.values()
                if c != CampaignClassification.IMMATURE
            ]
        )

        # Step 5: Generation number
        generation_number = await self._next_generation(user_id)

        # Step 6: Apply kill framework
        kill_decisions = self.kill_manager.evaluate_kills(
            evaluations, fitness_results, config
        )

        # Step 7: Execute kills
        killed_records = []
        for kd in kill_decisions:
            success = await self._execute_kill(kd, token)
            killed_records.append(
                {
                    "campaign_id": str(kd.campaign_id),
                    "publication_id": str(kd.publication_id),
                    "tier": kd.tier,
                    "reason": kd.reason,
                    "action": kd.action,
                    "executed": success,
                }
            )

        kill_ids = {kd.campaign_id for kd in kill_decisions}

        # Step 8: Select winners for duplication
        dup_decisions = self.duplication_manager.select_winners(
            evaluations,
            fitness_results,
            kill_ids,
            config,
            current_active_count=len(evaluations),
        )

        # Step 9: Execute duplications
        duplicated_records = []
        # Collect all winner fitness results for crossover pairing
        winner_ids = [d.campaign_id for d in dup_decisions]

        for dd in dup_decisions:
            for i, mutation_param in enumerate(dd.mutation_params):
                # Fetch original proposal
                proposal = await self._fetch_proposal(dd.campaign_id, token)
                if not proposal:
                    logger.warning(
                        "proposal_fetch_failed",
                        campaign_id=str(dd.campaign_id),
                    )
                    continue

                base = dict(proposal)

                # Crossover check
                if (
                    random.random() < config.crossover_rate
                    and len(winner_ids) > 1
                ):
                    other_id = random.choice(
                        [w for w in winner_ids if w != dd.campaign_id]
                    )
                    other_proposal = await self._fetch_proposal(other_id, token)
                    if other_proposal:
                        base = self.crossover_service.crossover(
                            base, other_proposal, config.crossover_rate
                        )

                # Mutation
                mutated = await self.mutation_service.mutate_proposal(
                    base, mutation_param, config.mutation_rate
                )

                # Create new campaign
                new_campaign_id = await self._create_campaign(
                    user_id=user_id,
                    parent_id=dd.campaign_id,
                    mutated_proposal=mutated,
                    mutation_field=mutation_param,
                    token=token,
                )

                duplicated_records.append(
                    {
                        "parent_id": str(dd.campaign_id),
                        "new_campaign_id": str(new_campaign_id)
                        if new_campaign_id
                        else None,
                        "mutation_field": mutation_param,
                        "copy_index": i + 1,
                    }
                )

        # Step 10: Store optimization run
        fitness_dict = {}
        for fr in fitness_results:
            fitness_dict[str(fr.campaign_id)] = {
                "classification": fr.classification.value,
                "final_score": fr.final_score,
                "weighted_score": fr.weighted_score,
                "confidence_factor": fr.confidence_factor,
                "raw_scores": fr.raw_scores,
                "normalized_scores": fr.normalized_scores,
            }

        run = await self._store_run(
            user_id=user_id,
            generation_number=generation_number,
            campaigns_evaluated=campaigns_evaluated,
            campaigns_killed=killed_records,
            campaigns_duplicated=duplicated_records,
            fitness_scores=fitness_dict,
        )

        # Dispatch notification
        try:
            celery_app.send_task(
                "tasks.notification_send",
                queue="notification_tasks",
                args=[
                    user_id,
                    "optimization_complete",
                    {
                        "generation": generation_number,
                        "evaluated": campaigns_evaluated,
                        "killed": len(killed_records),
                        "duplicated": len(duplicated_records),
                    },
                ],
            )
        except Exception as exc:
            logger.warning("notification_dispatch_failed", error=str(exc))

        logger.info(
            "optimization_complete",
            user_id=user_id,
            generation=generation_number,
            evaluated=campaigns_evaluated,
            killed=len(killed_records),
            duplicated=len(duplicated_records),
        )

        return run

    async def _get_or_create_config(self, user_id: str) -> GeneticConfig:
        """Load or auto-create GeneticConfig for user."""
        result = await self.db.execute(
            select(GeneticConfig).where(GeneticConfig.user_id == user_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            config = GeneticConfig(user_id=user_id)
            self.db.add(config)
            await self.db.flush()
            logger.info("config_auto_created", user_id=user_id)

        return config

    async def _next_generation(self, user_id: str) -> int:
        """Get next generation number for this user."""
        result = await self.db.execute(
            select(func.max(OptimizationRun.generation_number)).where(
                OptimizationRun.user_id == user_id
            )
        )
        last_gen = result.scalar_one_or_none()
        return (last_gen or 0) + 1

    async def _store_run(
        self,
        user_id: str,
        generation_number: int,
        campaigns_evaluated: int,
        campaigns_killed: list,
        campaigns_duplicated: list,
        fitness_scores: dict,
    ) -> OptimizationRun:
        """Persist OptimizationRun record."""
        run = OptimizationRun(
            user_id=user_id,
            generation_number=generation_number,
            campaigns_evaluated=campaigns_evaluated,
            campaigns_killed=campaigns_killed,
            campaigns_duplicated=campaigns_duplicated,
            fitness_scores=fitness_scores,
        )
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def _execute_kill(self, kd, token: str) -> bool:
        """Execute a kill decision via publishing-service."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if kd.action == "pause":
                    resp = await client.post(
                        f"{settings.PUBLISHING_SERVICE_URL}"
                        f"/api/v1/publish/publications/{kd.publication_id}/pause",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    resp.raise_for_status()
                else:
                    # reduce_budget_20 / reduce_budget_30 → pause for MVP
                    logger.info(
                        "budget_reduction_requested_mvp_pause",
                        campaign_id=str(kd.campaign_id),
                        action=kd.action,
                    )
                    resp = await client.post(
                        f"{settings.PUBLISHING_SERVICE_URL}"
                        f"/api/v1/publish/publications/{kd.publication_id}/pause",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    resp.raise_for_status()

            logger.info(
                "kill_executed",
                campaign_id=str(kd.campaign_id),
                action=kd.action,
            )
            return True
        except Exception as exc:
            logger.error(
                "kill_execution_failed",
                campaign_id=str(kd.campaign_id),
                error=str(exc),
            )
            return False

    async def _fetch_proposal(
        self, campaign_id: uuid.UUID, token: str
    ) -> dict | None:
        """Fetch the selected proposal from campaign-service."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{settings.CAMPAIGN_SERVICE_URL}"
                    f"/api/v1/campaigns/{campaign_id}/proposals",
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                proposals = resp.json()
                if isinstance(proposals, dict):
                    proposals = proposals.get("items", proposals.get("proposals", []))
                # Find selected proposal
                for p in proposals:
                    if p.get("is_selected"):
                        return p
                # Fallback to first
                return proposals[0] if proposals else None
        except Exception as exc:
            logger.error(
                "fetch_proposal_failed",
                campaign_id=str(campaign_id),
                error=str(exc),
            )
            return None

    async def _create_campaign(
        self,
        user_id: str,
        parent_id: uuid.UUID,
        mutated_proposal: dict,
        mutation_field: str,
        token: str,
    ) -> uuid.UUID | None:
        """Create a new campaign via campaign-service with mutated proposal."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{settings.CAMPAIGN_SERVICE_URL}/api/v1/campaigns",
                    json={
                        "user_prompt": (
                            f"Mutation of campaign {parent_id}: "
                            f"mutated {mutation_field}"
                        ),
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                new_id = data.get("id")
                logger.info(
                    "campaign_created",
                    parent_id=str(parent_id),
                    new_id=new_id,
                    mutation_field=mutation_field,
                )
                return uuid.UUID(new_id) if new_id else None
        except Exception as exc:
            logger.error(
                "campaign_creation_failed",
                parent_id=str(parent_id),
                error=str(exc),
            )
            return None
