"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import PipelineRail from "../pipeline/PipelineRail";
import PioneerPanel from "../pipeline/PioneerPanel";
import FalPanel from "../pipeline/FalPanel";
import CitationChips from "../pipeline/CitationChips";
import BenchmarkPanel from "./BenchmarkPanel";
import GameCanvas from "./GameCanvas";
import { gameBus } from "../../lib/gameBus";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function postJson(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${path} failed: ${response.status}`);
  return response.json();
}

const INITIAL_PIPELINE = {
  voice: "waiting",
  pioneer: "waiting",
  tavily: "waiting",
  fal: "waiting",
  battle: "waiting",
  announcer: "waiting",
};

const ROOM_ART = [
  "/assets/rooms/room-1-merchant.png",
  "/assets/rooms/room-2-enemy.png",
  "/assets/rooms/room-3-boss.png",
];

// view: title | map | room | victory
export default function DungeonScene() {
  const [view, setView] = useState("title");
  const [dungeon, setDungeon] = useState(null);
  const [score, setScore] = useState(null);
  const [hp, setHp] = useState(3);
  const [coins, setCoins] = useState(0);
  const [streak, setStreak] = useState(0);
  const [status, setStatus] = useState("idle"); // idle|loading|recording|scoring|success|miss
  const [interimText, setInterimText] = useState("");
  const [matchedWords, setMatchedWords] = useState([]);
  const [message, setMessage] = useState("");
  const [pipeline, setPipeline] = useState(INITIAL_PIPELINE);
  const [falStatus, setFalStatus] = useState(null);
  const [pioneer, setPioneer] = useState(null);
  const [showInspector, setShowInspector] = useState(false);
  const [showBenchmark, setShowBenchmark] = useState(false);
  const [musicOn, setMusicOn] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const audioRef = useRef(null);
  const recognitionRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);

  function setStep(key, value) {
    setPipeline((cur) => ({ ...cur, [key]: value }));
  }

  // Theme CSS variables follow active room palette
  useEffect(() => {
    const palette = dungeon?.palette;
    if (!palette) return;
    const root = document.documentElement;
    root.style.setProperty("--bg", palette.bg || "#0a0e1a");
    root.style.setProperty("--fg", palette.fg || "#f4d35e");
    root.style.setProperty("--accent", palette.accent || "#ee964b");
  }, [dungeon?.palette]);

  // Music control
  useEffect(() => {
    if (!audioRef.current) return;
    audioRef.current.volume = 0.35;
    if (musicOn) {
      audioRef.current.play().catch(() => setMusicOn(false));
    } else {
      audioRef.current.pause();
    }
  }, [musicOn]);

  // Auto-speak the target phrase whenever a new room becomes active so the
  // player hears the model pronunciation without having to hunt for the
  // Listen button. Runs once per room (keyed off room id + view transition).
  const lastSpokenRoomRef = useRef(null);
  useEffect(() => {
    if (view !== "room" || !dungeon?.room) return;
    const key = `${dungeon.runId}:${dungeon.roomIndex}`;
    if (lastSpokenRoomRef.current === key) return;
    lastSpokenRoomRef.current = key;
    const t = setTimeout(() => {
      speakText(dungeon.room.targetPhrase, dungeon.room.language, dungeon.room.voiceProfileNarrator);
    }, 700);
    return () => clearTimeout(t);
  }, [view, dungeon?.runId, dungeon?.roomIndex]);

  async function startDungeon() {
    setStatus("loading");
    setView("map");
    setMessage("Entering the dungeon...");
    setStep("battle", "running");
    setMusicOn(true);
    try {
      const state = await postJson("/api/dungeon/start", { language: "es-ES" });
      setDungeon(state);
      setScore(null);
      setStep("battle", "done");
      // Pause on the world map so Kaplay can boot and walk Sora to the first node
      setTimeout(() => {
        setView("room");
        setStatus("idle");
        setMessage(`Room 1: ${state.room.title}`);
        generateRoomImage(state.room);
      }, 2800);
    } catch (err) {
      setStatus("idle");
      setView("title");
      setStep("battle", "error");
      setMessage(`Failed to start: ${err.message}`);
    }
  }

  async function generateRoomImage(room) {
    if (!room?.visualPrompt) return;
    setStep("fal", "running");
    try {
      const result = await postJson("/api/creature/sprite", {
        description: room.visualPrompt,
        creature: {
          id: room.id, name: room.title, description: room.description,
          element: "shadow", archetype: "guardian", rarity: "rare",
          stats: { hp: 10, atk: 5, def: 5, speed: 5, magic: 5 },
          abilities: [], weaknesses: [], visualUrl: "", visualGradient: room.fallbackGradient || "",
          providerStatus: { provider: "fal", mode: "pending", status: "pending" },
          rawExtraction: {}, latencyMs: 0, fallback: false
        }
      });
      setFalStatus({ provider: "fal", mode: result.fallback ? "fallback" : "live", modelId: result.providerStatus?.modelId, latencyMs: result.latencyMs, fallback: result.fallback });
      setStep("fal", result.fallback ? "fallback" : "done");
    } catch {
      setStep("fal", "error");
      setFalStatus({ provider: "fal", mode: "fixture-fallback", fallback: true });
    }
  }

  async function advanceDungeon() {
    if (!dungeon) return;
    setStatus("loading");
    setStep("battle", "running");
    // Show map transition between rooms
    setView("map");
    try {
      const state = await postJson("/api/dungeon/advance", {
        runId: dungeon.runId,
        roomIndex: dungeon.roomIndex,
        lastScore: score?.score || 0,
      });
      setDungeon(state);
      setScore(null);
      setMatchedWords([]);
      setInterimText("");
      if (state.status === "victory") {
        setTimeout(() => {
          setView("victory");
          setStep("battle", "done");
          setMessage("The bodega remembers what you said.");
        }, 1200);
      } else {
        setTimeout(() => {
          setView("room");
          setStatus("idle");
          setStep("battle", "done");
          setMessage(`Room ${state.roomIndex + 1}: ${state.room.title}`);
          generateRoomImage(state.room);
        }, 2400);
      }
    } catch (err) {
      setStatus("idle");
      setView("room");
      setStep("battle", "error");
      setMessage(`Error advancing: ${err.message}`);
    }
  }

  function targetWords() {
    return (dungeon?.room?.targetPhrase || "")
      .replace(/[¿?¡!.,]/g, "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
  }

  function updateMatchedWords(transcript) {
    const norm = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[¿?¡!.,]/g, "").trim();
    const heard = new Set(norm(transcript).split(/\s+/));
    const target = targetWords();
    const matched = target.map((w) => heard.has(norm(w)));
    setMatchedWords(matched);
  }

  function startRecording() {
    setIsRecording(true);
    setStatus("recording");
    setMatchedWords([]);
    setInterimText("");
    setStep("voice", "running");
    setMessage("Listening...");

    // SLNG-first: skip the flaky Web Speech path (Chrome routes recognition
    // through Google's cloud which 502s behind VPN / corp DNS) and go straight
    // to MediaRecorder -> /api/voice/transcribe (SLNG nova:3). Toggle to the
    // browser-side recognizer with window.__useWebSpeech = true if you want
    // to compare. SLNG is also our sponsor STT — keeping it on the hot path
    // makes the integration load-bearing for the LEGO prize criterion.
    const useWebSpeech = typeof window !== "undefined" && window.__useWebSpeech === true;

    const SpeechRecognition = useWebSpeech
      ? (window.SpeechRecognition || window.webkitSpeechRecognition)
      : null;
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.lang = dungeon?.language || dungeon?.room?.language || "es-ES";
      rec.interimResults = true;
      rec.continuous = false;
      rec.maxAlternatives = 1;
      recognitionRef.current = rec;
      rec.onresult = (event) => {
        let interim = "";
        let final = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const r = event.results[i];
          if (r.isFinal) final += r[0].transcript;
          else interim += r[0].transcript;
        }
        setInterimText(interim || final);
        updateMatchedWords(interim || final);
        if (final) {
          setIsRecording(false);
          setStatus("scoring");
          setStep("voice", "done");
          handleTranscript(final);
        }
      };
      rec.onerror = (e) => {
        // Web Speech network errors hit reliably behind VPNs / restricted DNS.
        // Fall back to MediaRecorder -> /api/voice/transcribe (SLNG) instead
        // of dead-ending the user.
        if (e.error === "network" || e.error === "service-not-allowed") {
          recognitionRef.current = null;
          setMessage("Web Speech blocked — switching to SLNG transcription…");
          startMediaRecorderFallback();
          return;
        }
        setIsRecording(false);
        setStatus("idle");
        setStep("voice", "error");
        const hint = e.error === "not-allowed"
          ? "Mic blocked — click the mic icon in your URL bar and Allow, then reload."
          : e.error === "no-speech"
            ? "I didn't catch that — try again, a little louder."
            : `Voice error: ${e.error}. Try again.`;
        setMessage(hint);
      };
      rec.onend = () => setIsRecording(false);
      rec.start();
    } else {
      startMediaRecorderFallback();
    }
  }

  function startMediaRecorderFallback() {
    setIsRecording(true);
    setStatus("recording");
    setStep("voice", "running");
    if (!navigator.mediaDevices) {
      setMessage("Microphone unavailable on this browser.");
      setIsRecording(false);
      setStatus("idle");
      setStep("voice", "error");
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorderRef.current = recorder;
      recorder.ondataavailable = (e) => { if (e.data?.size) chunksRef.current.push(e.data); };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        submitAudioBlob(blob);
      };
      recorder.start();
      setMessage("Listening (SLNG)…");
      setTimeout(() => { if (recorder.state !== "inactive") recorder.stop(); setIsRecording(false); }, 8000);
    }).catch(() => {
      setMessage("Microphone permission denied.");
      setIsRecording(false);
      setStatus("idle");
      setStep("voice", "error");
    });
  }

  function stopRecording() {
    if (recognitionRef.current) { recognitionRef.current.stop(); recognitionRef.current = null; }
    if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop();
    setIsRecording(false);
  }

  async function submitAudioBlob(blob) {
    const form = new FormData();
    form.append("audio", blob, "phrase.webm");
    setMessage("Transcribing...");
    try {
      const resp = await fetch(`${API_BASE}/api/voice/transcribe`, { method: "POST", body: form });
      if (!resp.ok) throw new Error(`Transcribe failed: ${resp.status}`);
      const data = await resp.json();
      setStep("voice", data.fallback ? "fallback" : "done");
      handleTranscript(data.transcript || "");
    } catch (err) {
      setStep("voice", "error");
      setStatus("idle");
      setMessage(`Transcription failed: ${err.message}`);
    }
  }

  const handleTranscript = useCallback(async (transcript) => {
    if (!dungeon?.room) return;
    updateMatchedWords(transcript);
    setStatus("scoring");
    setStep("pioneer", "running");
    setMessage("Pioneer is extracting intent...");
    try {
      const result = await postJson("/api/pronunciation/score", {
        transcript,
        targetPhrase: dungeon.room.targetPhrase,
        language: dungeon.room.language,
      });
      setScore(result);
      setStep("pioneer", result.fallback ? "fallback" : "done");
      setPioneer({
        providerStatus: result.providerStatus || { provider: "pioneer", mode: "live" },
        rawExtraction: result.pioneerExtraction || {},
        latencyMs: result.latencyMs,
        fallback: result.fallback,
      });
      fetchCulturalNote(dungeon.room.targetPhrase);

      if (result.tier === "excellent" || result.tier === "good") {
        setStatus("success");
        setMessage(result.tier === "excellent" ? "Magnificent!" : "Well spoken!");
        gameBus.emit("scoreSuccess", { tier: result.tier });
        speakText(
          result.tier === "excellent" ? "Magnificent!" : "Well spoken, traveler.",
          "en-US",
          dungeon.room.voiceProfileNarrator,
        );
      } else if (result.tier === "partial") {
        setStatus("miss");
        setMessage(`Close — try again.`);
        gameBus.emit("scoreMiss", {});
        speakText("Close. Try again.", "en-US", dungeon.room.voiceProfileNarrator);
      } else {
        setStatus("miss");
        setMessage(`The cat tilts its head. Say "${dungeon.room.phonetic || dungeon.room.targetPhrase}"`);
        gameBus.emit("scoreMiss", {});
        speakText("The cat tilts its head.", "en-US", dungeon.room.voiceProfileNarrator);
      }
    } catch (err) {
      setStep("pioneer", "error");
      setStatus("idle");
      setMessage(`Scoring failed: ${err.message}`);
    }
  }, [dungeon]);

  async function fetchCulturalNote(phrase) {
    setStep("tavily", "running");
    try {
      const resp = await fetch(`${API_BASE}/api/creature/lore`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: phrase, element: "language", abilities: [], weaknesses: [] }),
      });
      if (!resp.ok) throw new Error("lore failed");
      const data = await resp.json();
      setStep("tavily", data.fallback ? "fallback" : "done");
    } catch {
      setStep("tavily", "error");
    }
  }

  // Speak arbitrary text via the SLNG/Gradium TTS bridge and actually play it.
  async function speakText(text, language, voiceId) {
    if (!text) return false;
    try {
      const resp = await fetch(`${API_BASE}/api/voice/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language, voiceId }),
      });
      if (!resp.ok) throw new Error(`speak ${resp.status}`);
      const data = await resp.json();
      if (data.audioBase64) {
        const mime = data.audioMime || "audio/mpeg";
        const audio = new Audio(`data:${mime};base64,${data.audioBase64}`);
        audio.volume = 0.95;
        await audio.play().catch((err) => {
          // Autoplay block: surface to user once
          console.warn("audio play blocked", err);
        });
      }
      return !data.fallback;
    } catch (err) {
      console.warn("speakText error:", err);
      return false;
    }
  }

  async function playExamplePhrase() {
    if (!dungeon?.room) return;
    setStep("announcer", "running");
    const ok = await speakText(
      dungeon.room.targetPhrase,
      dungeon.room.language,
      dungeon.room.voiceProfileNarrator,
    );
    setStep("announcer", ok ? "done" : "error");
  }

  function resetGame() {
    setView("title");
    setDungeon(null);
    setScore(null);
    setStatus("idle");
    setPipeline(INITIAL_PIPELINE);
    setMatchedWords([]);
    setInterimText("");
    setMessage("");
    gameBus.emit("resetRun", {});
  }

  // Dev-only: expose handleTranscript on window for demo/testing without a mic
  useEffect(() => {
    if (typeof window === "undefined" || process.env.NODE_ENV === "production") return;
    window.__simulateSpeak = (transcript) => {
      if (!dungeon?.room) return Promise.reject(new Error("no room"));
      const t = transcript || dungeon.room.targetPhrase;
      setStatus("scoring");
      return handleTranscript(t);
    };
    return () => { try { delete window.__simulateSpeak; } catch {} };
  }, [dungeon, handleTranscript]);

  // Mirror Kaplay HUD state into React so hearts/coins are visible across views
  useEffect(() => {
    const offs = [];
    offs.push(gameBus.on("youDied", () => {
      setMessage("You ran out of hearts. The dungeon resets.");
      setTimeout(() => resetGame(), 1400);
    }));
    offs.push(gameBus.on("scoreSuccess", ({ tier }) => {
      setCoins((c) => c + (tier === "excellent" ? 10 : 5));
      setStreak((s) => s + 1);
    }));
    offs.push(gameBus.on("scoreMiss", () => {
      setHp((h) => Math.max(0, h - 1));
      setStreak(0);
    }));
    offs.push(gameBus.on("resetRun", () => {
      setHp(3);
      setCoins(0);
      setStreak(0);
    }));
    return () => offs.forEach((off) => off && off());
  }, []);

  const room = dungeon?.room;
  const roomBg = dungeon
    ? ROOM_ART[dungeon.roomIndex ?? 0] || ROOM_ART[0]
    : "/assets/title-splash.png";
  const totalRooms = dungeon?.totalRooms || 3;
  const currentIdx = dungeon?.roomIndex ?? 0;
  const target = targetWords();

  return (
    <div className="sora-app">
      {/* Background music (autoplay only after user click via startDungeon) */}
      <audio ref={audioRef} src="/assets/theme-music.mp3" loop preload="auto" />

      {/* Always-visible HUD overlay */}
      <div className="hud-overlay">
        <div className="hud-brand" onClick={resetGame}>
          <span className="hud-brand__eyebrow">SORA THE EXPLORER</span>
          <span className="hud-brand__title">An Imagined Roguelike</span>
        </div>
        <div className="hud-controls">
          {dungeon && (
            <div className="hud-game-stats" aria-label="Run stats">
              <span className="hud-hearts" aria-label={`${hp} hearts`}>
                {Array.from({ length: 3 }).map((_, i) => (
                  <span key={i} className={`hud-heart ${i < hp ? "" : "is-lost"}`}>
                    {i < hp ? "♥" : "♡"}
                  </span>
                ))}
              </span>
              <span className="hud-coins" aria-label={`${coins} coins`}>◎ {coins}</span>
              {streak >= 2 && <span className="hud-streak">🔥 x{streak}</span>}
            </div>
          )}
          <button
            type="button"
            className="hud-icon"
            onClick={() => setMusicOn((v) => !v)}
            title={musicOn ? "Pause music" : "Play music"}
            aria-label="Toggle music"
          >
            {musicOn ? "♪" : "♪̸"}
          </button>
          {dungeon && (
            <div className="hud-progress" aria-label="Dungeon progress">
              {Array.from({ length: totalRooms }).map((_, i) => (
                <span
                  key={i}
                  className={`hud-progress__dot ${i === currentIdx ? "is-current" : ""} ${i < currentIdx ? "is-done" : ""}`}
                />
              ))}
            </div>
          )}
          <button
            type="button"
            className="hud-icon"
            onClick={() => setShowInspector((v) => !v)}
            title="AI Inspector"
            aria-label="Toggle AI Inspector"
          >
            ⚙
          </button>
        </div>
      </div>

      {/* TITLE VIEW */}
      {view === "title" && (
        <section className="title-stage" style={{ backgroundImage: `url(${roomBg})` }}>
          <div className="title-stage__veil" />
          <div className="title-stage__content">
            <p className="title-eyebrow">SORA · THE · EXPLORER</p>
            <h1 className="title-headline">An Imagined Roguelike</h1>
            <p className="title-sub">Speak. Survive. Learn.</p>
            <div className="title-actions">
              <button type="button" className="cta-primary" onClick={startDungeon} disabled={status === "loading"}>
                {status === "loading" ? "Entering…" : "▶  Play Adventure"}
              </button>
              <button type="button" className="cta-ghost" onClick={() => setShowBenchmark(true)}>
                Behind the AI
              </button>
            </div>
            <p className="title-foot">A solo hackathon experiment · Pioneer · fal · SLNG · Gradium · OpenAI · Tavily</p>
          </div>
        </section>
      )}

      {/* MAP / WORLD VIEW (Kaplay canvas) */}
      {view === "map" && (
        <section className="map-stage map-stage--canvas">
          <GameCanvas roomIndex={currentIdx} />
          <div className="map-stage__title-overlay">
            <p className="map-eyebrow">{dungeon ? `Approaching Room ${currentIdx + 1}` : "Entering the dungeon"}</p>
            <h2 className="map-headline">{dungeon?.themeId === "moonlit-bodega" ? "Moonlit Bodega" : (dungeon?.themeId || "The Dungeon")}</h2>
          </div>
        </section>
      )}

      {/* ROOM (GAMEPLAY) VIEW */}
      {view === "room" && room && (
        <section className="room-stage" style={{ backgroundImage: `url(${roomBg})` }}>
          <div className="room-stage__veil" />
          <div className="room-stage__overlay">
            <div className="room-stage__header">
              <p className="room-stage__chip">{room.type?.toUpperCase() || "ROOM"}  ·  Room {currentIdx + 1} of {totalRooms}</p>
              <h2 className="room-stage__title">{room.title}</h2>
            </div>

            {/* Karaoke phrase */}
            <div className="karaoke">
              <div className="karaoke__lang">
                <span className="karaoke__flag">🇪🇸</span>
                <span className="karaoke__locale">{room.language || "es-ES"}</span>
                <button type="button" className="karaoke__listen" onClick={playExamplePhrase} aria-label="Hear example">
                  ▶ Listen
                </button>
              </div>
              <p className="karaoke__line">
                {target.map((w, i) => (
                  <span
                    key={`${w}-${i}`}
                    className={`karaoke__word ${matchedWords[i] ? "is-matched" : ""} ${status === "recording" ? "is-listening" : ""}`}
                  >
                    {w}
                  </span>
                ))}
              </p>
              <p className="karaoke__translation">{room.translation}</p>
              {room.phonetic && <p className="karaoke__phonetic">{room.phonetic}</p>}
              {interimText && <p className="karaoke__interim">{interimText}</p>}
            </div>

            {/* Mic action */}
            <div className="mic-zone">
              <button
                type="button"
                className={`mic-orb ${isRecording ? "is-recording" : ""}`}
                onClick={isRecording ? stopRecording : startRecording}
                disabled={status === "scoring" || status === "loading"}
                aria-label={isRecording ? "Stop recording" : "Speak"}
              >
                <span className="mic-orb__icon">🎙</span>
                <span className="mic-orb__label">{isRecording ? "Listening…" : status === "scoring" ? "Pioneer thinking…" : "Speak, Traveler"}</span>
              </button>
              {status === "scoring" && <div className="mic-status">Pioneer GLiNER2 → extracting intent</div>}
            </div>

            {/* Score reveal */}
            {score && (
              <div className={`score-card score-card--${score.tier}`}>
                <div className="score-card__top">
                  <span className="score-card__tier">{score.tier?.toUpperCase()}</span>
                  <span className="score-card__num">{score.score}</span>
                </div>
                {score.pioneerExtraction && (
                  <div className="score-card__chips">
                    {score.pioneerExtraction.action && <span className="score-chip">{score.pioneerExtraction.action}</span>}
                    {score.pioneerExtraction.target && <span className="score-chip">{score.pioneerExtraction.target}</span>}
                    {score.pioneerExtraction.intent && <span className="score-chip score-chip--accent">{score.pioneerExtraction.intent}</span>}
                  </div>
                )}
                <div className="score-card__meta">{score.latencyMs}ms · Pioneer GLiNER2 · {score.fallback ? "fixture" : "live"}</div>
              </div>
            )}

            {/* Advance / retry */}
            {(status === "success" || status === "miss") && (
              <div className="cta-row">
                {status === "success" && (
                  <button type="button" className="cta-primary" onClick={advanceDungeon}>
                    {currentIdx + 1 >= totalRooms ? "Claim Victory ▸" : "Onward ▸"}
                  </button>
                )}
                {status === "miss" && (
                  <button type="button" className="cta-ghost" onClick={() => { setStatus("idle"); setScore(null); setInterimText(""); setMatchedWords([]); }}>
                    Try Again
                  </button>
                )}
              </div>
            )}

            {message && status !== "scoring" && <p className="room-stage__message">{message}</p>}
          </div>
          <img src="/assets/sora-character.png" alt="Sora" className="room-stage__character" />
        </section>
      )}

      {/* VICTORY VIEW */}
      {view === "victory" && (
        <section className="victory-stage" style={{ backgroundImage: `url(${ROOM_ART[2]})` }}>
          <div className="victory-stage__veil" />
          <div className="victory-stage__content">
            <p className="victory-eyebrow">VICTORY</p>
            <h2 className="victory-headline">The Bodega Remembers You</h2>
            <p className="victory-sub">You spoke the words. The eternal cat nods.</p>
            <div className="cta-row">
              <button type="button" className="cta-primary" onClick={resetGame}>Play Again</button>
              <button type="button" className="cta-ghost" onClick={() => setShowBenchmark(true)}>See Pioneer Benchmark</button>
            </div>
          </div>
        </section>
      )}

      {/* Benchmark modal */}
      {showBenchmark && (
        <div className="modal-backdrop" onClick={() => setShowBenchmark(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="modal__close" onClick={() => setShowBenchmark(false)} aria-label="Close">×</button>
            <BenchmarkPanel />
          </div>
        </div>
      )}

      {/* AI Inspector drawer */}
      {showInspector && (
        <div className="inspector-drawer">
          <div className="inspector-drawer__header">
            <h3>AI Inspector</h3>
            <button type="button" onClick={() => setShowInspector(false)} aria-label="Close inspector">×</button>
          </div>
          <p className="inspector-drawer__hint">Live status of every sponsor in the pipeline.</p>
          <PipelineRail steps={pipeline} />
          <div className="inspector-drawer__panels">
            <PioneerPanel creature={pioneer} />
            <FalPanel spriteStatus={falStatus} creature={null} />
          </div>
          <CitationChips lore={null} />
        </div>
      )}
    </div>
  );
}
