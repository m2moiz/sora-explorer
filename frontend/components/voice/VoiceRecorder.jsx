"use client";

import { useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function statusLabel(status) {
  if (!status) return "fixture fallback";
  if (status.provider === "slng" && !status.fallback) return "SLNG live";
  if (status.provider === "gradium" && !status.fallback) return "Gradium live";
  if (status.provider === "voice-fixture") return "fixture fallback";
  return status.fallback ? "fallback" : status.provider;
}

const shellStyle = {
  display: "grid",
  gap: 10,
  padding: 12,
  border: "1px solid rgba(248, 250, 252, 0.16)",
  borderRadius: 8,
  background: "rgba(8, 10, 15, 0.72)",
  color: "#f8fafc"
};

const rowStyle = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: 8
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

export default function VoiceRecorder({ onTranscript = () => {} }) {
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const [isRecording, setIsRecording] = useState(false);
  const [message, setMessage] = useState("Voice input ready.");
  const [providerStatus, setProviderStatus] = useState({
    provider: "voice-fixture",
    mode: "transcript",
    fallback: true,
    status: "ready"
  });

  async function submitAudio(blob) {
    const form = new FormData();
    form.append("audio", blob, "creature-prompt.webm");
    setMessage("Transcribing voice prompt...");

    try {
      const response = await fetch(`${API_BASE}/api/voice/transcribe`, {
        method: "POST",
        body: form
      });
      if (!response.ok) throw new Error(`Transcribe failed: ${response.status}`);
      const payload = await response.json();
      const transcript = payload.transcript || "";
      setProviderStatus(payload.providerStatus || providerStatus);
      setMessage(transcript ? `Transcript: ${transcript}` : "No transcript returned; typed prompt remains available.");
      if (transcript) onTranscript(transcript, payload);
    } catch (error) {
      setProviderStatus({
        provider: "voice-fixture",
        mode: "transcript",
        fallback: true,
        status: "fallback"
      });
      setMessage("Voice unavailable; use the typed prompt or fixture fallback.");
    }
  }

  async function startRecording() {
    if (typeof window === "undefined" || !navigator.mediaDevices || !window.MediaRecorder) {
      setMessage("Browser recording unavailable; use the typed prompt fallback.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data?.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        if (blob.size) {
          submitAudio(blob);
        } else {
          setMessage("No audio captured; typed prompt remains available.");
        }
      };

      recorder.start();
      setIsRecording(true);
      setMessage("Recording creature concept...");
    } catch (error) {
      setProviderStatus({
        provider: "voice-fixture",
        mode: "transcript",
        fallback: true,
        status: "permission-denied"
      });
      setMessage("Microphone permission denied; use the typed prompt fallback.");
    }
  }

  function stopRecording() {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
    setIsRecording(false);
  }

  return (
    <section style={shellStyle} aria-label="Voice creature prompt">
      <div style={rowStyle}>
        <button type="button" onClick={isRecording ? stopRecording : startRecording}>
          {isRecording ? "Stop Recording" : "Record Voice"}
        </button>
        <span style={chipStyle}>Voice provider: {statusLabel(providerStatus)}</span>
        <span style={chipStyle}>Transcript mode: {providerStatus?.mode || "transcript"}</span>
        {providerStatus?.fallback ? <span style={chipStyle}>fallback active</span> : null}
      </div>
      <p style={{ margin: 0, color: "#cbd5e1", lineHeight: 1.35 }}>{message}</p>
    </section>
  );
}
