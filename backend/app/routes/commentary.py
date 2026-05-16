from typing import Any

from fastapi import APIRouter

from app.services.openai_client import get_commentary


router = APIRouter(prefix="/api", tags=["commentary"])


@router.post("/commentary")
async def commentary(payload: dict[str, Any]) -> dict[str, Any]:
    return get_commentary(payload)
