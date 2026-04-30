from __future__ import annotations

COOKING_IS_ACTIVE_JS = """
() => !!game?.cooking?.isActive
"""

COOKING_LIST_JS = """
() => {
    const c = game?.cooking;
    return (c?.actions?.allObjects ?? []).map(a => ({
        name: a?.name ?? "Unknown",
        unlocked: !!(c?.isMasteryActionUnlocked?.(a)),
        level: Number(a?.level ?? 0),
    }));
}
"""

COOKING_START_JS = """
(recipeName) => {
    const c = game?.cooking;
    const recipe = (c?.actions?.allObjects ?? []).find(a => a?.name === recipeName);
    if (!recipe) return { ok:false, error:"recipe not found" };
    const sameActiveRecipe = (() => {
        if (!c?.isActive) return false;
        try {
            const active = c.activeRecipe;
            return !!active && String(active?.name ?? "") === String(recipe?.name ?? "");
        } catch (e) {
            return false;
        }
    })();
    if (sameActiveRecipe) {
        return { ok:true, alreadyActive:true };
    }
    try { c.onRecipeSelectionClick(recipe); } catch (e) { return { ok:false, error:String(e) }; }
    try { 
        c.onActiveCookButtonClick(recipe.category); 
        return { ok:true }; 
    } catch (e) { 
        return { ok:false, error:String(e) }; 
    }
}
"""

COOKING_STOP_JS = """
() => {
    const c = game?.cooking;
    if (!c) return { ok:false, error:"no cooking" };
    if (!c?.isActive) return { ok:false, error:"not cooking now" };
    if (typeof c?.stop === "function") {
        try { c.stop(); return { ok:true, via:"stop" }; } catch (e) {}
    }
    return { ok:false, error:"cooking.stop unavailable" };
}
"""
