import json
from functools import lru_cache
from pathlib import Path

from app.models.creature import Creature


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "creatures.json"


@lru_cache(maxsize=1)
def load_fixtures() -> list[Creature]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
        data = json.load(fixture_file)
    return [Creature.model_validate(item) for item in data]


def fixture_by_id(creature_id: str) -> Creature | None:
    return next((creature for creature in load_fixtures() if creature.id == creature_id), None)
