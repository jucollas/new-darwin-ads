"""
GPT service — handles all OpenAI API communication.

Uses the openai Python SDK (async client) with response_format=json_object.
Implements retry logic with exponential backoff.
"""

import asyncio
import json

import structlog
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError

from app.config import settings
from app.schemas.ai import (
    GenerateProposalsResponse,
    MutateProposalResponse,
    ProposalResponse,
    TargetAudienceResponse,
)
from app.services.prompt_templates import (
    SYSTEM_PROMPT_MUTATE,
    SYSTEM_PROMPT_PROPOSALS,
    build_user_prompt_mutate,
    build_user_prompt_proposals,
)

logger = structlog.get_logger()


class GPTService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT,
        )
        self.model = settings.OPENAI_MODEL

    async def generate_proposals(
        self,
        user_prompt: str,
        business_context: dict | None = None,
    ) -> GenerateProposalsResponse:
        """Generate 3 ad proposals using GPT. Retries up to 3 times on failure."""
        user_message = build_user_prompt_proposals(user_prompt, business_context)

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_PROPOSALS},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=settings.OPENAI_MAX_TOKENS,
                    temperature=settings.OPENAI_TEMPERATURE,
                )

                raw_content = response.choices[0].message.content
                parsed = json.loads(raw_content)

                proposals = self._validate_proposals(parsed)

                logger.info(
                    "proposals_generated",
                    model=self.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                    attempt=attempt + 1,
                )

                return GenerateProposalsResponse(
                    proposals=proposals,
                    model_used=self.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                )

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                last_error = e
                logger.warning("gpt_response_parse_error", error=str(e), attempt=attempt + 1)
                continue

            except RateLimitError as e:
                last_error = e
                logger.warning("gpt_rate_limit", attempt=attempt + 1)
                await asyncio.sleep(2 ** attempt)
                continue

            except APITimeoutError as e:
                last_error = e
                logger.warning("gpt_timeout", attempt=attempt + 1)
                continue

            except APIError as e:
                last_error = e
                logger.error("gpt_api_error", error=str(e), attempt=attempt + 1)
                if attempt == max_retries - 1:
                    raise
                continue

        raise RuntimeError(f"Failed to generate proposals after {max_retries} attempts: {last_error}")

    async def mutate_proposal(
        self,
        original_proposal: dict,
        mutation_rate: float = 0.15,
        campaign_context: str | None = None,
    ) -> MutateProposalResponse:
        """Mutate an existing proposal for the genetic algorithm."""
        user_message = build_user_prompt_mutate(original_proposal, mutation_rate, campaign_context)

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_MUTATE},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=settings.OPENAI_MAX_TOKENS,
                    temperature=min(settings.OPENAI_TEMPERATURE + mutation_rate, 1.5),
                )

                raw_content = response.choices[0].message.content
                parsed = json.loads(raw_content)

                mutated = self._validate_single_proposal(parsed["mutated_proposal"])
                mutations = parsed.get("mutations_applied", [])

                logger.info(
                    "proposal_mutated",
                    model=self.model,
                    mutation_rate=mutation_rate,
                    mutations_count=len(mutations),
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                )

                return MutateProposalResponse(
                    mutated_proposal=mutated,
                    mutations_applied=mutations,
                    model_used=self.model,
                )

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                last_error = e
                logger.warning("gpt_mutate_parse_error", error=str(e), attempt=attempt + 1)
                continue

            except (RateLimitError, APITimeoutError, APIError) as e:
                last_error = e
                logger.warning("gpt_mutate_error", error=str(e), attempt=attempt + 1)
                await asyncio.sleep(2 ** attempt)
                continue

        raise RuntimeError(f"Failed to mutate proposal after {max_retries} attempts: {last_error}")

    def _validate_proposals(self, parsed: dict) -> list[ProposalResponse]:
        """Validate and normalize GPT response into exactly 3 proposals."""
        raw_proposals = parsed.get("proposals", [])

        if not isinstance(raw_proposals, list) or len(raw_proposals) == 0:
            raise ValueError("GPT response missing 'proposals' array")

        proposals = []
        for raw in raw_proposals[:3]:
            proposals.append(self._validate_single_proposal(raw))

        while len(proposals) < 3:
            logger.warning("gpt_returned_fewer_proposals", count=len(proposals))
            last = proposals[-1].model_dump()
            last["copy_text"] = last["copy_text"] + " \u00a1Aprovecha ahora!"
            proposals.append(ProposalResponse(**last))

        return proposals

    def _validate_single_proposal(self, raw: dict) -> ProposalResponse:
        """Validate a single proposal dict into ProposalResponse."""
        audience = raw.get("target_audience", {})
        normalized_audience = TargetAudienceResponse(
            age_min=audience.get("age_min", 18),
            age_max=audience.get("age_max", 65),
            genders=audience.get("genders", ["male", "female"]),
            interests=audience.get("interests", ["general"]),
            locations=audience.get("locations", ["CO"]),
        )

        return ProposalResponse(
            copy_text=raw.get("copy_text", "")[:500],
            script=raw.get("script", ""),
            image_prompt=raw.get("image_prompt", "Professional product photography, clean background"),
            target_audience=normalized_audience,
            cta_type=raw.get("cta_type", "whatsapp_chat"),
            whatsapp_number=raw.get("whatsapp_number"),
        )
