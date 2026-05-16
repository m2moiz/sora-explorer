"""Pronunciation scoring route for Sora the Explorer."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.models.dungeon import PronunciationResult
from app.services.pronunciation_scorer import score_phrase
from app.services.intent_extractor import extract_intent

router = APIRouter(prefix="/api/pronunciation", tags=["pronunciation"])


class ScoreRequest(BaseModel):
    transcript: str
    targetPhrase: str
    language: str = "es-ES"


@router.post("/score", response_model=PronunciationResult)
async def score_pronunciation(payload: ScoreRequest) -> PronunciationResult:
    """Score a spoken transcript against the target phrase.

    Also calls Pioneer GLiNER2 for intent extraction.
    """
    # Score pronunciation (accent-forgiving fuzzy match)
    result = score_phrase(payload.transcript, payload.targetPhrase, forgiving=True)

    # Extract intent via Pioneer (async)
    intent_result = await extract_intent(payload.transcript)

    # Build extraction dict for the response
    pioneer_extraction: dict = intent_result.get("extraction", {})

    return PronunciationResult(
        score=result["score"],
        tier=result["tier"],
        normalizedTranscript=result["normalizedTranscript"],
        normalizedTarget=result["normalizedTarget"],
        pioneerExtraction=pioneer_extraction,
        providerStatus=intent_result.get("providerStatus"),
        latencyMs=result["latencyMs"] + intent_result.get("latencyMs", 0),
        fallback=intent_result.get("fallback", False),
    )
