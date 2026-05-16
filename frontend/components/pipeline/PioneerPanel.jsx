"use client";

export default function PioneerPanel({ creature }) {
  const status = creature?.providerStatus || {};
  const raw = creature?.rawExtraction || {};
  const confidence =
    raw?.confidence ??
    raw?.pioneerResponse?.confidence ??
    raw?.pioneerResponse?.score ??
    null;
  const isFallback = Boolean(creature?.fallback) || status.mode?.includes("fallback");

  return (
    <section className="pioneer-panel" aria-label="Pioneer extraction proof">
      <div className="pioneer-panel__header">
        <div>
          <p className="pioneer-panel__eyebrow">Pioneer/GLiNER2</p>
          <h2>Creature extraction</h2>
        </div>
        <span className={isFallback ? "pioneer-panel__status is-fallback" : "pioneer-panel__status"}>
          {isFallback ? "fixture fallback" : status.mode || "waiting"}
        </span>
      </div>

      <dl className="pioneer-panel__metrics">
        <div>
          <dt>Model</dt>
          <dd>{status.modelId || "PIONEER_MODEL_ID pending"}</dd>
        </div>
        <div>
          <dt>Latency</dt>
          <dd>{Number.isFinite(creature?.latencyMs) ? `${creature.latencyMs} ms` : "waiting"}</dd>
        </div>
        <div>
          <dt>Provider</dt>
          <dd>{status.provider || "pioneer"}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{confidence == null ? "not reported" : confidence}</dd>
        </div>
      </dl>

      <details className="pioneer-panel__raw" open={isFallback}>
        <summary>raw Pioneer response</summary>
        <pre>{JSON.stringify(raw, null, 2)}</pre>
      </details>
    </section>
  );
}
