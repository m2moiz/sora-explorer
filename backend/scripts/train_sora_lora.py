#!/usr/bin/env python3
"""fal flux-lora training kickoff for Sora the Explorer "uncanny edutainment" style.

Pipeline (all cloud-async, ~25min wallclock):
1. Generate 12 reference images via fal-ai/flux-schnell with consistent style prompt
2. Zip them
3. Upload zip + kick off flux-lora-fast-training with is_style=True
4. Print FAL_LORA_URL for .env

Usage:
    backend/.venv/bin/python backend/scripts/train_sora_lora.py
    # FAL_KEY must be set in .env
"""
from __future__ import annotations

import os
import sys
import time
import tempfile
import zipfile
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

FAL_KEY = os.environ.get("FAL_KEY")
if not FAL_KEY:
    print("ERROR: FAL_KEY not set", file=sys.stderr)
    sys.exit(1)

# Lazy import — only available after `pip install fal-client`
try:
    import fal_client  # type: ignore
except ImportError:
    print("ERROR: fal-client not installed. Run: backend/.venv/bin/pip install fal-client", file=sys.stderr)
    sys.exit(1)

# Auth via env (fal_client picks up FAL_KEY automatically)

STYLE_PROMPT_BASE = (
    "pixel art illustration in the style of early 2000s children's edutainment TV, "
    "flat saturated colors, thick black outlines, slightly uncanny proportions, "
    "{subject}, 1024x1024, centered composition, plain background, retro game aesthetic"
)

SUBJECTS = [
    "a jungle temple ruin",
    "a magic market stall under neon",
    "a sneaky fox character with a backpack",
    "a llama wearing a sombrero",
    "a treasure chest glowing softly",
    "a swamp at night with fireflies",
    "an animate backpack with friendly eyes",
    "a cat shopkeeper behind a counter",
    "a glowing key floating in midair",
    "a moonlit bodega convenience store",
    "a crayon-textured catacomb hallway",
    "a friendly ghost holding a lantern",
]


def gen_reference_image(subject: str, seed: int) -> str:
    """Generate one reference image via flux-schnell. Returns URL."""
    prompt = STYLE_PROMPT_BASE.format(subject=subject)
    res = fal_client.subscribe(
        "fal-ai/flux/schnell",
        arguments={
            "prompt": prompt,
            "image_size": "square_hd",
            "num_inference_steps": 4,
            "seed": seed,
        },
        with_logs=False,
    )
    return res["images"][0]["url"]


def download(url: str, dest: Path) -> None:
    with httpx.stream("GET", url, timeout=30) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=8192):
                f.write(chunk)


def main() -> None:
    print("=" * 60)
    print("Sora style LoRA training pipeline")
    print("=" * 60)

    # ============================================================
    # STEP 1: Generate 12 reference images
    # ============================================================
    print(f"\n[1/3] Generating {len(SUBJECTS)} reference images via flux-schnell...")
    workdir = Path(tempfile.mkdtemp(prefix="sora-lora-"))
    print(f"  workdir: {workdir}")
    image_paths: list[Path] = []
    for i, subject in enumerate(SUBJECTS):
        print(f"  [{i+1}/{len(SUBJECTS)}] {subject[:50]}...")
        try:
            url = gen_reference_image(subject, seed=i + 1)
            dest = workdir / f"ref_{i:02d}.png"
            download(url, dest)
            image_paths.append(dest)
            print(f"      saved: {dest.name}")
        except Exception as e:
            print(f"      FAILED: {e}", file=sys.stderr)

    if len(image_paths) < 4:
        print(f"ERROR: only {len(image_paths)} images generated, need >=4", file=sys.stderr)
        sys.exit(1)

    print(f"  Generated {len(image_paths)} images")

    # ============================================================
    # STEP 2: Zip and upload
    # ============================================================
    print("\n[2/3] Zipping and uploading...")
    zip_path = workdir / "sora-style-dataset.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        for p in image_paths:
            z.write(p, p.name)
    print(f"  zip: {zip_path} ({zip_path.stat().st_size // 1024} KB)")

    zip_url = fal_client.upload_file(str(zip_path))
    print(f"  uploaded: {zip_url[:80]}...")

    # ============================================================
    # STEP 3: Train LoRA
    # ============================================================
    print("\n[3/3] Training LoRA (5-15 min, ~$2)...")
    print("  trigger_word: sdpx illustration")
    print("  is_style: True (auto-caption disabled)")
    print("  steps: 1000")

    train = fal_client.subscribe(
        "fal-ai/flux-lora-fast-training",
        arguments={
            "images_data_url": zip_url,
            "trigger_word": "sdpx illustration",
            "is_style": True,
            "steps": 1000,
        },
        with_logs=True,
    )

    lora_url = train["diffusers_lora_file"]["url"]
    print(f"\n=== SUCCESS ===")
    print(f"LoRA URL: {lora_url}")
    print(f"\nAdd to .env:")
    print(f"  FAL_LORA_URL={lora_url}")
    print(f"  FAL_LORA_TRIGGER=sdpx illustration")
    print(f"\nTest with genmedia CLI (preferred — hits 'genmedia CLI' fal criterion):")
    print(f"  genmedia run fal-ai/flux-lora \\")
    print(f"    --prompt 'sdpx illustration of a moonlit bodega convenience store' \\")
    print(f"    --input loras='[{{\"path\":\"{lora_url}\",\"scale\":1.0}}]' \\")
    print(f"    --download out/{{request_id}}.png")
    print(f"\nOr with curl:")
    print(f"  curl -X POST https://fal.run/fal-ai/flux-lora \\")
    print(f"    -H \"Authorization: Key $FAL_KEY\" \\")
    print(f"    -H \"Content-Type: application/json\" \\")
    print(f"    -d '{{\"prompt\": \"sdpx illustration of a stone jungle temple room\", "
          f"\"loras\": [{{\"path\": \"{lora_url}\", \"scale\": 1.0}}]}}'")


if __name__ == "__main__":
    main()
