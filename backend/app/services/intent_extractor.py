"""Pioneer GLiNER2 intent extractor for Sora the Explorer.

Multi-task schema: extracts game-intent classifications (action, intent)
and entities (target, element, modifier) from player spoken phrases.

Falls back to keyword fixture when PIONEER_API_KEY is unset or call fails.
"""

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.models.dungeon import IntentExtraction, ProviderStatus

PIONEER_INTENT_MODEL_ID = os.getenv("PIONEER_INTENT_MODEL_ID", "fastino/gliner2-base-v1")
PIONEER_API_URL = os.getenv("PIONEER_API_URL", "https://api.pioneer.ai/inference")

INTENT_SCHEMA = {
    "entities": ["target", "element", "modifier"],
    "classifications": [
        {
            "task": "action",
            "labels": [
                "attack", "defend", "cast", "open", "ask", "buy",
                "heal", "flee", "greet", "take", "use", "summon",
            ],
        },
        {
            "task": "intent",
            "labels": [
                "combat", "merchant", "healer", "interact", "defense", "magic",
            ],
        },
    ],
    "threshold": 0.4,
}

# Phrase-based fixture fallbacks for common game phrases
_PHRASE_FIXTURES: list[tuple[list[str], dict[str, str]]] = [
    (["cuanto", "cuesta", "precio", "how much", "cost"], {"action": "ask", "target": "item", "intent": "merchant"}),
    (["detente", "stop", "halt", "pare", "parar"], {"action": "attack", "target": "enemy", "intent": "combat"}),
    (["hola", "hello", "greet", "buenos"], {"action": "greet", "target": "npc", "intent": "interact"}),
    (["hasta", "luego", "goodbye", "bye", "adios"], {"action": "greet", "target": "boss", "intent": "interact"}),
    (["attack", "ataca", "hit", "strike", "fight"], {"action": "attack", "target": "enemy", "intent": "combat"}),
    (["defend", "block", "escudo", "shield"], {"action": "defend", "target": "self", "intent": "defense"}),
    (["heal", "cure", "curar", "medic"], {"action": "heal", "target": "self", "intent": "healer"}),
    (["open", "abrir", "unlock", "door"], {"action": "open", "target": "door", "intent": "interact"}),
    (["buy", "comprar", "purchase", "sell"], {"action": "buy", "target": "item", "intent": "merchant"}),
    (["cast", "spell", "magia", "magic"], {"action": "cast", "target": "enemy", "intent": "magic"}),
]


def _fixture_match(text: str) -> dict[str, str]:
    lowered = text.lower()
    best_score = 0
    best_match = {"action": "interact", "target": "unknown", "intent": "interact"}
    for keywords, extraction in _PHRASE_FIXTURES:
        score = sum(1 for kw in keywords if kw in lowered)
        if score > best_score:
            best_score = score
            best_match = extraction
    return best_match


def _extract_from_response(raw: dict[str, Any]) -> IntentExtraction:
    """Parse Pioneer /inference response into IntentExtraction."""
    result = raw.get("result", raw)
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            result = {}

    classifications: dict[str, Any] = {}
    entities: dict[str, Any] = {}

    # Handle nested result.data structure
    if isinstance(result, dict):
        data = result.get("data", result)
        if isinstance(data, dict):
            classifications = data.get("classifications", {})
            entities = data.get("entities", {})
        # Also try top-level
        if not classifications:
            classifications = result.get("classifications", {})
        if not entities:
            entities = result.get("entities", {})

    def _get_class(key: str) -> str | None:
        val = classifications.get(key)
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            return val.get("label") or val.get("value")
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("label") or first.get("text")
        return None

    def _get_entity(key: str) -> str | None:
        val = entities.get(key)
        if isinstance(val, str):
            return val
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("text") or first.get("value")
        return None

    return IntentExtraction(
        action=_get_class("action"),
        intent=_get_class("intent"),
        target=_get_entity("target"),
        element=_get_entity("element"),
        modifier=_get_entity("modifier"),
    )


def _call_pioneer(text: str) -> dict[str, Any]:
    api_key = os.getenv("PIONEER_API_KEY")
    if not api_key:
        raise RuntimeError("PIONEER_API_KEY not set")
    payload = {
        "model_id": PIONEER_INTENT_MODEL_ID,
        "text": text,
        "schema": INTENT_SCHEMA,
        "threshold": 0.4,
    }
    req = Request(
        PIONEER_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    with urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def extract_intent(text: str) -> dict[str, Any]:
    """Extract game intent from player text.

    Returns:
        extraction: IntentExtraction dict
        providerStatus: ProviderStatus dict
        latencyMs: int
        fallback: bool
    """
    started = time.perf_counter()

    try:
        raw = _call_pioneer(text)
        latency_ms = max(1, int((time.perf_counter() - started) * 1000))
        extraction = _extract_from_response(raw)
        # If extraction has nothing useful, augment from fixture
        if not extraction.action and not extraction.intent:
            fixture = _fixture_match(text)
            extraction = IntentExtraction(**{**fixture, **extraction.model_dump(exclude_none=True)})
        provider_status = ProviderStatus(
            provider="pioneer",
            mode="live",
            modelId=PIONEER_INTENT_MODEL_ID,
            status="ready",
        )
        return {
            "extraction": extraction.model_dump(),
            "providerStatus": provider_status.model_dump(),
            "latencyMs": latency_ms,
            "fallback": False,
            "rawResponse": raw,
        }
    except (RuntimeError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        latency_ms = max(1, int((time.perf_counter() - started) * 1000))
        fixture = _fixture_match(text)
        extraction = IntentExtraction(**fixture)
        provider_status = ProviderStatus(
            provider="pioneer",
            mode="fixture-fallback",
            modelId=PIONEER_INTENT_MODEL_ID,
            status="fallback",
        )
        return {
            "extraction": extraction.model_dump(),
            "providerStatus": provider_status.model_dump(),
            "latencyMs": latency_ms,
            "fallback": True,
            "reason": str(exc),
        }
