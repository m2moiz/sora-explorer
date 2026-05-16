// Tiny pub/sub bus so React can push game events into Kaplay scenes
// and Kaplay can emit events back without prop-drilling.
const listeners = new Map();

export const gameBus = {
  on(event, fn) {
    if (!listeners.has(event)) listeners.set(event, new Set());
    listeners.get(event).add(fn);
    return () => listeners.get(event)?.delete(fn);
  },
  emit(event, payload) {
    listeners.get(event)?.forEach((fn) => {
      try { fn(payload); } catch (err) { console.error("gameBus listener error:", err); }
    });
  },
  clear() { listeners.clear(); },
};
