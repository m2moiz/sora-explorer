"use client";

import { useMemo, useState } from "react";
import CreatureCard from "./CreatureCard";
import TurnLog from "./TurnLog";
import { samplePrompts } from "../../lib/creature";
import Announcer from "../voice/Announcer";
import VoiceRecorder from "../voice/VoiceRecorder";
import CitationChips from "../pipeline/CitationChips";
import FalPanel from "../pipeline/FalPanel";
import PioneerPanel from "../pipeline/PioneerPanel";
import PipelineRail from "../pipeline/PipelineRail";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function postJson(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

export default function BattleArena() {
  const [prompt, setPrompt] = useState(samplePrompts[0]);
  const [left, setLeft] = useState(null);
  const [right, setRight] = useState(null);
  const [leftLore, setLeftLore] = useState(null);
  const [rightLore, setRightLore] = useState(null);
  const [battle, setBattle] = useState(null);
  const [commentary, setCommentary] = useState(null);
  const [latestExtraction, setLatestExtraction] = useState(null);
  const [latestCreature, setLatestCreature] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("Offline fixture lane ready.");
  const [pipeline, setPipeline] = useState({
    voice: "waiting",
    pioneer: "waiting",
    tavily: "waiting",
    fal: "waiting",
    battle: "waiting",
    announcer: "waiting"
  });

  const activeHp = useMemo(() => {
    if (!battle?.turns?.length) return {};
    const last = battle.turns[battle.turns.length - 1];
    return { [battle.left.id]: last.leftHp, [battle.right.id]: last.rightHp };
  }, [battle]);

  function setStep(key, value) {
    setPipeline((current) => ({ ...current, [key]: value }));
  }

  async function enrichLore(creature, slot) {
    setStep("tavily", "running");
    try {
      const lore = await postJson("/api/creature/lore", {
        name: creature.name,
        element: creature.element,
        abilities: creature.abilities,
        weaknesses: creature.weaknesses
      });
      if (slot === "left") setLeftLore(lore);
      if (slot === "right") setRightLore(lore);
      setStep("tavily", lore.fallback ? "fallback" : "done");
      return lore;
    } catch {
      setStep("tavily", "error");
      return null;
    }
  }

  async function addSprite(creature, description) {
    setStep("fal", "running");
    try {
      const visualCreature = await postJson("/api/creature/sprite", { description, creature });
      setStep("fal", visualCreature.fallback ? "fallback" : "done");
      return visualCreature;
    } catch {
      setStep("fal", "error");
      return creature;
    }
  }

  async function createCreature(slot, description = prompt) {
    setLoading(true);
    setMessage(`Summoning ${slot} creature...`);
    setStep("pioneer", "running");
    try {
      const creature = await postJson("/api/creature/extract", { description });
      setStep("pioneer", creature.fallback ? "fallback" : "done");
      setLatestExtraction(creature);
      const visualCreature = await addSprite(creature, description);
      await enrichLore(visualCreature, slot);
      if (slot === "left") setLeft(visualCreature);
      if (slot === "right") setRight(visualCreature);
      setLatestCreature(visualCreature);
      setBattle(null);
      setCommentary(null);
      setStep("battle", "waiting");
      setStep("announcer", "waiting");
      setMessage(`${visualCreature.name} loaded into the ${slot} slot.`);
    } catch (error) {
      setStep("pioneer", "error");
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function runBattle() {
    if (!left || !right) {
      setMessage("Load both creature slots first.");
      return;
    }
    setLoading(true);
    setMessage("Resolving deterministic battle...");
    setStep("battle", "running");
    try {
      const result = await postJson("/api/battle", { left, right });
      setBattle(result);
      setStep("battle", "done");
      setStep("announcer", "running");
      setMessage(`${result.winnerName} wins the coliseum round.`);
      try {
        const nextCommentary = await postJson("/api/commentary", {
          winner: result.winnerName,
          turnLog: result.turns,
          left: result.left,
          right: result.right
        });
        setCommentary(nextCommentary);
        setStep("announcer", nextCommentary.fallback ? "fallback" : "done");
      } catch {
        setStep("announcer", "error");
      }
    } catch (error) {
      setStep("battle", "error");
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  function handleTranscript(transcript) {
    setPrompt(transcript);
    setStep("voice", "fallback");
    setMessage("Voice transcript loaded into the prompt field.");
  }

  const activeLore = rightLore || leftLore;
  const announcerText =
    commentary?.commentary ||
    (battle?.winnerName ? `${battle.winnerName} wins the coliseum round.` : "The arena awaits a clean challenger reveal.");

  return (
    <main className="arena-shell">
      <section className="command-deck">
        <div>
          <p className="eyebrow">Procedural Coliseum</p>
          <h1>Summon two creatures. Let the arena decide.</h1>
        </div>
        <PipelineRail steps={pipeline} />
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          rows={3}
          aria-label="Creature concept"
        />
        <div className="sample-grid">
          {samplePrompts.map((sample) => (
            <button key={sample} type="button" onClick={() => setPrompt(sample)}>
              {sample.split(" ").slice(1, 3).join(" ")}
            </button>
          ))}
        </div>
        <div className="actions">
          <button type="button" onClick={() => createCreature("left")} disabled={loading}>
            Load Left
          </button>
          <button type="button" onClick={() => createCreature("right")} disabled={loading}>
            Load Right
          </button>
          <button type="button" className="primary" onClick={runBattle} disabled={loading || !left || !right}>
            Battle
          </button>
        </div>
        <p className="status-line">{message}</p>
      </section>

      <section className="sponsor-panels">
        <VoiceRecorder onTranscript={handleTranscript} />
        <PioneerPanel creature={latestExtraction} />
        <FalPanel creature={latestCreature} />
      </section>

      <section className="battlefield">
        <CreatureCard
          creature={left}
          side="Left challenger"
          activeHp={left ? activeHp[left.id] : undefined}
          visualState={battle?.winnerId === left?.id ? "victory" : battle ? "damage" : "entrance"}
        />
        <div className="versus">
          <span>VS</span>
          {battle?.winnerName ? <strong>{battle.winnerName}</strong> : <strong>Deterministic</strong>}
        </div>
        <CreatureCard
          creature={right}
          side="Right challenger"
          activeHp={right ? activeHp[right.id] : undefined}
          visualState={battle?.winnerId === right?.id ? "victory" : battle ? "damage" : "entrance"}
        />
      </section>

      <CitationChips lore={activeLore} />
      <Announcer text={announcerText} autoPlay={Boolean(commentary?.commentary)} />
      <TurnLog turns={battle?.turns || []} winnerName={battle?.winnerName} />
    </main>
  );
}
