const stateClassNames = {
  entrance: "creature-visual--entrance",
  attack: "creature-visual--attack",
  damage: "creature-visual--damage",
  victory: "creature-visual--victory",
};

export default function CreatureVisual({ creature, state = "entrance", side = "left", compact = false }) {
  const stateClass = stateClassNames[state] || stateClassNames.entrance;
  const visualUrl = creature?.visualUrl;
  const visualGradient =
    creature?.visualGradient ||
    "linear-gradient(135deg, #111827 0%, #f8fafc 48%, #d97706 100%)";
  const name = creature?.name || "Awaiting creature";
  const element = creature?.element || "unknown";
  const provider = creature?.fallback ? "fixture fallback" : creature?.providerStatus?.provider || "pending";

  return (
    <figure
      className={[
        "creature-visual",
        `creature-visual--${side}`,
        stateClass,
        compact ? "creature-visual--compact" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      aria-label={`${name} visual`}
    >
      <div className="creature-visual__stage" style={{ "--creature-gradient": visualGradient }}>
        {visualUrl ? (
          <img className="creature-visual__image" src={visualUrl} alt={`${name} generated battle art`} />
        ) : (
          <div className="creature-visual__fallback" aria-hidden="true">
            <span>{name.slice(0, 2).toUpperCase()}</span>
          </div>
        )}
        <div className="creature-visual__shadow" aria-hidden="true" />
      </div>
      <figcaption className="creature-visual__caption">
        <strong>{name}</strong>
        <span>{element} &middot; {provider}</span>
      </figcaption>
    </figure>
  );
}
