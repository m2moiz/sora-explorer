from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routes import battle, commentary, creatures, lore, sprites, voice
from app.routes import dungeon, pronunciation


load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

app = FastAPI(title="Sora the Explorer / Procedural Coliseum", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, bool | str]:
    return {"ok": True, "service": "procedural-coliseum"}


app.include_router(dungeon.router)
app.include_router(pronunciation.router)
app.include_router(creatures.router)
app.include_router(battle.router)
app.include_router(sprites.router)
app.include_router(voice.router)
app.include_router(lore.router)
app.include_router(commentary.router)
