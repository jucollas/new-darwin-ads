from fastapi import APIRouter, HTTPException, status

from app.schemas.ai import (
    GenerateProposalsRequest,
    GenerateProposalsResponse,
    MutateProposalRequest,
    MutateProposalResponse,
)
from app.services.gpt_service import GPTService

router = APIRouter(tags=["ai-generation"])


@router.post("/generate/proposals", response_model=GenerateProposalsResponse)
async def generate_proposals(data: GenerateProposalsRequest):
    """
    Generate 3 ad proposals using GPT.
    Internal service communication only — no JWT required.
    """
    try:
        service = GPTService()
        result = await service.generate_proposals(
            user_prompt=data.user_prompt,
            business_context=data.business_context.model_dump() if data.business_context else None,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI generation failed: {str(e)}",
        )


@router.post("/generate/mutate", response_model=MutateProposalResponse)
async def mutate_proposal(data: MutateProposalRequest):
    """
    Mutate an existing proposal (used by genetic algorithm service).
    Internal endpoint — no JWT required.
    """
    try:
        service = GPTService()
        result = await service.mutate_proposal(
            original_proposal=data.original_proposal.model_dump(),
            mutation_rate=data.mutation_rate,
            campaign_context=data.campaign_context,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI mutation failed: {str(e)}",
        )
