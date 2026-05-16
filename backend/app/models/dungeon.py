from typing import Any

from pydantic import BaseModel


class Room(BaseModel):
    id: str
    type: str
    biome: str
    title: str
    description: str
    targetPhrase: str
    translation: str
    language: str
    difficulty: int
    expectedIntent: str
    expectedAction: str | None = None
    expectedTarget: str | None = None
    visualPrompt: str
    fallbackGradient: str | None = None
    voiceProfileNarrator: str | None = None
    voiceProfileNpc: str | None = None
    phonetic: str | None = None
    rewardOnSuccess: str | None = None
    enemy: dict[str, Any] | None = None
    boss: dict[str, Any] | None = None


class DungeonState(BaseModel):
    runId: str
    roomIndex: int
    totalRooms: int
    room: Room
    score: int = 0
    attempts: int = 0
    status: str = "active"  # active | victory | defeat
    language: str = "es-ES"
    themeId: str = "moonlit-bodega"
    palette: dict[str, str] | None = None


class PronunciationResult(BaseModel):
    score: int
    tier: str  # excellent | good | partial | miss
    normalizedTranscript: str
    normalizedTarget: str
    pioneerExtraction: dict[str, Any] | None = None
    providerStatus: dict[str, Any] | None = None
    latencyMs: int
    fallback: bool = False


class IntentExtraction(BaseModel):
    action: str | None = None
    target: str | None = None
    element: str | None = None
    modifier: str | None = None
    intent: str | None = None


class ProviderStatus(BaseModel):
    provider: str
    mode: str
    modelId: str | None = None
    status: str = "ready"
