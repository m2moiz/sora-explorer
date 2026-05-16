import time
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

try:
    from app.models.creature import Creature
    from app.routes.fixtures import fixture_by_id, load_fixtures
    from app.services.fal_client import build_sprite_prompt, generate_fal_sprite
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from app.models.creature import Creature
    from app.routes.fixtures import fixture_by_id, load_fixtures
    from app.services.fal_client import build_sprite_prompt, generate_fal_sprite


router = APIRouter(prefix="/api/creature", tags=["sprites"])


class SpriteRequest(BaseModel):
    description: str | None = None
    creature: Creature | dict[str, Any] | None = None


def _as_payload(creature: Creature) -> dict[str, Any]:
    return creature.model_dump(by_alias=True)


def _fallback_visual(creature: Creature) -> tuple[str, str, str]:
    fixture = fixture_by_id(creature.id)
    if fixture is None:
        fixture = next((item for item in load_fixtures() if item.element.lower() == creature.element.lower()), None)

    visual_url = creature.visualUrl or (fixture.visualUrl if fixture else "")
    visual_gradient = creature.visualGradient or (fixture.visualGradient if fixture else "")
    if not visual_url and not visual_gradient:
        visual_gradient = "linear-gradient(135deg, #111827 0%, #f8fafc 48%, #d97706 100%)"

    matched_id = fixture.id if fixture else "generated-default-gradient"
    return visual_url, visual_gradient, matched_id


def _coerce_creature(payload: SpriteRequest | Creature) -> Creature:
    if isinstance(payload, Creature):
        return payload
    if isinstance(payload.creature, Creature):
        return payload.creature
    creature_data = payload.creature if isinstance(payload.creature, dict) else {}
    fixtures = load_fixtures()
    name = str(creature_data.get("name") or "").lower()
    element = str(creature_data.get("element") or "").lower()
    fixture = next((item for item in fixtures if item.name.lower() == name), None)
    if fixture is None and element:
        fixture = next((item for item in fixtures if item.element.lower() == element), None)
    if fixture is None:
        fixture = fixtures[0]
    merged = fixture.model_dump(by_alias=True)
    merged.update({key: value for key, value in creature_data.items() if value is not None})
    if payload.description:
        merged["description"] = payload.description
    return Creature.model_validate(merged)


@router.post("/sprite")
async def create_sprite(payload: SpriteRequest | Creature) -> dict[str, Any]:
    creature = _coerce_creature(payload)
    started = time.perf_counter()
    payload = _as_payload(creature)
    prompt = build_sprite_prompt(creature)

    try:
        result = generate_fal_sprite(creature)
        payload["visualUrl"] = result.visual_url
        payload["providerStatus"] = result.provider_status
        payload["latencyMs"] = result.latency_ms
        payload["fallback"] = False
        payload["rawExtraction"] = {
            **deepcopy(payload.get("rawExtraction") or {}),
            "sprite": {
                "provider": "fal",
                "prompt": result.prompt,
                "fallback": False,
            },
        }
        return payload
    except Exception as error:
        visual_url, visual_gradient, matched_id = _fallback_visual(creature)
        payload["visualUrl"] = visual_url
        payload["visualGradient"] = visual_gradient
        payload["providerStatus"] = {
            "provider": "fal",
            "mode": "fixture-fallback",
            "modelId": "fixture-visual-gradient-v1",
            "status": "fallback",
            "lora": "pending",
        }
        payload["latencyMs"] = max(1, int((time.perf_counter() - started) * 1000))
        payload["fallback"] = True
        payload["rawExtraction"] = {
            **deepcopy(payload.get("rawExtraction") or {}),
            "sprite": {
                "provider": "fal",
                "prompt": prompt,
                "fallback": True,
                "matchedFixtureId": matched_id,
                "reason": str(error),
            },
        }
        return payload
