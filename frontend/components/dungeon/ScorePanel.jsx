"use client";

import { useEffect, useRef, useState } from "react";

const TIER_COLORS = {
  excellent: { bg: "#1a4a1a", border: "#4ade80", label: "Excellent!" },
  good: { bg: "#1a3a4a", border: "#38bdf8", label: "Good!" },
  partial: { bg: "#3a2a00", border: "#fbbf24", label: "Partial" },
  miss: { bg: "#3a1a1a", border: "#f87171", label: "Miss" },
};

function AnimatedNumber({ target, duration = 800 }) {
  const [current, setCurrent] = useState(0);
  const frameRef = useRef(null);

  useEffect(() => {
    if (target === 0) { setCurrent(0); return; }
    const start = performance.now();
    function tick(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.round(eased * target));
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick);
      }
    }
    frameRef.current = requestAnimationFrame(tick);
    return () => { if (frameRef.current) cancelAnimationFrame(frameRef.current); };
  }, [target, duration]);

  return <span>{current}</span>;
}

export default function ScorePanel({ result, roomIndex, totalRooms }) {
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    // Flash reveal animation
    const t = setTimeout(() => setRevealed(true), 50);
    return () => clearTimeout(t);
  }, [result]);

  if (!result) return null;

  const tier = result.tier || "miss";
  const colors = TIER_COLORS[tier] || TIER_COLORS.miss;
  const extraction = result.pioneerExtraction;

  return (
    <div
      className={`score-panel ${revealed ? "score-panel--revealed" : ""}`}
      style={{
        background: colors.bg,
        borderColor: colors.border,
      }}
      role="status"
      aria-live="polite"
    >
      <div className="score-panel__row">
        <div className="score-panel__score">
          <span className="score-panel__number">
            <AnimatedNumber target={result.score} duration={800} />
          </span>
          <span className="score-panel__max">/100</span>
        </div>
        <div
          className={`score-panel__tier score-panel__tier--${tier} ${revealed ? "score-panel__tier--flash" : ""}`}
          style={{ borderColor: colors.border }}
        >
          {colors.label}
        </div>
      </div>

      {/* Room progress */}
      <div className="score-panel__progress">
        Room {(roomIndex || 0) + 1} of {totalRooms || 3}
      </div>

      {/* Pioneer extraction chip */}
      {extraction && (extraction.action || extraction.intent) && (
        <div className="score-panel__pioneer">
          <span className="score-panel__pioneer-label">Pioneer extracted:</span>
          {extraction.action && <span className="score-panel__chip">{extraction.action}</span>}
          {extraction.target && <span className="score-panel__chip">{extraction.target}</span>}
          {extraction.intent && <span className="score-panel__chip score-panel__chip--intent">{extraction.intent}</span>}
        </div>
      )}

      {/* Transcript comparison */}
      <div className="score-panel__comparison">
        <div>
          <span className="score-panel__comparison-label">You said:</span>
          <em>{result.normalizedTranscript}</em>
        </div>
        <div>
          <span className="score-panel__comparison-label">Target:</span>
          <em>{result.normalizedTarget}</em>
        </div>
      </div>

      {result.fallback && (
        <span className="score-panel__fallback">Pioneer: fixture fallback</span>
      )}
    </div>
  );
}
