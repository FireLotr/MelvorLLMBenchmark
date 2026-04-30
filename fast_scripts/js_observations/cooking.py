from __future__ import annotations

COOKING_LIST_JS = """() => {
    const c = game?.cooking;
    if (!c) return { ok:false, error:"no cooking" };
    let selectedRecipe = null;
    try { selectedRecipe = c?.activeRecipe?.name ?? null; } catch (e) { selectedRecipe = null; }
    let isCooking = false;
    try { isCooking = !!c?.isActive; } catch (e) { isCooking = false; }
    const rows = (c?.actions?.allObjects ?? []).map((a) => {
        let unlocked = false;
        try { unlocked = !!c?.isMasteryActionUnlocked?.(a); } catch (e) {}
        let interval = null;
        try { interval = Number(c?.getRecipeCookingInterval?.(a)); } catch (e) {}
        return {
            name: a?.name ?? "Unknown",
            category: a?.category?.name ?? a?.category?.id ?? "Unknown",
            level: Number(a?.level ?? 0),
            xp: Number(a?.baseExperience ?? 0),
            interval,
            unlocked,
        };
    });
    return {
        ok: true,
        level: Number(c?.level ?? 0),
        selectedRecipe,
        isCooking,
        rows,
    };
}"""

COOKING_GLOVES_JS = """() => {
    const eq = (game?.combat?.player?.equipment?.equippedArray ?? [])
        .find((e) => String(e?.slot?.id ?? "").toLowerCase().includes("gloves"));
    const item = eq?.item ?? null;
    if (!item || String(item?.id ?? "").includes("Empty_Equipment")) {
        return { ok:true, equipped: false, name: null, charges: null };
    }
    const name = String(item?.name ?? "Unknown Gloves");
    let charges = null;
    try { charges = Number(game?.itemCharges?.getCharges?.(item) ?? 0); } catch (e) { charges = null; }
    return { ok:true, equipped: true, name, charges };
}"""
