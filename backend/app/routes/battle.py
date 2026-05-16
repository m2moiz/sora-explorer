from fastapi import APIRouter, HTTPException

from app.models.creature import BattleRequest, BattleResponse, BattleTurn, Creature
from app.routes.fixtures import fixture_by_id


router = APIRouter(prefix="/api", tags=["battle"])


ELEMENT_EDGE = {
    "thunder": {"glass", "water", "mirror"},
    "glass": {"shadow", "moss"},
    "moss": {"stone", "clockwork"},
    "shadow": {"water", "mirror"},
    "clockwork": {"glass", "thunder"},
    "mirror": {"magic", "shadow"},
    "water": {"fire", "clockwork"},
}


def _resolve(creature_id: str | None, creature: Creature | None, side: str) -> Creature:
    if creature is not None:
        return creature
    if creature_id:
        fixture = fixture_by_id(creature_id)
        if fixture:
            return fixture
    raise HTTPException(status_code=400, detail=f"Missing or unknown {side} creature")


def _has_edge(attacker: Creature, defender: Creature) -> bool:
    defender_terms = {defender.element.lower(), *[weakness.lower() for weakness in defender.weaknesses]}
    return bool(ELEMENT_EDGE.get(attacker.element.lower(), set()) & defender_terms)


def _damage(attacker: Creature, defender: Creature) -> tuple[int, str]:
    stats = attacker.stats
    defender_stats = defender.stats
    base = max(4, stats.atk + stats.magic // 2 - defender_stats.def_ // 2)
    if _has_edge(attacker, defender):
        return base + 9, "weakness exploited"
    if attacker.element.lower() in {weakness.lower() for weakness in defender.weaknesses}:
        return base + 5, "elemental pressure"
    return base, "standard strike"


@router.post("/battle", response_model=BattleResponse)
async def battle(payload: BattleRequest) -> BattleResponse:
    left = _resolve(payload.leftId, payload.left, "left")
    right = _resolve(payload.rightId, payload.right, "right")
    left_hp = left.stats.hp
    right_hp = right.stats.hp
    turns: list[BattleTurn] = []

    first_left = (left.stats.speed, left.id) >= (right.stats.speed, right.id)
    order = [(left, right), (right, left)] if first_left else [(right, left), (left, right)]

    for turn_number in range(1, 13):
        attacker, defender = order[(turn_number - 1) % 2]
        damage, modifier = _damage(attacker, defender)
        if defender.id == left.id:
            left_hp = max(0, left_hp - damage)
        else:
            right_hp = max(0, right_hp - damage)

        ability = attacker.abilities[(turn_number - 1) % len(attacker.abilities)]
        turns.append(
            BattleTurn(
                turn=turn_number,
                attackerId=attacker.id,
                attackerName=attacker.name,
                defenderId=defender.id,
                defenderName=defender.name,
                move=ability,
                damage=damage,
                modifier=modifier,
                leftHp=left_hp,
                rightHp=right_hp,
            )
        )
        if left_hp <= 0 or right_hp <= 0:
            break

    if left_hp == right_hp:
        winner = left if (left.stats.magic + left.stats.speed, left.id) >= (right.stats.magic + right.stats.speed, right.id) else right
    else:
        winner = left if left_hp > right_hp else right

    return BattleResponse(
        left=left,
        right=right,
        turns=turns,
        winnerId=winner.id,
        winnerName=winner.name,
        finalHp={left.id: left_hp, right.id: right_hp},
    )
