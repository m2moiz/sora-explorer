"""Pronunciation scorer using rapidfuzz + Unidecode for accent-forgiving fuzzy matching."""

import re
import time
from typing import Any

from rapidfuzz import fuzz
from unidecode import unidecode

_PUNCT_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize(text: str, forgiving: bool = True) -> str:
    """Normalize text for comparison.

    Steps:
    1. Lowercase
    2. Strip punctuation
    3. Collapse whitespace
    4. If forgiving=True, strip accents via unidecode
    """
    result = text.lower()
    result = _PUNCT_RE.sub("", result)
    result = _WHITESPACE_RE.sub(" ", result).strip()
    if forgiving:
        result = unidecode(result)
    return result


def _tier(score: int) -> str:
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "good"
    if score >= 50:
        return "partial"
    return "miss"


def score_phrase(
    transcript: str,
    target: str,
    forgiving: bool = True,
) -> dict[str, Any]:
    """Score a spoken transcript against a target phrase.

    Returns a dict with:
    - score: int 0-100
    - tier: excellent | good | partial | miss
    - normalizedTranscript: str
    - normalizedTarget: str
    - latencyMs: int
    """
    started = time.perf_counter()

    norm_transcript = normalize(transcript, forgiving=forgiving)
    norm_target = normalize(target, forgiving=forgiving)

    # Use token_sort_ratio for word-order flexibility + partial_ratio for substring
    ratio = fuzz.ratio(norm_transcript, norm_target)
    token_sort = fuzz.token_sort_ratio(norm_transcript, norm_target)
    partial = fuzz.partial_ratio(norm_transcript, norm_target)

    # Weighted combination: exact match matters most, but partial helps with short phrases
    if norm_target and norm_transcript:
        score = int(ratio * 0.5 + token_sort * 0.3 + partial * 0.2)
    else:
        score = 0

    latency_ms = max(1, int((time.perf_counter() - started) * 1000))

    return {
        "score": min(100, max(0, score)),
        "tier": _tier(score),
        "normalizedTranscript": norm_transcript,
        "normalizedTarget": norm_target,
        "latencyMs": latency_ms,
    }
