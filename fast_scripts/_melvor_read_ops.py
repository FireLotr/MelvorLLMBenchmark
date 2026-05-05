"""Read-only in-page JSON snapshots for melvor_daemon `op: read` (no navigation; pure game state)."""

from __future__ import annotations

# Each returns a small JSON-serializable object for benchmarking / quick inspection.

READ_JS: dict[str, str] = {
    "game_ready": r"""() => ({
  ok: typeof game !== "undefined" && !!game?.bank,
  hasGame: typeof game !== "undefined"
})""",
    "mining": r"""() => {
  const m = game?.mining;
  if (!m) return { ok: false, error: "no mining" };
  let active = null;
  try { active = m?.activeRock?.name ?? null; } catch (e) { active = null; }
  return {
    ok: true,
    level: Number(m.level ?? 0),
    active: active,
    actions: (m?.actions?.allObjects ?? []).length
  };
}""",
    "woodcutting": r"""() => {
  const wc = game?.woodcutting;
  if (!wc) return { ok: false, error: "no woodcutting" };
  return {
    ok: true,
    level: Number(wc.level ?? 0),
    active: wc?.activeTrees ? Array.from(wc.activeTrees).map(t => t?.name) : [],
    actions: (wc?.actions?.allObjects ?? []).length
  };
}""",
    "fishing": r"""() => {
  const f = game?.fishing;
  if (!f) return { ok: false, error: "no fishing" };
  return {
    ok: true,
    level: Number(f.level ?? 0),
    areas: (f?.areas?.allObjects ?? []).length
  };
}""",
    "firemaking": r"""() => {
  const fm = game?.firemaking;
  if (!fm) return { ok: false, error: "no firemaking" };
  return { ok: true, level: Number(fm.level ?? 0), actions: (fm?.actions?.allObjects ?? []).length };
}""",
    "cooking": r"""() => {
  const c = game?.cooking;
  if (!c) return { ok: false, error: "no cooking" };
  const n = (c?.recipes?.allObjects ?? []).length;
  return { ok: true, level: Number(c.level ?? 0), recipeCount: n };
}""",
    "smithing": r"""() => {
  const s = game?.smithing;
  if (!s) return { ok: false, error: "no smithing" };
  return { ok: true, level: Number(s.level ?? 0), actions: (s?.actions?.allObjects ?? []).length };
}""",
    "farming": r"""() => {
  const f = game?.farming;
  if (!f) return { ok: false, error: "no farming" };
  return { ok: true, level: Number(f.level ?? 0) };
}""",
    "skills": r"""() => {
  if (!game?.skills) return { ok: false, error: "no skills" };
  const all = game.skills?.allObjects ?? [];
  return {
    ok: true,
    n: all.length,
    first5: (all ?? []).slice(0, 5).map((s) => ({ name: s?.name, level: Number(s?.level ?? 0) }))
  };
}""",
    "bank_space": r"""() => {
  const b = game?.bank;
  if (!b) return { ok: false, error: "no bank" };
  const used = Number(b.occupiedSlots ?? b.usedSlots ?? 0);
  const maxS = Number(b.maximumSlots ?? b.maxSlots ?? 0);
  return { ok: true, used, max: maxS };
}""",
    "equipment": r"""() => {
  const p = game?.combat?.player;
  const eq = p?.equipment?.equippedArray ?? [];
  if (!p) return { ok: false, error: "no player" };
  const equipped = (eq ?? []).filter((r) => {
    const id = String(r?.item?.id ?? "");
    return id && !id.endsWith("Empty_Equipment");
  }).map((r) => ({ slot: String(r?.slot?.name ?? r?.slot?.id ?? "Unknown"), name: String(r?.item?.name ?? "Unknown"), qty: Number(r?.quantity ?? 0) }));
  return { ok: true, slots: Number(eq.length || 0), equippedCount: equipped.length, equipped };
}""",
    "shop": r"""() => {
  const s = game?.shop;
  if (!s) return { ok: false, error: "no shop" };
  const gp = Number(game?.gp?.amount ?? game?.gp ?? 0);
  const sc = Number(game?.slayerCoins?.amount ?? game?.slayerCoins ?? 0);
  return { ok: true, purchases: (s?.purchases?.allObjects ?? []).length, gp, slayerCoins: sc };
}""",
    "combat": r"""() => {
  const c = game?.combat?.player;
  if (!c) return { ok: false, error: "no combat player" };
  return {
    ok: true,
    hp: Number(c.hitpoints ?? 0),
    maxHp: Number(c?.stats?._maxHitpoints ?? c?.stats?.maxHitpoints ?? 0)
  };
}""",
    "account_age": r"""() => {
  try {
    const general = game?.stats?.General;
    if (!general?.get) return { ok: false, error: "no general stats" };
    const created = Number(general.get((typeof GeneralStats !== "undefined" ? GeneralStats.AccountCreationDate : 3)));
    if (!Number.isFinite(created) || created <= 0) return { ok: false, error: "account creation date unavailable" };
    const elapsedMs = Math.max(0, Date.now() - created);
    const accountAge = typeof formatAsTimePeriod === "function"
      ? formatAsTimePeriod(elapsedMs)
      : `${Math.floor(elapsedMs / 86400000)}d`;
    return { ok: true, accountAge, accountCreationTimestampMs: created, elapsedMs };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}""",
}

MASTERY_BRIEF_JS = r"""(skillKey) => {
  const k = String(skillKey || "fishing").toLowerCase();
  const s = game?.[k];
  if (!s) return { ok: false, error: "skill not found: " + k };
  const r = s?.currentRealm;
  return {
    ok: true,
    pool: Number(s?.getMasteryPoolXP?.(r) ?? 0),
    totalMastery: Number(s?.getTotalCurrentMasteryLevelInRealm?.(r) ?? 0)
  };
}"""


def list_read_kinds() -> list[str]:
    return sorted(READ_JS.keys()) + ["mastery"]
