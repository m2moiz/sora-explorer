from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

try:
    from app.services.voice import synthesize_speech, transcribe_audio
except ModuleNotFoundError:
    from backend.app.services.voice import synthesize_speech, transcribe_audio


router = APIRouter(prefix="/api/voice", tags=["voice"])


class SpeakRequest(BaseModel):
    text: str | None = None


@router.post("/transcribe")
async def transcribe(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type")
    audio = await request.body()
    return await transcribe_audio(audio, content_type)


@router.post("/speak")
async def speak(payload: SpeakRequest) -> dict[str, Any]:
    return await synthesize_speech(payload.text)
