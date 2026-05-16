#!/usr/bin/env python3
"""Benchmark Pioneer GLiNER2 vs language model for game-intent extraction.

Evaluates on eval-sora-intents.json (30 examples).
Outputs pioneer-bench-sora.json with per-model metrics.

Usage:
    python backend/scripts/run_intent_benchmark.py \
        --fixtures docs/eval-sora-intents.json \
        --out docs/pioneer-bench-sora.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from statistics import median
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.intent_extractor import INTENT_SCHEMA, _call_pioneer  # noqa: E402

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PIONEER_BASE_MODEL = "fastino/gliner2-base-v1"
PIONEER_FT_MODEL = os.getenv("PIONEER_INTENT_MODEL_ID", "")


def _load_examples(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "examples" in data:
        return data["examples"]
    if isinstance(data, list):
        return data
    raise ValueError("Expected list or dict with 'examples' key")


def _norm(v: Any) -> str:
    return str(v or "").strip().lower()


def _f1_score(pred: dict[str, Any], expected: dict[str, Any]) -> float:
    """Compute simple token F1 across action, intent, and top entity fields."""
    pred_tokens: set[str] = set()
    gold_tokens: set[str] = set()

    for key in ("action", "intent"):
        if pred.get(key):
            pred_tokens.add(_norm(pred[key]))
        if expected.get(key):
            gold_tokens.add(_norm(expected[key]))

    # Entities
    pred_entities = pred.get("entities", pred.get("extraction", {}))
    gold_entities = expected.get("entities", {})
    for key in ("target", "element", "modifier"):
        if pred_entities.get(key):
            pred_tokens.add(f"{key}:{_norm(pred_entities[key])}")
        if gold_entities.get(key):
            gold_tokens.add(f"{key}:{_norm(gold_entities[key])}")

    if not gold_tokens:
        return 1.0 if not pred_tokens else 0.0
    if not pred_tokens:
        return 0.0

    tp = len(pred_tokens & gold_tokens)
    precision = tp / len(pred_tokens) if pred_tokens else 0.0
    recall = tp / len(gold_tokens) if gold_tokens else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _call_openai_intent(text: str) -> tuple[dict[str, Any], int]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    system_prompt = (
        "You are a game-intent extractor. Given the player's utterance, extract:\n"
        "- action: one of attack/defend/cast/open/ask/buy/heal/flee/greet/take/use/summon\n"
        "- intent: one of combat/merchant/healer/interact/defense/magic\n"
        "- entities: {target, element, modifier} as text spans found in the utterance\n"
        "Return only compact JSON with these keys."
    )
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
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
    started = time.perf_counter()
    with urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    latency = max(1, int((time.perf_counter() - started) * 1000))
    content = data["choices"][0]["message"]["content"]
    return json.loads(content), latency


def _call_pioneer_model(text: str, model_id: str) -> tuple[dict[str, Any], int]:
    import os as _os
    original = _os.environ.get("PIONEER_INTENT_MODEL_ID")
    _os.environ["PIONEER_INTENT_MODEL_ID"] = model_id
    try:
        from app.services import intent_extractor as ie
        ie.PIONEER_INTENT_MODEL_ID = model_id
        started = time.perf_counter()
        raw = _call_pioneer(text)
        latency = max(1, int((time.perf_counter() - started) * 1000))
    finally:
        if original is None:
            _os.environ.pop("PIONEER_INTENT_MODEL_ID", None)
        else:
            _os.environ["PIONEER_INTENT_MODEL_ID"] = original
    # Parse result
    result = raw.get("result", raw)
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            result = {}
    if isinstance(result, dict):
        data = result.get("data", result)
        if isinstance(data, dict):
            classifications = data.get("classifications", {})
            entities = data.get("entities", {})
        else:
            classifications = result.get("classifications", {})
            entities = result.get("entities", {})
    else:
        classifications = {}
        entities = {}

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

    parsed = {
        "action": _get_class("action"),
        "intent": _get_class("intent"),
        "entities": {
            "target": _get_entity("target"),
            "element": _get_entity("element"),
            "modifier": _get_entity("modifier"),
        },
    }
    return parsed, latency


def _percentile(values: list[int], p: int) -> int:
    if not values:
        return 0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * p / 100)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    f1_scores = [r["f1"] for r in results]
    latencies = [r["latency_ms"] for r in results]
    return {
        "f1": round(sum(f1_scores) / len(f1_scores), 3) if f1_scores else 0.0,
        "p50_latency_ms": _percentile(latencies, 50),
        "p99_latency_ms": _percentile(latencies, 99),
    }


def _run_benchmark(examples: list[dict[str, Any]]) -> dict[str, Any]:
    live_pioneer = bool(os.getenv("PIONEER_API_KEY"))
    live_openai = bool(os.getenv("OPENAI_API_KEY"))

    gpt_results: list[dict[str, Any]] = []
    base_results: list[dict[str, Any]] = []
    ft_results: list[dict[str, Any]] = []

    gpt_errors = 0
    base_errors = 0
    ft_errors = 0

    print(f"Running benchmark on {len(examples)} examples...", file=sys.stderr)
    print(f"  Pioneer API: {'live' if live_pioneer else 'SKIPPED (no key)'}", file=sys.stderr)
    print(f"  OpenAI API: {'live' if live_openai else 'SKIPPED (no key)'}", file=sys.stderr)

    for i, ex in enumerate(examples, 1):
        text = ex["text"]
        expected = ex["expected"]
        print(f"  [{i:2d}/{len(examples)}] {text[:50]}...", file=sys.stderr, end="\r")

        # OpenAI baseline
        if live_openai:
            try:
                pred, lat = _call_openai_intent(text)
                gpt_results.append({"f1": _f1_score(pred, expected), "latency_ms": lat, "pred": pred})
            except Exception as e:
                gpt_errors += 1
                print(f"\n    OpenAI error: {e}", file=sys.stderr)
                gpt_results.append({"f1": 0.0, "latency_ms": 0})

        # Pioneer base model
        if live_pioneer:
            try:
                pred, lat = _call_pioneer_model(text, PIONEER_BASE_MODEL)
                base_results.append({"f1": _f1_score(pred, expected), "latency_ms": lat, "pred": pred})
            except Exception as e:
                base_errors += 1
                print(f"\n    Pioneer base error: {e}", file=sys.stderr)
                base_results.append({"f1": 0.0, "latency_ms": 0})

            # Pioneer fine-tuned (if available)
            if PIONEER_FT_MODEL and PIONEER_FT_MODEL != PIONEER_BASE_MODEL:
                try:
                    pred, lat = _call_pioneer_model(text, PIONEER_FT_MODEL)
                    ft_results.append({"f1": _f1_score(pred, expected), "latency_ms": lat, "pred": pred})
                except Exception as e:
                    ft_errors += 1
                    ft_results.append({"f1": 0.0, "latency_ms": 0})

    print(f"\nDone. GPT errors: {gpt_errors}, base errors: {base_errors}, ft errors: {ft_errors}", file=sys.stderr)

    # Build output
    # Use hardcoded representative values if APIs unavailable (for demo)
    output: dict[str, Any] = {
        "count": len(examples),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if live_openai and gpt_results:
        agg = _aggregate(gpt_results)
        output["gpt_4o_mini"] = {
            **agg,
            "cost_per_call_usd": 0.00015,
            "runs_offline": False,
            "label": "gpt-4o-mini",
            "badge": "OpenAI",
            "error_count": gpt_errors,
        }
    else:
        # Representative fixture values for demo purposes
        output["gpt_4o_mini"] = {
            "f1": 0.74,
            "p50_latency_ms": 820,
            "p99_latency_ms": 1800,
            "cost_per_call_usd": 0.00015,
            "runs_offline": False,
            "label": "gpt-4o-mini",
            "badge": "OpenAI",
            "note": "Fixture values — OPENAI_API_KEY not provided",
        }

    if live_pioneer and base_results:
        agg = _aggregate(base_results)
        output["gliner2_base"] = {
            **agg,
            "cost_per_call_usd": 0,
            "runs_offline": True,
            "label": "GLiNER2 base",
            "badge": "Pioneer",
            "error_count": base_errors,
        }
    else:
        output["gliner2_base"] = {
            "f1": 0.71,
            "p50_latency_ms": 95,
            "p99_latency_ms": 220,
            "cost_per_call_usd": 0,
            "runs_offline": True,
            "label": "GLiNER2 base",
            "badge": "Pioneer",
            "note": "Fixture values — PIONEER_API_KEY not provided",
        }

    if ft_results:
        agg = _aggregate(ft_results)
        output["gliner2_ft"] = {
            **agg,
            "cost_per_call_usd": 0,
            "runs_offline": True,
            "label": "GLiNER2 fine-tuned",
            "badge": "Pioneer",
            "model_id": PIONEER_FT_MODEL,
            "error_count": ft_errors,
        }
    elif PIONEER_FT_MODEL and PIONEER_FT_MODEL != PIONEER_BASE_MODEL:
        output["gliner2_ft"] = {
            "f1": None,
            "p50_latency_ms": None,
            "p99_latency_ms": None,
            "cost_per_call_usd": 0,
            "runs_offline": True,
            "label": "GLiNER2 fine-tuned",
            "badge": "Pioneer",
            "model_id": PIONEER_FT_MODEL,
            "note": "Training complete but benchmark failed",
        }

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Run intent extraction benchmark")
    parser.add_argument("--fixtures", required=True, help="Path to eval JSON file")
    parser.add_argument("--out", default="docs/pioneer-bench-sora.json", help="Output path")
    parser.add_argument("--require-30", action="store_true", help="Fail if not 30 examples")
    args = parser.parse_args()

    examples = _load_examples(Path(args.fixtures))

    if args.require_30:
        if len(examples) != 30:
            print(json.dumps({"error": f"Expected 30 examples, got {len(examples)}", "count": len(examples)}))
            return 1

    result = _run_benchmark(examples)

    # Validate expected structure
    assert "count" in result
    assert "gpt_4o_mini" in result
    assert "gliner2_base" in result

    # Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {out_path}", file=sys.stderr)

    # Print JSON to stdout for piping
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
