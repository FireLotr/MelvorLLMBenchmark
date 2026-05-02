from __future__ import annotations

SMITHING_LIST_JS = """
() => {
    const s = game?.smithing;
    return (s?.actions?.allObjects ?? []).map(a => ({
        name: a?.name ?? "Unknown",
        unlocked: !!(s?.isMasteryActionUnlocked?.(a)),
        level: Number(a?.level ?? 0),
    }));
}
"""

SMITHING_START_JS = """
(recipeName) => {
    const norm = (x) => String(x ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const s = game?.smithing;
    if (!s) return { ok:false, error:"no smithing" };
    const q = norm(recipeName);
    const recipes = Array.from(s?.actions?.allObjects ?? []);
    const exact = recipes.filter((a) => norm(a?.name) === q);
    const picks = exact.length ? exact : recipes.filter((a) => q && norm(a?.name).includes(q));
    if (picks.length !== 1) return { ok:false, error:"Unknown or ambiguous recipe" };
    const recipe = picks[0];
    if (!recipe) return { ok:false, error:"recipe not found" };
    if (!s?.isMasteryActionUnlocked?.(recipe)) return { ok:false, error:`Recipe locked: ${recipe?.name ?? recipeName}` };

    const getSelectedRecipeSafe = () => {
        try { return s?.selectedRecipe ?? null; } catch (e) { return null; }
    };
    const getActiveRecipeSafe = () => {
        try { return s?.activeRecipe ?? null; } catch (e) { return null; }
    };
    const selected = getSelectedRecipeSafe();
    const active = getActiveRecipeSafe();
    if (s?.isActive && (active === recipe || selected === recipe)) {
        return { ok:true, alreadyActive:true, recipe: recipe?.name ?? recipeName };
    }

    if (typeof s?.selectRecipeOnClick !== "function") return { ok:false, error:"selectRecipeOnClick unavailable" };
    if (typeof s?.createButtonOnClick !== "function") return { ok:false, error:"createButtonOnClick unavailable" };

    try {
        s.selectRecipeOnClick(recipe);
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
    try {
        s.createButtonOnClick();
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
    if (!s?.isActive) {
        return { ok:false, error:"could not start smithing (likely missing costs/ingredients or blocked by current state)" };
    }
    return { ok:true, started:true, recipe: recipe?.name ?? recipeName };
}
"""

# Smithing extends ArtisanSkill: interval lives on the skill (currentActionInterval / actionInterval / baseInterval).
SMITHING_ACTION_INTERVAL_MS_JS = """
() => {
    const s = game?.smithing;
    if (!s?.isActive) return { ok: false, error: "smithing not active" };
    const ms = Number(s.currentActionInterval ?? s.actionInterval ?? s.baseInterval ?? NaN);
    if (!Number.isFinite(ms) || ms <= 0) {
        return { ok: false, error: "could not read action interval" };
    }
    return { ok: true, intervalMs: ms };
}
"""

SMITHING_STOP_JS = """
() => {
    const s = game?.smithing;
    if (!s) return { ok:false, error:"no smithing" };
    if (!s?.isActive) return { ok:false, error:"not smithing now" };
    if (typeof s?.createButtonOnClick !== "function") return { ok:false, error:"createButtonOnClick unavailable" };
    try {
        s.createButtonOnClick();
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
    if (s?.isActive) return { ok:false, error:"stop did not apply" };
    return { ok:true, stopped:true };
}
"""
