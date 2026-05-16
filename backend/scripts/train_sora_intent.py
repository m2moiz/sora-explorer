#!/usr/bin/env python3
"""Pioneer intent-extractor training kickoff for Sora the Explorer.

Generates synthetic NER data, kicks off LoRA training on gliner2-base-v1, polls
to completion, then prints the trained model_id (which user pastes into .env as
PIONEER_INTENT_MODEL_ID).

Usage:
    backend/.venv/bin/python backend/scripts/train_sora_intent.py
    # (after env vars loaded)

Notes:
- Generates NER-only dataset (entities: target, element, modifier).
- Classification labels (action, intent) are NOT trained via Pioneer because
  /generate is single-task; classification head is applied at inference time
  with a fixed label set in the multi-task /inference schema.
- Per Pioneer agent: "Don't fine-tune for theater. Measure base first."
  This script trains anyway because the benchmark slide is stronger with three
  rows (GPT vs base vs fine-tuned), but the benchmark script also runs base+GPT
  comparison so we still ship something even if this fails.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv


# Load .env from repo root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API_KEY = os.environ.get("PIONEER_API_KEY")
BASE = os.environ.get("PIONEER_BASE_URL", "https://api.pioneer.ai").rstrip("/")
HEADERS = {"X-API-Key": API_KEY or "", "Content-Type": "application/json"}

if not API_KEY:
    print("ERROR: PIONEER_API_KEY not set in env", file=sys.stderr)
    sys.exit(1)


def post(path: str, body: dict) -> dict:
    r = httpx.post(f"{BASE}{path}", headers=HEADERS, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def get(path: str) -> dict:
    r = httpx.get(f"{BASE}{path}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def poll(path: str, terminal: set[str], every: int = 10, max_wait: int = 1800) -> dict:
    """Poll until status is in `terminal`. Returns final payload."""
    start = time.time()
    while True:
        elapsed = int(time.time() - start)
        if elapsed > max_wait:
            print(f"  ! Timeout after {elapsed}s", file=sys.stderr)
            return {"status": "timeout"}
        body = get(path)
        # Extract a nested status from various Pioneer response shapes.
        status = (
            body.get("status")
            or body.get("state")
            or (body.get("job", {}) or {}).get("status")
        )
        print(f"  [{elapsed:4d}s] status={status}")
        if status in terminal:
            return body
        time.sleep(every)


def main() -> None:
    print("=" * 60)
    print("Sora intent-extractor training pipeline")
    print("=" * 60)

    # ============================================================
    # STEP 1: Generate synthetic NER data
    # ============================================================
    print("\n[1/4] Generating synthetic NER data (target/element/modifier)...")
    gen_payload = {
        "task_type": "ner",
        "dataset_name": "sora-intent-ner-v1",
        "labels": ["target", "element", "modifier"],
        "num_examples": 300,
        "domain_description": (
            "Player utterances in a fantasy-roguelike language-learning game. "
            "Players speak short natural-language commands during combat, merchant "
            "interactions, healer encounters, traps, and boss fights. Examples: "
            "'I attack the dragon with fire', 'open the silver door please', "
            "'how much does this potion cost', 'I cast a shield spell carefully', "
            "'freeze the troll with ice', 'I throw a fireball at the goblin'. "
            "Entities: target (the noun being acted on - dragon, door, potion, goblin), "
            "element (fire/water/ice/lightning/magic/light/dark), modifier "
            "(adjectives or adverbs - silver, quickly, gently, three). "
            "Vary fantasy/medieval/modern/sci-fi settings. Avoid generic verbs."
        ),
    }
    gen_resp = post("/generate", gen_payload)
    gen_job_id = gen_resp.get("id") or gen_resp.get("job_id")
    print(f"  job_id={gen_job_id}")

    if not gen_job_id:
        print("ERROR: /generate did not return a job_id", file=sys.stderr)
        print(gen_resp, file=sys.stderr)
        sys.exit(1)

    # ============================================================
    # STEP 2: Poll until synth complete
    # ============================================================
    print("\n[2/4] Polling synth job to completion...")
    final = poll(
        f"/generate/jobs/{gen_job_id}",
        terminal={"complete", "completed", "failed", "succeeded", "ready"},
        every=5,
        max_wait=600,
    )
    if final.get("status") not in {"complete", "completed", "succeeded", "ready"}:
        print(f"ERROR: synth job ended with status {final.get('status')}", file=sys.stderr)
        sys.exit(1)
    print("  Synth data ready: sora-intent-ner-v1")

    # ============================================================
    # STEP 3: Kick off LoRA training
    # ============================================================
    print("\n[3/4] Kicking off LoRA training...")
    train_payload = {
        "model_name": "sora-intent-extractor-v1",
        "base_model": "fastino/gliner2-base-v1",
        "datasets": [{"name": "sora-intent-ner-v1"}],
        "training_type": "lora",
        "nr_epochs": 5,
        "learning_rate": 5e-5,
        "batch_size": 6,
    }
    train_resp = post("/felix/training-jobs", train_payload)
    training_job_id = train_resp.get("id") or train_resp.get("job_id")
    print(f"  training_job_id={training_job_id}")

    if not training_job_id:
        print("ERROR: /felix/training-jobs did not return an id", file=sys.stderr)
        print(train_resp, file=sys.stderr)
        sys.exit(1)

    # Persist immediately so user can use base model in parallel
    print(f"\n  >>> Set this in your .env (will be picked up by intent_extractor.py):")
    print(f"  PIONEER_INTENT_MODEL_ID={training_job_id}")

    # ============================================================
    # STEP 4: Poll training to completion
    # ============================================================
    print("\n[4/4] Polling training job (~5-15 min)...")
    final_train = poll(
        f"/felix/training-jobs/{training_job_id}",
        terminal={"complete", "completed", "failed", "succeeded", "ready", "cancelled"},
        every=20,
        max_wait=1800,
    )
    status = final_train.get("status")
    print(f"\n  Training final status: {status}")

    if status in {"complete", "completed", "succeeded", "ready"}:
        print(f"\n=== SUCCESS ===")
        print(f"Trained model_id: {training_job_id}")
        print(f"Add to .env: PIONEER_INTENT_MODEL_ID={training_job_id}")
        print(f"\nThen run the benchmark:")
        print(f"  backend/.venv/bin/python backend/scripts/run_intent_benchmark.py")
    else:
        print(f"\n=== FAILED / TIMEOUT ===")
        print("Fall back to base model: fastino/gliner2-base-v1")
        print("The benchmark script will still produce a 2-row slide (GPT vs base).")


if __name__ == "__main__":
    main()
