"""Dungeon routes for Sora the Explorer."""

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.dungeon import DungeonState, Room

router = APIRouter(prefix="/api/dungeon", tags=["dungeon"])

_ROOMS_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "rooms.json"


def _load_rooms() -> dict[str, Any]:
    with open(_ROOMS_PATH, encoding="utf-8") as f:
        return json.load(f)


class StartRequest(BaseModel):
    language: str = "es-ES"


class AdvanceRequest(BaseModel):
    runId: str
    roomIndex: int
    lastScore: int = 0


@router.post("/start", response_model=DungeonState)
async def start_dungeon(payload: StartRequest) -> DungeonState:
    """Start a new dungeon run. Returns state with first room."""
    data = _load_rooms()
    rooms = data.get("rooms", [])
    if not rooms:
        raise HTTPException(status_code=500, detail="No rooms configured")
    first_room_data = rooms[0]
    room = Room(**first_room_data)
    return DungeonState(
        runId=str(uuid.uuid4()),
        roomIndex=0,
        totalRooms=len(rooms),
        room=room,
        score=0,
        attempts=0,
        status="active",
        language=payload.language or data.get("language", "es-ES"),
        themeId=data.get("themeId", "moonlit-bodega"),
        palette=data.get("palette"),
    )


@router.post("/advance", response_model=DungeonState)
async def advance_dungeon(payload: AdvanceRequest) -> DungeonState:
    """Advance to the next room, or return victory if all rooms cleared."""
    data = _load_rooms()
    rooms = data.get("rooms", [])
    next_index = payload.roomIndex + 1

    if next_index >= len(rooms):
        # Victory — return last room but with victory status
        last_room = Room(**rooms[-1])
        return DungeonState(
            runId=payload.runId,
            roomIndex=next_index,
            totalRooms=len(rooms),
            room=last_room,
            score=payload.lastScore,
            status="victory",
            language=data.get("language", "es-ES"),
            themeId=data.get("themeId", "moonlit-bodega"),
            palette=data.get("palette"),
        )

    next_room_data = rooms[next_index]
    room = Room(**next_room_data)
    return DungeonState(
        runId=payload.runId,
        roomIndex=next_index,
        totalRooms=len(rooms),
        room=room,
        score=payload.lastScore,
        status="active",
        language=data.get("language", "es-ES"),
        themeId=data.get("themeId", "moonlit-bodega"),
        palette=data.get("palette"),
    )
