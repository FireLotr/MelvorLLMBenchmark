from __future__ import annotations

MINING_START_JS = """

(rockQuery) => {
  const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
  const q = norm(rockQuery);
  const m = game?.mining;
  if (!m?.actions?.allObjects) return { ok: false, error: "game.mining not ready" };

  const lvl = Number(m.level ?? 0);
  const rows = m.actions.allObjects.map((a) => ({
    name: a?.name ?? "Unknown",
    level: Number(a?.level ?? 0),
    unlocked: lvl >= Number(a?.level ?? 0),
    rock: a,
  }));

  let target = rows.find((r) => norm(r.name) === q);
  if (!target) {
    const partial = rows.filter((r) => q.length >= 1 && norm(r.name).includes(q));
    if (partial.length === 1) target = partial[0];
    else if (partial.length > 1) {
      return { ok: false, error: "ambiguous", matches: partial.map((r) => r.name) };
    } else return { ok: false, error: "unknown rock" };
  }

  if (!target.unlocked) {
    return { ok: false, error: "locked", level: target.level, name: target.name };
  }

  const getActiveRockSafe = () => {
    try { return m.activeRock ?? null; } catch (e) { return null; }
  };
  const wasActive = !!m.isActive;
  const activeBefore = getActiveRockSafe();
  if (wasActive && activeBefore === target.rock) {
    return { ok: true, name: target.name, alreadyActive: true, active: target.name };
  }

  try {
    m.onRockClick(target.rock);
  } catch (e) {
    return { ok: false, error: String(e) };
  }

  const activeAfter = getActiveRockSafe();
  const isActiveAfter = !!m.isActive;
  if (!isActiveAfter || activeAfter !== target.rock) {
    return {
      ok: false,
      error: "start did not apply",
      requested: target.name,
      active: activeAfter?.name ?? null,
    };
  }
  return { ok: true, name: target.name, active: target.name, switched: wasActive && activeBefore !== target.rock };
}

"""

MINING_STOP_JS = """
() => {
  const m = game?.mining;
  if (!m) return { ok: false, error: "no mining" };
  if (!m.isActive) return { ok: false, error: "not mining now" };
  const getActiveRockSafe = () => {
    try { return m.activeRock ?? null; } catch (e) { return null; }
  };
  const activeRock = getActiveRockSafe();
  if (!activeRock) return { ok: false, error: "could not resolve active rock" };
  try {
    m.onRockClick(activeRock);
  } catch (e) {
    return { ok: false, error: String(e) };
  }
  if (m.isActive) return { ok: false, error: "stop did not apply" };
  return { ok: true, stopped: true, rock: activeRock?.name ?? "Unknown Rock" };
}
"""
