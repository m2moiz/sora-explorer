import kaplay from "kaplay";
import { gameBus } from "../../lib/gameBus";

// World layout: 3 room nodes connected by a winding path along the map.
// Coordinates are tuned for a 1280x720 canvas; sprite scales with viewport.
const NODES = [
  { id: 0, x: 220, y: 540, label: "MERCHANT", kind: "merchant" },
  { id: 1, x: 640, y: 360, label: "ENEMY", kind: "enemy" },
  { id: 2, x: 1060, y: 540, label: "BOSS", kind: "boss" },
];

export function bootGameWorld(canvasEl) {
  const k = kaplay({
    canvas: canvasEl,
    width: 1280,
    height: 720,
    letterbox: true,
    background: [10, 14, 26],
    crisp: true,
    global: false,
    touchToMouse: true,
  });

  // Asset loads (best-effort — if missing, fall back to procedural shapes)
  k.loadSprite("map", "/assets/dungeon-map.png").catch(() => {});
  k.loadSprite("sora", "/assets/sora-character.png").catch(() => {});

  // Background map — full-bleed
  const bg = k.add([
    k.sprite("map", { width: 1280, height: 720 }),
    k.pos(0, 0),
    k.opacity(0.85),
    k.z(0),
  ]);

  // Dim veil so HUD is readable
  k.add([
    k.rect(1280, 720),
    k.pos(0, 0),
    k.color(8, 12, 28),
    k.opacity(0.45),
    k.z(1),
  ]);

  // Path lines between nodes (drawn under nodes)
  for (let i = 0; i < NODES.length - 1; i++) {
    const a = NODES[i];
    const b = NODES[i + 1];
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    const ang = Math.atan2(dy, dx) * (180 / Math.PI);
    k.add([
      k.rect(len, 4),
      k.pos(a.x, a.y),
      k.rotate(ang),
      k.color(244, 211, 94),
      k.opacity(0.5),
      k.z(2),
    ]);
  }

  // Room nodes — pulsing yellow circles with kind label
  const nodeRefs = NODES.map((n, idx) => {
    const ring = k.add([
      k.circle(36),
      k.pos(n.x, n.y),
      k.color(244, 211, 94),
      k.outline(3, k.rgb(255, 255, 255)),
      k.anchor("center"),
      k.z(3),
      "node",
      { idx, cleared: false },
    ]);
    k.add([
      k.text(String(idx + 1), { size: 28, font: "monospace" }),
      k.pos(n.x, n.y),
      k.anchor("center"),
      k.color(20, 20, 30),
      k.z(4),
    ]);
    k.add([
      k.text(n.label, { size: 16, font: "monospace" }),
      k.pos(n.x, n.y + 62),
      k.anchor("center"),
      k.color(255, 255, 255),
      k.opacity(0.85),
      k.z(4),
    ]);
    // Pulsing animation
    ring.onUpdate(() => {
      const t = k.time();
      const pulse = 1 + Math.sin(t * 3 + idx) * 0.08;
      ring.scale = k.vec2(pulse, pulse);
    });
    return ring;
  });

  // Sora sprite — starts at node 0
  let sora;
  try {
    sora = k.add([
      k.sprite("sora", { width: 96, height: 96 }),
      k.pos(NODES[0].x, NODES[0].y - 80),
      k.anchor("center"),
      k.z(5),
      "sora",
    ]);
  } catch {
    sora = k.add([
      k.rect(48, 64),
      k.pos(NODES[0].x, NODES[0].y - 80),
      k.color(160, 130, 220),
      k.outline(3, k.rgb(255, 255, 255)),
      k.anchor("center"),
      k.z(5),
      "sora",
    ]);
  }

  // Bobbing idle animation
  const baseY = () => sora.pos.y;
  let bobBase = NODES[0].y - 80;
  sora.onUpdate(() => {
    const t = k.time();
    sora.pos.y = bobBase + Math.sin(t * 4) * 4;
  });

  // Hearts HUD (top-left)
  let hp = 3;
  const hearts = [];
  function renderHearts() {
    hearts.forEach((h) => h.destroy());
    hearts.length = 0;
    for (let i = 0; i < 3; i++) {
      hearts.push(
        k.add([
          k.text(i < hp ? "♥" : "♡", { size: 38, font: "monospace" }),
          k.pos(32 + i * 44, 32),
          k.color(i < hp ? k.rgb(238, 90, 124) : k.rgb(120, 90, 100)),
          k.fixed(),
          k.z(10),
        ]),
      );
    }
  }
  renderHearts();

  // Coins HUD
  let coins = 0;
  const coinLabel = k.add([
    k.text("◎ 0", { size: 28, font: "monospace" }),
    k.pos(1280 - 140, 32),
    k.color(244, 211, 94),
    k.fixed(),
    k.z(10),
  ]);

  // Streak HUD
  let streak = 0;
  const streakLabel = k.add([
    k.text("", { size: 24, font: "monospace" }),
    k.pos(1280 - 140, 70),
    k.color(255, 140, 80),
    k.fixed(),
    k.z(10),
  ]);

  // Walk Sora to a target node by index
  function walkToNode(idx) {
    const target = NODES[Math.min(idx, NODES.length - 1)];
    if (!target) return;
    const targetY = target.y - 80;
    const startX = sora.pos.x;
    const startY = bobBase;
    const dist = Math.hypot(target.x - startX, targetY - startY);
    const dur = Math.max(0.6, Math.min(1.6, dist / 600));
    bobBase = startY; // freeze bob baseline during walk
    k.tween(
      startX,
      target.x,
      dur,
      (v) => { sora.pos.x = v; },
      k.easings.easeInOutQuad,
    );
    k.tween(
      startY,
      targetY,
      dur,
      (v) => { bobBase = v; },
      k.easings.easeInOutQuad,
    ).onEnd(() => {
      gameBus.emit("arrivedAtNode", { idx });
    });
  }

  // Particle burst at sora position
  function burst(color = [244, 211, 94], count = 14) {
    for (let i = 0; i < count; i++) {
      const ang = (Math.PI * 2 * i) / count;
      const speed = 80 + Math.random() * 60;
      const p = k.add([
        k.circle(4 + Math.random() * 3),
        k.pos(sora.pos.x, sora.pos.y),
        k.color(...color),
        k.opacity(1),
        k.z(6),
        k.lifespan(0.8, { fade: 0.6 }),
        k.move(k.vec2(Math.cos(ang) * speed, Math.sin(ang) * speed)),
      ]);
    }
  }

  // Event subscriptions from React
  const offs = [];
  offs.push(gameBus.on("walkTo", ({ idx }) => walkToNode(idx)));
  offs.push(gameBus.on("scoreSuccess", ({ tier, coinsDelta = 0 }) => {
    const color = tier === "excellent" ? [120, 240, 180] : [244, 211, 94];
    burst(color, tier === "excellent" ? 22 : 14);
    streak += 1;
    coins += coinsDelta || (tier === "excellent" ? 10 : 5);
    coinLabel.text = `◎ ${coins}`;
    if (streak >= 2) {
      streakLabel.text = `🔥 x${streak}`;
      if (streak >= 3) burst([255, 140, 80], 10);
    }
    // Mark current node cleared
    const here = nodeRefs.find((n) => Math.abs(n.pos.x - sora.pos.x) < 50);
    if (here) {
      here.cleared = true;
      here.color = k.rgb(120, 240, 180);
    }
  }));
  offs.push(gameBus.on("scoreMiss", () => {
    hp = Math.max(0, hp - 1);
    streak = 0;
    streakLabel.text = "";
    renderHearts();
    burst([238, 90, 124], 10);
    // Camera shake
    k.shake(8);
    if (hp <= 0) {
      gameBus.emit("youDied", {});
    }
  }));
  offs.push(gameBus.on("resetRun", () => {
    hp = 3;
    coins = 0;
    streak = 0;
    coinLabel.text = "◎ 0";
    streakLabel.text = "";
    renderHearts();
    sora.pos.x = NODES[0].x;
    bobBase = NODES[0].y - 80;
    nodeRefs.forEach((n) => { n.cleared = false; n.color = k.rgb(244, 211, 94); });
  }));

  // Return teardown so React can clean up
  return () => {
    offs.forEach((off) => off && off());
    try { k.quit(); } catch {}
  };
}
