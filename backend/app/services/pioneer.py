import hashlib
import json
import os
import re
import time
from collections import Counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.models.creature import Creature
from app.routes.fixtures import load_fixtures


PIONEER_MODEL_ID = os.getenv("PIONEER_MODEL_ID", "fastino/gliner2-base-v1")
PIONEER_API_URL = os.getenv("PIONEER_API_URL", "https://api.pioneer.ai/inference")
TOKEN_RE = re.compile(r"[a-z0-9]+")

CREATURE_SCHEMA = {
    "entities": ["element", "material", "ability", "weakness", "body_part", "weapon"],
    "classifications": [
        {
            "task": "archetype",
            "labels": ["rebirth duelist", "siege tank", "drain skirmisher", "control striker", "counter mage", "assassin", "guardian"],
        },
        {
            "task": "rarity",
            "labels": ["common", "uncommon", "rare", "epic", "legendary", "mythic"],
        },
        {
            "task": "combat_style",
            "labels": ["burst", "control", "tank", "drain", "counter", "skirmish"],
        },
    ],
    "structures": {
        "stats": {
            "hp": "integer",
            "atk": "integer",
            "def": "integer",
            "speed": "integer",
            "magic": "integer",
        }
    },
}

PIONEER_INFERENCE_SCHEMA = {
    "entities": CREATURE_SCHEMA["entities"],
    "classifications": CREATURE_SCHEMA["classifications"],
}

RARITIES = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]
ELEMENTS = [
    "fire",
    "water",
    "thunder",
    "glass",
    "moss",
    "shadow",
    "mirror",
    "clockwork",
    "ice",
    "light",
    "stone",
    "storm",
    "poison",
    "sunlight",
    "void",
]


def _tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


def _score_fixture(description_tokens: set[str], fixture: Creature) -> int:
    fixture_tokens = _tokens(
        " ".join(
            [
                fixture.id,
                fixture.name,
                fixture.description,
                fixture.element,
                fixture.archetype,
                fixture.rarity,
                " ".join(fixture.abilities),
                " ".join(fixture.weaknesses),
            ]
        )
    )
    weighted = Counter(description_tokens)
    for token in description_tokens:
        if token in fixture.name.lower():
            weighted[token] += 3
        if token in fixture.element.lower() or token in fixture.archetype.lower():
            weighted[token] += 2
    return sum(weighted[token] for token in fixture_tokens & description_tokens)


def _selected_fixture(description: str) -> tuple[Creature, int]:
    fixtures = load_fixtures()
    description_tokens = _tokens(description)
    selected = max(fixtures, key=lambda fixture: _score_fixture(description_tokens, fixture))
    return selected, _score_fixture(description_tokens, selected)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _text_values(raw: dict[str, Any], key: str) -> list[str]:
    values: list[str] = []
    result = raw.get("result", {}) if isinstance(raw.get("result"), dict) else {}
    data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
    containers = [raw, raw.get("entities", {}), raw.get("extraction", {}), result, data, data.get("entities", {})]
    for container in containers:
        if not isinstance(container, dict):
            continue
        for item in _as_list(container.get(key)):
            if isinstance(item, str):
                values.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("value") or item.get("label")
                if text:
                    values.append(str(text))
    return values


def _classification(raw: dict[str, Any], key: str, default: str) -> str:
    result = raw.get("result", {}) if isinstance(raw.get("result"), dict) else {}
    data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
    containers = [raw, raw.get("classifications", {}), raw.get("extraction", {}), result, data]
    for container in containers:
        if not isinstance(container, dict):
            continue
        value = container.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
        if isinstance(value, dict):
            text = value.get("label") or value.get("value") or value.get("text")
            if text:
                return str(text).strip().lower()
    return default


def _stat_from_text(description: str, stat: str, default: int) -> int:
    lowered = description.lower()
    boosts = {
        "hp": ["titan", "colossus", "giant", "armored", "ancient", "enduring"],
        "atk": ["blade", "fang", "weapon", "crush", "rending", "spear", "fist"],
        "def": ["shell", "shield", "armor", "stone", "guard", "fortress"],
        "speed": ["swift", "quick", "darting", "winged", "blink", "nimble"],
        "magic": ["spell", "arcane", "curse", "mirror", "psychic", "sorcery", "moon"],
    }
    penalties = {
        "hp": ["fragile", "glass"],
        "atk": ["gentle"],
        "def": ["fragile", "paper"],
        "speed": ["slow", "heavy"],
        "magic": ["mundane"],
    }
    value = default
    value += sum(8 for word in boosts[stat] if word in lowered)
    value -= sum(5 for word in penalties[stat] if word in lowered)
    return max(5, min(160, value))


def _stats(raw: dict[str, Any], description: str, fixture: Creature) -> dict[str, int]:
    raw_stats: Any = raw.get("stats")
    if not isinstance(raw_stats, dict):
        structures = raw.get("structures")
        if isinstance(structures, dict):
            raw_stats = structures.get("stats")
    output: dict[str, int] = {}
    fixture_stats = fixture.stats.model_dump(by_alias=True)
    for key, default in fixture_stats.items():
        value = raw_stats.get(key) if isinstance(raw_stats, dict) else None
        try:
            output[key] = max(1, int(value))
        except (TypeError, ValueError):
            output[key] = _stat_from_text(description, key, int(default))
    return output


def _title_from_description(description: str, element: str, archetype: str) -> str:
    tokens = [token for token in TOKEN_RE.findall(description.lower()) if token not in {"a", "an", "the", "that", "with", "and", "but"}]
    if len(tokens) >= 2:
        name = " ".join(tokens[:2])
    else:
        name = f"{element} {archetype.split()[0]}"
    return name.title()


def _stable_id(description: str) -> str:
    digest = hashlib.sha1(description.encode("utf-8")).hexdigest()[:10]
    return f"pioneer-{digest}"


def _first_or_default(values: list[str], default: str) -> str:
    return next((value.strip().lower() for value in values if value.strip()), default)


def _derive_element(description: str, raw: dict[str, Any], fixture: Creature) -> str:
    explicit = _first_or_default(_text_values(raw, "element"), "")
    if explicit:
        return explicit
    lowered = description.lower()
    for element in ELEMENTS:
        if element in lowered:
            return element
    return fixture.element


def _derive_weaknesses(description: str, raw: dict[str, Any], fixture: Creature) -> list[str]:
    values = [value.lower() for value in _text_values(raw, "weakness")]
    lowered = description.lower()
    fear_match = re.search(r"(?:fears?|weak(?:ness)?(?: to)?|vulnerable to|shatters under)\s+([a-z -]+)", lowered)
    if fear_match:
        values.append(fear_match.group(1).split(" but ")[0].split(" and ")[0].strip())
    return list(dict.fromkeys([value for value in values if value]))[:3] or fixture.weaknesses[:]


def _derive_abilities(description: str, raw: dict[str, Any], fixture: Creature) -> list[str]:
    values = _text_values(raw, "ability")
    lowered = description.lower()
    for pattern in [r"that ([a-z ]+?)(?: but| and|,|$)", r"with ([a-z ]+?)(?: but| and|,|$)"]:
        match = re.search(pattern, lowered)
        if match:
            values.append(match.group(1))
    titled = [value.strip().title() for value in values if value.strip()]
    return list(dict.fromkeys(titled))[:3] or fixture.abilities[:]


def _normalize_creature(description: str, raw: dict[str, Any], latency_ms: int) -> Creature:
    fixture, score = _selected_fixture(description)
    element = _derive_element(description, raw, fixture)
    archetype = _classification(raw, "archetype", fixture.archetype)
    rarity = _classification(raw, "rarity", fixture.rarity)
    if rarity not in RARITIES:
        rarity = fixture.rarity
    creature = fixture.model_copy(deep=True)
    creature.id = _stable_id(description)
    creature.name = _title_from_description(description, element, archetype)
    creature.description = description
    creature.element = element
    creature.archetype = archetype
    creature.rarity = rarity
    creature.stats = creature.stats.__class__.model_validate(_stats(raw, description, fixture))
    creature.abilities = _derive_abilities(description, raw, fixture)
    creature.weaknesses = _derive_weaknesses(description, raw, fixture)
    creature.providerStatus.provider = "pioneer"
    creature.providerStatus.mode = "live"
    creature.providerStatus.modelId = PIONEER_MODEL_ID
    creature.providerStatus.status = "ready"
    creature.rawExtraction = {
        "schema": CREATURE_SCHEMA,
        "pioneerResponse": raw,
        "fixtureBasis": {"id": fixture.id, "score": score},
    }
    creature.latencyMs = latency_ms
    creature.fallback = False
    return creature


def _fixture_fallback(description: str, started: float, reason: str) -> Creature:
    selected, score = _selected_fixture(description)
    creature = selected.model_copy(deep=True)
    creature.latencyMs = max(1, int((time.perf_counter() - started) * 1000))
    creature.fallback = True
    creature.providerStatus.provider = "pioneer"
    creature.providerStatus.mode = "fixture-fallback"
    creature.providerStatus.modelId = PIONEER_MODEL_ID
    creature.providerStatus.status = "fallback"
    creature.rawExtraction = {
        "input": description,
        "schema": CREATURE_SCHEMA,
        "selection": "keyword-overlap",
        "matchedFixtureId": selected.id,
        "matchedFixtureName": selected.name,
        "score": score,
        "reason": reason,
    }
    return creature


def _call_pioneer(description: str) -> dict[str, Any]:
    api_key = os.getenv("PIONEER_API_KEY")
    if not api_key:
        raise RuntimeError("PIONEER_API_KEY is not configured")
    payload = {
        "model_id": PIONEER_MODEL_ID,
        "text": description,
        "schema": PIONEER_INFERENCE_SCHEMA,
        "threshold": 0.35,
    }
    request = Request(
        PIONEER_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    with urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


async def extract_creature_with_pioneer(description: str) -> Creature:
    started = time.perf_counter()
    try:
        raw = _call_pioneer(description)
    except (RuntimeError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return _fixture_fallback(description, started, str(exc))
    latency_ms = max(1, int((time.perf_counter() - started) * 1000))
    return _normalize_creature(description, raw, latency_ms)
