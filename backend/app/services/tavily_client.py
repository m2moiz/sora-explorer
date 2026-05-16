import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LORE_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "lore.json"
TAVILY_URL = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")


def _load_fixtures() -> dict[str, Any]:
    with LORE_FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _domain(url: str) -> str:
    return url.split("//")[-1].split("/")[0]


def _fixture_lore(payload: dict[str, Any], started: float, reason: str) -> dict[str, Any]:
    fixtures = _load_fixtures()
    key = str(payload.get("element") or "").lower()
    fixture = fixtures.get(key) or fixtures.get("default")
    name = payload.get("name") or "this creature"
    weaknesses = ", ".join(payload.get("weaknesses") or []) or "unknown counters"
    citations = [
        {
            **citation,
            "domain": _domain(citation.get("url", "")),
        }
        for citation in fixture["citations"]
    ]
    return {
        "summary": fixture["summary"].format(name=name, weaknesses=weaknesses),
        "citations": citations,
        "providerStatus": {
            "provider": "tavily",
            "mode": "fixture-fallback",
            "modelId": "fixture-lore-v1",
            "status": "fallback",
        },
        "latencyMs": max(1, int((time.perf_counter() - started) * 1000)),
        "fallback": True,
        "raw": {"reason": reason, "fixtureKey": key if key in fixtures else "default"},
    }


def get_lore(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return _fixture_lore(payload, started, "TAVILY_API_KEY is not configured")

    query = " ".join(
        [
            str(payload.get("name") or "fantasy creature"),
            str(payload.get("element") or ""),
            "mythology elemental counters weaknesses",
            " ".join(payload.get("weaknesses") or []),
        ]
    )
    request = Request(
        TAVILY_URL,
        data=json.dumps(
            {
                "query": query,
                "search_depth": "basic",
                "max_results": 3,
                "include_answer": True,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return _fixture_lore(payload, started, str(exc))

    results = raw.get("results") or []
    citations = [
        {
            "title": item.get("title") or "Tavily result",
            "url": item.get("url") or "",
            "snippet": item.get("content") or item.get("snippet") or "",
            "domain": _domain(item.get("url") or ""),
        }
        for item in results[:3]
    ]
    if not citations:
        return _fixture_lore(payload, started, "Tavily returned no citations")
    return {
        "summary": raw.get("answer") or citations[0]["snippet"],
        "citations": citations,
        "providerStatus": {
            "provider": "tavily",
            "mode": "live",
            "modelId": "tavily-search",
            "status": "ready",
        },
        "latencyMs": max(1, int((time.perf_counter() - started) * 1000)),
        "fallback": False,
        "raw": raw,
    }
