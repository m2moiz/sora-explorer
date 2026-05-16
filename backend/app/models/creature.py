from typing import Any

from pydantic import BaseModel, Field


class CreatureStats(BaseModel):
    hp: int = Field(gt=0)
    atk: int = Field(gt=0)
    def_: int = Field(alias="def", gt=0)
    speed: int = Field(gt=0)
    magic: int = Field(gt=0)

    model_config = {"populate_by_name": True}


class ProviderStatus(BaseModel):
    provider: str
    mode: str
    modelId: str | None = None
    status: str = "ready"


class Creature(BaseModel):
    id: str
    name: str
    description: str
    element: str
    archetype: str
    rarity: str
    stats: CreatureStats
    abilities: list[str]
    weaknesses: list[str]
    visualUrl: str
    visualGradient: str
    providerStatus: ProviderStatus
    rawExtraction: dict[str, Any]
    latencyMs: int
    fallback: bool


class CreatureExtractRequest(BaseModel):
    description: str


class BattleRequest(BaseModel):
    leftId: str | None = None
    rightId: str | None = None
    left: Creature | None = None
    right: Creature | None = None


class BattleTurn(BaseModel):
    turn: int
    attackerId: str
    attackerName: str
    defenderId: str
    defenderName: str
    move: str
    damage: int
    modifier: str
    leftHp: int
    rightHp: int


class BattleResponse(BaseModel):
    left: Creature
    right: Creature
    turns: list[BattleTurn]
    winnerId: str
    winnerName: str
    finalHp: dict[str, int]
