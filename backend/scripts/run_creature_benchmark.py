#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.pioneer import extract_creature_with_pioneer  # noqa: E402


FIELDS = ["element", "archetype", "rarity"]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _load(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fixture_file:
        data = json.load(fixture_file)
    if not isinstance(data, list):
        raise ValueError("fixtures must be a JSON list")
    return data


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _contains_any(actual: list[str], expected: list[str]) -> bool:
    actual_text = " ".join(_norm(item) for item in actual)
    return any(_norm(item) and _norm(item) in actual_text for item in expected)


def _score_creature(creature: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for field in FIELDS:
        scores[field] = 1.0 if _norm(creature.get(field)) == _norm(expected.get(field)) else 0.0
    scores["abilities"] = 1.0 if _contains_any(creature.get("abilities", []), expected.get("abilities", [])) else 0.0
    scores["weaknesses"] = 1.0 if _contains_any(creature.get("weaknesses", []), expected.get("weaknesses", [])) else 0.0
    stat_scores = []
    for key, expected_value in expected.get("stats", {}).items():
        actual_value = creature.get("stats", {}).get(key)
        try:
            stat_scores.append(1.0 if abs(int(actual_value) - int(expected_value)) <= 10 else 0.0)
        except (TypeError, ValueError):
            stat_scores.append(0.0)
    scores["stats"] = mean(stat_scores) if stat_scores else 0.0
    scores["overall"] = mean(scores.values())
    return scores


def _call_openai_baseline(description: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    schema = {
        "element": "string",
        "archetype": "string",
        "rarity": "common|uncommon|rare|epic|legendary|mythic",
        "abilities": ["string"],
        "weaknesses": ["string"],
        "stats": {"hp": 1, "atk": 1, "def": 1, "speed": 1, "magic": 1},
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Extract a battle creature as compact JSON only. Use the provided keys exactly.",
            },
            {
                "role": "user",
                "content": f"Schema example: {json.dumps(schema)}\nCreature description: {description}",
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    request = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


async def _run(fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    live_openai = bool(os.getenv("OPENAI_API_KEY"))
    live_openai_used = False
    openai_errors = []
    rows = []
    for item in fixtures:
        started = time.perf_counter()
        creature = await extract_creature_with_pioneer(item["description"])
        elapsed_ms = max(1, int((time.perf_counter() - started) * 1000))
        creature_data = creature.model_dump(by_alias=True)
        expected = item["expected"]
        baseline_source = "saved"
        baseline = item.get("openaiBaseline", expected)
        if live_openai:
            try:
                baseline = _call_openai_baseline(item["description"])
                baseline_source = "live-openai"
                live_openai_used = True
            except (RuntimeError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, OSError) as exc:
                openai_errors.append({"id": item.get("id"), "error": str(exc)})
        rows.append(
            {
                "id": item.get("id"),
                "description": item["description"],
                "providerMode": creature.providerStatus.mode,
                "baselineSource": baseline_source,
                "pioneer": {
                    "name": creature.name,
                    "element": creature.element,
                    "archetype": creature.archetype,
                    "rarity": creature.rarity,
                    "abilities": creature.abilities,
                    "weaknesses": creature.weaknesses,
                    "stats": creature_data["stats"],
                    "latencyMs": creature.latencyMs,
                    "fallback": creature.fallback,
                },
                "scores": _score_creature(creature_data, expected),
                "baselineScores": _score_creature(baseline, expected),
                "elapsedMs": elapsed_ms,
            }
        )
    field_scores: dict[str, float] = {}
    for key in ["element", "archetype", "rarity", "abilities", "weaknesses", "stats", "overall"]:
        field_scores[key] = round(mean(row["scores"][key] for row in rows), 3)
    baseline_scores: dict[str, float] = {}
    for key in ["element", "archetype", "rarity", "abilities", "weaknesses", "stats", "overall"]:
        baseline_scores[key] = round(mean(row["baselineScores"][key] for row in rows), 3)
    latencies = [row["pioneer"]["latencyMs"] for row in rows]
    mode = "pioneer-vs-live-openai" if live_openai_used else "pioneer-vs-saved-openai-baseline"
    return {
        "mode": mode,
        "openai": {
            "usedLive": live_openai_used,
            "model": OPENAI_MODEL if live_openai_used else None,
            "note": "OPENAI_API_KEY missing; saved OpenAI baseline fields used."
            if not live_openai
            else "Live OpenAI baseline used for at least one example; failed examples used saved baseline."
            if openai_errors
            else "Live OpenAI baseline used."
            if live_openai_used
            else "OPENAI_API_KEY detected but live OpenAI extraction failed; saved baseline fields used.",
            "errors": openai_errors,
        },
        "count": len(rows),
        "scores": field_scores,
        "baselineScores": baseline_scores,
        "latency": {
            "minMs": min(latencies) if latencies else 0,
            "avgMs": round(mean(latencies), 1) if latencies else 0,
            "maxMs": max(latencies) if latencies else 0,
        },
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--require-10", action="store_true")
    args = parser.parse_args()

    fixtures = _load(Path(args.fixtures))
    if args.require_10 and len(fixtures) != 10:
        print(json.dumps({"error": "expected exactly 10 fixtures", "count": len(fixtures)}), file=sys.stderr)
        return 1
    result = asyncio.run(_run(fixtures))
    if args.require_10 and result["count"] != 10:
        print(json.dumps({"error": "benchmark did not process 10 examples", "count": result["count"]}), file=sys.stderr)
        return 1
    if "scores" not in result or not result["scores"]:
        print(json.dumps({"error": "aggregate scores missing"}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
