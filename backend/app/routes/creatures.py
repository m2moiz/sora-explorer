from fastapi import APIRouter

from app.models.creature import Creature, CreatureExtractRequest
from app.services.pioneer import extract_creature_with_pioneer


router = APIRouter(prefix="/api/creature", tags=["creatures"])


@router.post("/extract", response_model=Creature)
async def extract_creature(payload: CreatureExtractRequest) -> Creature:
    return await extract_creature_with_pioneer(payload.description)
