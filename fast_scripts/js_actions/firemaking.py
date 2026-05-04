from __future__ import annotations

FIREMAKING_BONFIRE_START_JS = """
(query) => {
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const f = game?.firemaking;
    if (!f) return { ok:false, error:"no firemaking" };
    if (typeof f?.lightBonfire !== "function") return { ok:false, error:"lightBonfire is unavailable" };
    const safeActiveRecipe = () => {
        try { return f.activeRecipe ?? null; } catch (e) { return null; }
    };
    const safeSelectedRecipe = () => {
        try { return f.selectedRecipe ?? null; } catch (e) { return null; }
    };
    const q = norm(query);
    let selectedRecipe = safeSelectedRecipe() ?? safeActiveRecipe();
    if (q) {
        const actions = Array.from(f?.actions?.allObjects ?? []);
        const exact = actions.filter((a) => norm(a?.name) === q);
        const picks = exact.length ? exact : actions.filter((a) => q && norm(a?.name).includes(q));
        if (picks.length !== 1) return { ok:false, error:"Unknown or ambiguous log" };
        const wanted = picks[0];
        if (!f?.isMasteryActionUnlocked?.(wanted)) {
            return { ok:false, error:`Log locked: ${wanted?.name ?? "Unknown"}` };
        }
        if (typeof f?.selectLog !== "function") return { ok:false, error:"selectLog is unavailable" };
        try { f.selectLog(wanted); } catch (e) { return { ok:false, error:String(e?.message ?? e) }; }
        selectedRecipe = wanted;
    }
    if (!selectedRecipe) {
        return { ok:false, error:"no log selected for bonfire" };
    }
    const bonfireCost = Number(selectedRecipe?.bonfireCost ?? 10);
    const logItem = selectedRecipe?.log ?? null;
    const ownedLogs = Number(game?.bank?.getQty?.(logItem) ?? 0);
    if (!Number.isFinite(ownedLogs) || ownedLogs < bonfireCost) {
        return {
            ok:false,
            error:`not enough logs for bonfire: need ${bonfireCost}, have ${Number.isFinite(ownedLogs) ? ownedLogs : 0}`,
            log: selectedRecipe?.name ?? logItem?.name ?? null,
            required: bonfireCost,
            owned: Number.isFinite(ownedLogs) ? ownedLogs : 0,
        };
    }
    try {
        f.lightBonfire();
        return { ok:true };
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
}
"""

FIREMAKING_BONFIRE_STOP_JS = """
() => {
    const f = game?.firemaking;
    if (!f) return { ok:false, error:"no firemaking" };
    const methods = ["stopBonfire", "endBonfire", "onBonfireStop"];
    for (const m of methods) {
        if (typeof f?.[m] === "function") {
            try { f[m](); return { ok:true }; } catch (e) {}
        }
    }
    const btn = document.querySelector("#firemaking-bonfire-menu button.btn-danger");
    if (!btn) return { ok:true, message:"Bonfire not active" };
    btn.click();
    return { ok:true };
}
"""

FIREMAKING_SELECT_JS = """
(query) => {
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const f = game?.firemaking;
    const q = norm(query);
    if (!f) return { ok:false, error:"no firemaking" };
    const actions = (f?.actions?.allObjects ?? []);
    const exact = actions.filter((a) => norm(a?.name) === q);
    const picks = exact.length ? exact : actions.filter((a) => q && norm(a?.name).includes(q));
    if (picks.length !== 1) return { ok:false, error:"Unknown or ambiguous log" };
    const a = picks[0];
    if (!f?.isMasteryActionUnlocked?.(a)) return { ok:false, error:`Log locked: ${a?.name ?? "Unknown"}` };
    if (typeof f?.selectLog !== "function") {
        return { ok:false, error:"selectLog is unavailable" };
    }
    try {
        f.selectLog(a);
        return { ok:true, log:a?.name ?? "Unknown" };
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
}
"""

FIREMAKING_START_JS = """
(query) => {
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const f = game?.firemaking;
    if (!f) return { ok:false, error:"no firemaking" };
    if (typeof f?.burnLog !== "function") return { ok:false, error:"burnLog is unavailable" };

    const safeActiveRecipe = () => {
        try { return f.activeRecipe ?? null; } catch (e) { return null; }
    };
    const safeSelectedRecipe = () => {
        try { return f.selectedRecipe ?? null; } catch (e) { return null; }
    };
    const safeSelectedLog = () => {
        try { return f.selectedLog ?? null; } catch (e) { return null; }
    };

    const q = norm(query);
    const actions = Array.from(f?.actions?.allObjects ?? []);
    let wanted = null;
    if (q) {
        const exact = actions.filter((a) => norm(a?.name) === q);
        const picks = exact.length ? exact : actions.filter((a) => q && norm(a?.name).includes(q));
        if (picks.length !== 1) return { ok:false, error:"Unknown or ambiguous log" };
        wanted = picks[0];
        if (!f?.isMasteryActionUnlocked?.(wanted)) {
            return { ok:false, error:`Log locked: ${wanted?.name ?? "Unknown"}` };
        }
    }

    const selected = safeSelectedRecipe() ?? safeActiveRecipe() ?? safeSelectedLog();
    const sameWantedSelected = !!wanted && selected === wanted;
    const activeRecipe = safeActiveRecipe();
    const sameWantedActive = !!wanted && activeRecipe === wanted;

    if (f?.isActive && (sameWantedActive || sameWantedSelected || !wanted)) {
        return { ok:true, alreadyActive:true, log:(wanted?.name ?? activeRecipe?.name ?? selected?.name ?? null) };
    }

    if (wanted && !sameWantedSelected) {
        if (typeof f?.selectLog !== "function") return { ok:false, error:"selectLog is unavailable" };
        try { f.selectLog(wanted); } catch (e) { return { ok:false, error:String(e?.message ?? e) }; }
    }

    if (f?.isActive) {
        try { f.burnLog(); } catch (e) { return { ok:false, error:String(e?.message ?? e) }; }
        if (f?.isActive) return { ok:false, error:"could not stop current burn before switching logs" };
    }

    try { f.burnLog(); } catch (e) { return { ok:false, error:String(e?.message ?? e) }; }
    if (!f?.isActive) return { ok:false, error:"start did not apply" };
    let logName = wanted?.name ?? null;
    if (!logName) {
        const ar = safeActiveRecipe();
        const sr = safeSelectedRecipe();
        logName = ar?.name ?? sr?.name ?? null;
    }
    return { ok:true, started:true, log: logName };
}
"""

FIREMAKING_STOP_JS = """
() => {
    const fm = game?.firemaking;
    if (!fm) return { ok:false, error:"no firemaking" };
    if (!fm?.isActive) return { ok:false, error:"not burning now" };
    try {
        fm.burnLog();
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
    if (fm?.isActive) return { ok:false, error:"stop did not apply" };
    return { ok:true, stopped:true };
}
"""
