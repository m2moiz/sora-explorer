"use client";

import { useEffect, useRef } from "react";

export default function GameCanvas({ roomIndex = 0 }) {
  const canvasRef = useRef(null);
  const teardownRef = useRef(null);
  const lastIdxRef = useRef(-1);

  useEffect(() => {
    if (!canvasRef.current) return;
    let cancelled = false;

    (async () => {
      const { bootGameWorld } = await import("./gameWorld");
      const { gameBus } = await import("../../lib/gameBus");
      if (cancelled || !canvasRef.current) return;
      teardownRef.current = bootGameWorld(canvasRef.current);
      // Dev-only: expose for manual demo testing
      if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
        window.__gameBus = gameBus;
      }
      // Snap to current room on first mount
      if (roomIndex !== lastIdxRef.current) {
        gameBus.emit("walkTo", { idx: roomIndex });
        lastIdxRef.current = roomIndex;
      }
    })();

    return () => {
      cancelled = true;
      try { teardownRef.current?.(); } catch {}
      teardownRef.current = null;
    };
  }, []);

  // Walk sora when roomIndex changes
  useEffect(() => {
    if (lastIdxRef.current === -1) return; // boot effect will handle initial
    if (lastIdxRef.current === roomIndex) return;
    let cancelled = false;
    (async () => {
      const { gameBus } = await import("../../lib/gameBus");
      if (cancelled) return;
      gameBus.emit("walkTo", { idx: roomIndex });
      lastIdxRef.current = roomIndex;
    })();
    return () => { cancelled = true; };
  }, [roomIndex]);

  return (
    <div className="game-canvas-wrap" aria-hidden="false">
      <canvas ref={canvasRef} className="game-canvas" />
    </div>
  );
}
