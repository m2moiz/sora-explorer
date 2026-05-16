const labels = {
  voice: "Voice",
  pioneer: "Pioneer",
  tavily: "Tavily",
  fal: "fal",
  battle: "Battle/OpenAI",
  announcer: "Announcer",
};

export default function PipelineRail({ steps = {} }) {
  return (
    <div className="pipeline-rail" aria-label="Sponsor pipeline status">
      {Object.entries(labels).map(([key, label]) => {
        const state = steps[key] || "waiting";
        return (
          <span key={key} className={`pipeline-step pipeline-step--${state}`}>
            <strong>{label}</strong>
            <em>{state}</em>
          </span>
        );
      })}
    </div>
  );
}
