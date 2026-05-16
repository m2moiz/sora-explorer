from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.tavily_client import get_lore


router = APIRouter(prefix="/api/creature", tags=["lore"])


class LoreRequest(BaseModel):
    name: str
    element: str | None = None
    abilities: list[str] = []
    weaknesses: list[str] = []


@router.post("/lore")
async def creature_lore(payload: LoreRequest) -> dict[str, Any]:
    return get_lore(payload.model_dump())
