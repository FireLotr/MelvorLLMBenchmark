from __future__ import annotations

SMITHING_STATE_JS = """() => {
    const s = game?.smithing;
    if (!s) return { ok: false, error: "no smithing" };
    let isSmithing = false;
    try { isSmithing = !!s?.isActive; } catch (e) { isSmithing = false; }
    let active = null;
    try { active = s?.activeRecipe?.name ?? null; } catch (e) { active = null; }
    const rows = (s?.actions?.allObjects ?? []).map((a) => {
        let unlocked = false;
        try { unlocked = !!s?.isMasteryActionUnlocked?.(a); } catch (e) {}
        const costs = [];
        try {
            for (const ic of a?.itemCosts ?? []) {
                costs.push({
                    quantity: Number(ic?.quantity ?? 0),
                    name: ic?.item?.name ?? "",
                    id: ic?.item?.id ?? "",
                });
            }
        } catch (e) {}
        return {
            name: a?.name ?? "Unknown",
            level: Number(a?.level ?? 0),
            xp: Number(a?.baseExperience ?? 0),
            unlocked,
            itemCosts: costs,
        };
    });
    return { ok: true, level: Number(s?.level ?? 0), active, isSmithing, rows };
}"""

SMITHING_GLOVES_JS = """() => {
    const eq = (game?.combat?.player?.equipment?.equippedArray ?? [])
        .find((e) => String(e?.slot?.id ?? "").toLowerCase().includes("gloves"));
    const item = eq?.item ?? null;
    if (!item || String(item?.id ?? "").includes("Empty_Equipment")) {
        return { ok: true, equipped: false, name: null, charges: null };
    }
    const name = String(item?.name ?? "Unknown Gloves");
    let charges = null;
    try { charges = Number(game?.itemCharges?.getCharges?.(item) ?? 0); } catch (e) { charges = null; }
    return { ok: true, equipped: true, name, charges };
}"""
