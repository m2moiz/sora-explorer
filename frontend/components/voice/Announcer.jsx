"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function providerLabel(status) {
  if (!status) return "text-only fallback";
  if (status.provider === "slng" && !status.fallback) return "SLNG live";
  if (status.provider === "gradium" && !status.fallback) return "Gradium live";
  if (status.provider === "text-only") return "text-only fallback";
  return status.fallback ? "fixture fallback" : status.provider;
}

function audioSource(payload) {
  if (payload?.audioUrl) return payload.audioUrl;
  if (payload?.audioBase64) return `data:audio/mpeg;base64,${payload.audioBase64}`;
  return "";
}

const panelStyle = {
  display: "grid",
  gap: 10,
  padding: 12,
  border: "1px solid rgba(248, 250, 252, 0.16)",
  borderRadius: 8,
  background: "rgba(8, 10, 15, 0.72)",
  color: "#f8fafc"
};

const chipStyle = {
  display: "inline-flex",
  alignItems: "center",
  minHeight: 28,
  border: "1px solid rgba(248, 250, 252, 0.16)",
  borderRadius: 999,
  padding: "5px 9px",
  color: "#cbd5e1",
  fontSize: 12
};

export default function Announcer({ text = "", autoPlay = false }) {
  const audioRef = useRef(null);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("Announcer ready.");

  const displayText = payload?.displayText || text || "The arena awaits a challenger.";
  const providerStatus = payload?.providerStatus || {
    provider: "text-only",
    mode: "tts",
    fallback: true,
    status: "ready"
  };
  const src = useMemo(() => audioSource(payload), [payload]);

  async function speak() {
    setLoading(true);
    setMessage("Calling arena announcer...");
    try {
      const response = await fetch(`${API_BASE}/api/voice/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: displayText })
      });
      if (!response.ok) throw new Error(`Speak failed: ${response.status}`);
      const nextPayload = await response.json();
      setPayload(nextPayload);
      setMessage(nextPayload.audioUrl || nextPayload.audioBase64 ? "Voice commentary ready." : "Text-only commentary active.");
    } catch (error) {
      setPayload({
        displayText,
        providerStatus: {
          provider: "text-only",
          mode: "tts",
          fallback: true,
          status: "fallback"
        }
      });
      setMessage("Announcer voice unavailable; showing text commentary.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (autoPlay && text) speak();
  }, [autoPlay, text]);

  useEffect(() => {
    if (src && audioRef.current) {
      audioRef.current.play().catch(() => {
        setMessage("Audio generated; press play to hear it.");
      });
    }
  }, [src]);

  return (
    <section style={panelStyle} aria-label="Battle announcer">
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <button type="button" onClick={speak} disabled={loading}>
          {loading ? "Announcing..." : "Announce"}
        </button>
        <span style={chipStyle}>Voice provider: {providerLabel(providerStatus)}</span>
        <span style={chipStyle}>TTS mode: {providerStatus?.mode || "tts"}</span>
        {providerStatus?.fallback ? <span style={chipStyle}>fallback active</span> : null}
      </div>
      {src ? <audio ref={audioRef} controls src={src} /> : null}
      <p style={{ margin: 0, color: "#f8fafc", lineHeight: 1.4 }}>{displayText}</p>
      <p style={{ margin: 0, color: "#cbd5e1", fontSize: 13 }}>{message}</p>
    </section>
  );
}
