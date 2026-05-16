import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from app.models.creature import Creature
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from app.models.creature import Creature


STYLE_PHRASE = "dynamic fantasy battle card art, full body creature, dramatic arena lighting, clean background"
DEFAULT_MODEL_ID = "fal-ai/flux/dev"
LORA_MODEL_ID = "fal-ai/flux-lora"
FAL_TIMEOUT_SECONDS = 45


@dataclass(frozen=True)
class FalSpriteResult:
    visual_url: str
    provider_status: dict[str, Any]
    latency_ms: int
    prompt: str


def build_sprite_prompt(creature: Creature) -> str:
    abilities = ", ".join(creature.abilities[:3])
    weaknesses = ", ".join(creature.weaknesses[:2])
    return (
        f"{creature.name}, {creature.element} {creature.archetype}. "
        f"Signature abilities: {abilities}. Weak to {weaknesses}. "
        f"{STYLE_PHRASE}"
    )


def _extract_image_url(payload: dict[str, Any]) -> str | None:
    images = payload.get("images")
    if isinstance(images, list) and images:
        first_image = images[0]
        if isinstance(first_image, dict) and isinstance(first_image.get("url"), str):
            return first_image["url"]

    image = payload.get("image")
    if isinstance(image, dict) and isinstance(image.get("url"), str):
        return image["url"]

    if isinstance(payload.get("url"), str):
        return payload["url"]

    return None


def generate_fal_sprite(creature: Creature) -> FalSpriteResult:
    api_key = os.getenv("FAL_KEY")
    lora_url = os.getenv("FAL_LORA_URL")
    model_id = os.getenv("FAL_MODEL_ID") or (LORA_MODEL_ID if lora_url else DEFAULT_MODEL_ID)
    prompt = build_sprite_prompt(creature)
    started = time.perf_counter()

    if not api_key:
        raise RuntimeError("FAL_KEY is not configured")

    body: dict[str, Any] = {
        "prompt": prompt,
        "image_size": "square_hd",
        "num_images": 1,
        "enable_safety_checker": True,
    }
    lora_status = "none"
    if lora_url:
        body["loras"] = [{"path": lora_url, "scale": 1.0}]
        lora_status = "active"

    request = Request(
        f"https://fal.run/{model_id}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=FAL_TIMEOUT_SECONDS) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"fal request failed: {error.code} {detail[:240]}") from error
    except URLError as error:
        raise RuntimeError(f"fal request failed: {error.reason}") from error

    result = json.loads(response_body)
    visual_url = _extract_image_url(result)
    if not visual_url:
        raise RuntimeError("fal response did not include an image url")

    latency_ms = max(1, int((time.perf_counter() - started) * 1000))
    return FalSpriteResult(
        visual_url=visual_url,
        provider_status={
            "provider": "fal",
            "mode": "live",
            "modelId": model_id,
            "status": "ready",
            "lora": lora_status,
        },
        latency_ms=latency_ms,
        prompt=prompt,
    )
