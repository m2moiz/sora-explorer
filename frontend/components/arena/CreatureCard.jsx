import CreatureVisual from "./CreatureVisual";
import "./ArenaEffects.css";

export default function CreatureCard({ creature, side, activeHp, visualState = "entrance" }) {
  if (!creature) {
    return (
      <section className="creature-card creature-card--empty">
        <div className="slot-label">{side}</div>
        <div className="empty-orb" />
        <p>Awaiting challenger</p>
      </section>
    );
  }

  const hpPercent = Math.max(0, Math.round(((activeHp ?? creature.stats.hp) / creature.stats.hp) * 100));

  return (
    <section className="creature-card">
      <CreatureVisual creature={creature} side={side.toLowerCase().includes("right") ? "right" : "left"} state={visualState} compact />
      <div className="creature-head">
        <div>
          <div className="slot-label">{side}</div>
          <h2>{creature.name}</h2>
        </div>
        <span className="rarity">{creature.rarity}</span>
      </div>
      <p className="description">{creature.description}</p>
      <div className="hp-row">
        <span>HP</span>
        <div className="hp-track">
          <div className="hp-fill" style={{ width: `${hpPercent}%` }} />
        </div>
        <strong>{activeHp ?? creature.stats.hp}</strong>
      </div>
      <dl className="stats-grid">
        <div><dt>ATK</dt><dd>{creature.stats.atk}</dd></div>
        <div><dt>DEF</dt><dd>{creature.stats.def}</dd></div>
        <div><dt>SPD</dt><dd>{creature.stats.speed}</dd></div>
        <div><dt>MAG</dt><dd>{creature.stats.magic}</dd></div>
      </dl>
      <div className="tags">
        <span>{creature.element}</span>
        <span>{creature.archetype}</span>
        <span>{creature.fallback ? "fixture fallback" : creature.providerStatus.provider}</span>
      </div>
    </section>
  );
}
