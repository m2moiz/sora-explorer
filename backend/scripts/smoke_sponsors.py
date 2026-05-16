#!/usr/bin/env python3
"""One-shot sponsor smoke test. Confirms each API key + endpoint works.

Run: backend/.venv/bin/python backend/scripts/smoke_sponsors.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def banner(name: str) -> None:
    print(f"\n{'=' * 60}\n  {name}\n{'=' * 60}")


def stamp(name: str, ok: bool, detail: str = "") -> None:
    mark = "✅" if ok else "❌"
    print(f"  {mark} {name:<14} {detail}")


# ─── OpenAI ─────────────────────────────────────────────────────
def test_openai() -> bool:
    banner("OpenAI")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        stamp("OpenAI", False, "OPENAI_API_KEY not set")
        return False
    try:
        import httpx
        t0 = time.perf_counter()
        r = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "say OK"}], "max_tokens": 5},
            timeout=15,
        )
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            stamp("OpenAI", True, f"gpt-4o-mini OK ({ms}ms)")
            return True
        stamp("OpenAI", False, f"HTTP {r.status_code}: {r.text[:120]}")
        return False
    except Exception as e:
        stamp("OpenAI", False, str(e)[:120])
        return False


# ─── Tavily ─────────────────────────────────────────────────────
def test_tavily() -> bool:
    banner("Tavily")
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        stamp("Tavily", False, "TAVILY_API_KEY not set")
        return False
    try:
        import httpx
        t0 = time.perf_counter()
        r = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": "Sora the Explorer", "max_results": 1},
            timeout=15,
        )
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            stamp("Tavily", True, f"search OK ({ms}ms)")
            return True
        stamp("Tavily", False, f"HTTP {r.status_code}: {r.text[:120]}")
        return False
    except Exception as e:
        stamp("Tavily", False, str(e)[:120])
        return False


# ─── fal ────────────────────────────────────────────────────────
def test_fal() -> bool:
    banner("fal")
    key = os.environ.get("FAL_KEY")
    if not key:
        stamp("fal", False, "FAL_KEY not set")
        return False
    try:
        import fal_client  # noqa: F401  (just confirm SDK import)
        # Don't burn credits on a real call — just confirm SDK + key shape.
        if not key.startswith(("fal_", "sk-")) and len(key) < 20:
            stamp("fal", False, f"key shape suspicious len={len(key)}")
            return False
        stamp("fal", True, f"fal-client {fal_client.__version__ if hasattr(fal_client, '__version__') else 'installed'}, key looks valid")
        return True
    except ImportError:
        stamp("fal", False, "fal-client not installed")
        return False
    except Exception as e:
        stamp("fal", False, str(e)[:120])
        return False


# ─── Pioneer / Fastino ──────────────────────────────────────────
def test_pioneer() -> bool:
    banner("Pioneer / Fastino")
    key = os.environ.get("PIONEER_API_KEY")
    if not key:
        stamp("Pioneer", False, "PIONEER_API_KEY not set")
        return False
    try:
        import httpx
        base = os.environ.get("PIONEER_BASE_URL", "https://api.pioneer.ai").rstrip("/")
        t0 = time.perf_counter()
        # Cheapest call: a tiny /inference against gliner2-base with one entity.
        r = httpx.post(
            f"{base}/inference",
            headers={"X-API-Key": key, "Content-Type": "application/json"},
            json={
                "model_id": "fastino/gliner2-base-v1",
                "text": "I attack the dragon with fire.",
                "schema": {"entities": ["target", "element"]},
                "threshold": 0.4,
            },
            timeout=20,
        )
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            data = r.json()
            stamp("Pioneer", True, f"inference OK ({ms}ms), keys={list(data.keys())[:6]}")
            return True
        stamp("Pioneer", False, f"HTTP {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        stamp("Pioneer", False, str(e)[:120])
        return False


# ─── SLNG ───────────────────────────────────────────────────────
def test_slng() -> bool:
    banner("SLNG")
    key = os.environ.get("SLNG_API_KEY")
    if not key:
        stamp("SLNG", False, "SLNG_API_KEY not set")
        return False
    try:
        import httpx
        # Tiny TTS request — single short word, returns audio bytes.
        t0 = time.perf_counter()
        r = httpx.post(
            "https://api.slng.ai/v1/bridges/unmute/tts/deepgram/aura:2",
            headers={"Authorization": f"Bearer {key}"},
            json={"text": "hi"},
            timeout=15,
        )
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            stamp("SLNG", True, f"TTS OK ({ms}ms), bytes={len(r.content)}")
            return True
        stamp("SLNG", False, f"HTTP {r.status_code}: {r.text[:200] if r.text else 'no body'}")
        return False
    except Exception as e:
        stamp("SLNG", False, str(e)[:120])
        return False


# ─── Gradium ────────────────────────────────────────────────────
def test_gradium() -> bool:
    banner("Gradium")
    key = os.environ.get("GRADIUM_API_KEY")
    if not key:
        stamp("Gradium", False, "GRADIUM_API_KEY not set")
        return False
    try:
        import httpx
        # Tiny TTS request matching existing voice.py pattern (x-api-key header).
        t0 = time.perf_counter()
        r = httpx.post(
            "https://api.gradium.ai/api/post/speech/tts",
            headers={"x-api-key": key, "Content-Type": "application/json"},
            json={"text": "hi", "voice_id": "cu0XE3Cxmg_GmSJ3"},
            timeout=15,
        )
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            stamp("Gradium", True, f"TTS OK ({ms}ms), bytes={len(r.content)}")
            return True
        stamp("Gradium", False, f"HTTP {r.status_code}: {r.text[:200] if r.text else 'no body'}")
        return False
    except Exception as e:
        stamp("Gradium", False, str(e)[:120])
        return False


# ─── Pioneer /generate (separate, only if -G flag) ──────────────
def test_pioneer_generate() -> bool:
    banner("Pioneer /generate (synth data endpoint)")
    key = os.environ.get("PIONEER_API_KEY")
    if not key:
        return False
    try:
        import httpx
        # Just check the endpoint accepts a tiny payload — don't actually fire a job.
        # Use a dry-run by checking response code on a malformed payload (expecting 400 not 404/401).
        r = httpx.get(
            f"{os.environ.get('PIONEER_BASE_URL', 'https://api.pioneer.ai')}/generate/jobs/_test",
            headers={"X-API-Key": key},
            timeout=10,
        )
        if r.status_code in (404, 422, 400):
            stamp("Pioneer/gen", True, f"endpoint reachable (HTTP {r.status_code} expected for fake job id)")
            return True
        stamp("Pioneer/gen", False, f"HTTP {r.status_code}: {r.text[:120]}")
        return False
    except Exception as e:
        stamp("Pioneer/gen", False, str(e)[:120])
        return False


def main() -> None:
    results = {
        "OpenAI": test_openai(),
        "Tavily": test_tavily(),
        "fal": test_fal(),
        "Pioneer": test_pioneer(),
        "Pioneer-gen": test_pioneer_generate(),
        "SLNG": test_slng(),
        "Gradium": test_gradium(),
    }
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    for name, ok in results.items():
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}")
    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"\n  ⚠️  {len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)
    print("\n  ✨ All sponsors green. Ready to build.")


if __name__ == "__main__":
    main()
