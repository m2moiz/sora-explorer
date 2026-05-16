import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _fallback_commentary(payload: dict[str, Any], started: float, reason: str) -> dict[str, Any]:
    winner = payload.get("winner") or payload.get("winnerName") or "The challenger"
    turn_log = payload.get("turnLog") or payload.get("turns") or []
    first_turn = turn_log[0] if turn_log else "The arena opened with a decisive exchange"
    if isinstance(first_turn, dict):
        first_turn = f"{first_turn.get('attackerName', 'A creature')} used {first_turn.get('move', 'a strike')}"
    return {
        "commentary": f"{winner} takes the round after setting the tempo early. {first_turn}. The crowd gets a clean winner without waiting on live commentary.",
        "providerStatus": {
            "provider": "openai",
            "mode": "fixture-fallback",
            "modelId": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            "status": "fallback",
        },
        "latencyMs": max(1, int((time.perf_counter() - started) * 1000)),
        "fallback": True,
        "raw": {"reason": reason},
    }


def get_commentary(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if not api_key:
        return _fallback_commentary(payload, started, "OPENAI_API_KEY is not configured")

    winner = payload.get("winner") or payload.get("winnerName") or "the winner"
    turn_log = payload.get("turnLog") or payload.get("turns") or []
    request = Request(
        OPENAI_URL,
        data=json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Write concise fantasy sports commentary in one sentence."},
                    {"role": "user", "content": json.dumps({"winner": winner, "turnLog": turn_log})},
                ],
                "temperature": 0.7,
                "max_tokens": 80,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=12) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return _fallback_commentary(payload, started, str(exc))

    commentary = raw.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not commentary:
        return _fallback_commentary(payload, started, "OpenAI returned empty commentary")
    return {
        "commentary": commentary,
        "providerStatus": {
            "provider": "openai",
            "mode": "live",
            "modelId": model,
            "status": "ready",
        },
        "latencyMs": max(1, int((time.perf_counter() - started) * 1000)),
        "fallback": False,
        "raw": raw,
    }
