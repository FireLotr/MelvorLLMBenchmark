from __future__ import annotations

FARMING_CATEGORY_ACTION_JS = """
(pack) => {
    const category = String(pack?.category ?? "Allotments");
    const labelRegex = String(pack?.labelRegex ?? "");
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const clickByText = (root, sel, rx) => {
        const nodes = Array.from((root || document).querySelectorAll(sel));
        for (const el of nodes) {
            const txt = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && rx.test(txt)) { el.click(); return true; }
        }
        return false;
    };
    const chooseCategory = () => {
        const buttons = Array.from(document.querySelectorAll("farming-category-button"));
        for (const b of buttons) {
            const txt = norm((b.innerText || b.textContent || "").split("\n").find((x) => x.trim()) || "");
            if (txt === norm(category)) { b.click(); return true; }
        }
        return false;
    };
    chooseCategory();
    if (!labelRegex) return { ok:false, error:"missing labelRegex" };
    return { ok: clickByText(document, "#farming-category-options button", new RegExp(labelRegex, "i")) };
}
"""

FARMING_CLEAR_PLOT_JS = """
(pack) => {
    const stateLabel = (s) => {
        if (s === 0) return "locked";
        if (s === 1) return "empty";
        if (s === 2) return "growing";
        if (s === 3) return "grown";
        if (s === 4) return "dead";
        return `unknown(${s})`;
    };
    const farming = game?.farming;
    if (!farming) return { ok:false, error:"no farming" };
    const categoryName = String(pack?.category ?? "Allotments");
    const plotIndex = Number(pack?.plot ?? 1);
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const categories = Array.from(farming?.categories?.allObjects ?? []);
    const category = categories.find((c) => norm(c?.name) === norm(categoryName))
        || categories.find((c) => norm(c?.name).includes(norm(categoryName)));
    if (!category) return { ok:false, error:`farming category not found: ${categoryName}` };
    const plots = Array.from(farming?.getPlotsForCategory?.(category) ?? []);
    const plot = (plotIndex >= 1 && plotIndex <= plots.length) ? plots[plotIndex - 1] : null;
    if (!plot) return { ok:false, error:"plot not found in selected category" };

    const beforeState = Number(plot?.state ?? -1);
    if (beforeState !== 2) return { ok:false, error:"plot is not growing", state: stateLabel(beforeState) };

    try {
        farming.destroyPlot(plot);
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }

    const afterState = Number(plot?.state ?? -1);
    if (afterState === beforeState) {
        return { ok:false, error:"clear did not apply", state: stateLabel(afterState) };
    }
    if (afterState !== 1) {
        return { ok:false, error:"plot not empty after clear", state: stateLabel(afterState) };
    }
    return {
        ok:true,
        category: category?.name ?? categoryName,
        plot: plotIndex,
        action: "cleared growing crop",
        stateBefore: stateLabel(beforeState),
        stateAfter: stateLabel(afterState),
    };
}
"""

FARMING_COMPOST_ALL_GAME_JS = """
(pack) => {
    const farming = game?.farming;
    if (!farming) return { ok:false, error:"no farming" };
    const categoryName = String(pack?.category ?? "Allotments");
    const compostQuery = String(pack?.compost ?? "compost");
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const categories = Array.from(farming?.categories?.allObjects ?? []);
    const category = categories.find((c) => norm(c?.name) === norm(categoryName))
        || categories.find((c) => norm(c?.name).includes(norm(categoryName)));
    if (!category) return { ok:false, error:`farming category not found: ${categoryName}` };
    const plots = Array.from(farming?.getPlotsForCategory?.(category) ?? []);
    const before = plots.map((p) => ({
        compostLevel: Number(p?.compostLevel ?? 0),
        compostItemId: String(p?.compostItem?.id ?? ""),
    }));
    const gpBefore = Number(game?.gp?.amount ?? game?.gp ?? 0);
    const compostsRaw = game?.items?.composts;
    const composts = Array.isArray(compostsRaw?.allObjects)
        ? compostsRaw.allObjects
        : (compsRaw => {
            try { return Array.from(compsRaw ?? []); } catch (e) { return []; }
        })(compostsRaw);
    const cq = norm(compostQuery);
    const isGloopReq = cq.includes("gloop") || cq.includes("weird");
    const isCompostReq = cq === "compost" || cq.includes("normal compost");
    const compost = composts.find((x) => norm(x?.name) === cq)
        || (isGloopReq
            ? composts.find((x) => norm(x?.name).includes("gloop"))
            : null)
        || (isCompostReq
            ? composts.find((x) => norm(x?.name) === "compost" || norm(x?.name).includes("compost"))
            : null)
        || (!isGloopReq && !isCompostReq
            ? composts.find((x) => norm(x?.name).includes(cq))
            : null);
    if (!compost) return { ok:false, error:`compost item not found: ${compostQuery}` };
    const ownedCompost = Number(game?.bank?.getQty?.(compost) ?? 0);
    if (!Number.isFinite(ownedCompost) || ownedCompost <= 0) {
        return {
            ok:false,
            error:`no ${compost?.name ?? compostQuery} in bank`,
            compost: compost?.name ?? compostQuery,
            spent: 0,
            left: 0,
            owned: 0,
        };
    }
    try {
        farming.compostAllOnClick(category, compost);
        const after = plots.map((p) => ({
            compostLevel: Number(p?.compostLevel ?? 0),
            compostItemId: String(p?.compostItem?.id ?? ""),
        }));
        let compostedPlots = 0;
        for (let i = 0; i < Math.min(before.length, after.length); i++) {
            const changed =
                before[i].compostLevel !== after[i].compostLevel ||
                before[i].compostItemId !== after[i].compostItemId;
            if (changed) compostedPlots += 1;
        }
        const gpAfter = Number(game?.gp?.amount ?? game?.gp ?? 0);
        const left = Number(game?.bank?.getQty?.(compost) ?? 0);
        const spent = Number.isFinite(left) ? Math.max(0, ownedCompost - left) : 0;
        return {
            ok:true,
            category: category?.name ?? categoryName,
            compost: compost?.name ?? compostQuery,
            gpCost: gpBefore > gpAfter ? gpBefore - gpAfter : 0,
            compostedPlots,
            spent,
            left: Number.isFinite(left) ? left : null,
        };
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
}
"""

FARMING_COMPOST_PLOT_JS = """
(pack) => {
    const farming = game?.farming;
    if (!farming) return { ok:false, error:"no farming" };
    const categoryName = String(pack?.category ?? "Allotments");
    const plotIndex = Number(pack?.plot ?? 1);
    const compostQuery = String(pack?.compost ?? "compost");
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();

    const categories = Array.from(farming?.categories?.allObjects ?? []);
    const category = categories.find((c) => norm(c?.name) === norm(categoryName))
        || categories.find((c) => norm(c?.name).includes(norm(categoryName)));
    if (!category) return { ok:false, error:`farming category not found: ${categoryName}` };

    const plots = Array.from(farming?.getPlotsForCategory?.(category) ?? []);
    const plot = (plotIndex >= 1 && plotIndex <= plots.length) ? plots[plotIndex - 1] : null;
    if (!plot) return { ok:false, error:"plot not found in selected category" };
    if (Number(plot?.state) === 0) return { ok:false, error:"plot is locked" };
    if (Number(plot?.state) !== 1) return { ok:false, error:"plot is not empty" };

    const compostsRaw = game?.items?.composts;
    const composts = Array.isArray(compostsRaw?.allObjects)
        ? compostsRaw.allObjects
        : (compsRaw => {
            try { return Array.from(compsRaw ?? []); } catch (e) { return []; }
        })(compostsRaw);
    const cq = norm(compostQuery);
    const isGloopReq = cq.includes("gloop") || cq.includes("weird");
    const isCompostReq = cq === "compost" || cq.includes("normal compost");
    const compost = composts.find((x) => norm(x?.name) === cq)
        || (isGloopReq ? composts.find((x) => norm(x?.name).includes("gloop")) : null)
        || (isCompostReq ? composts.find((x) => norm(x?.name) === "compost" || norm(x?.name).includes("compost")) : null)
        || (!isGloopReq && !isCompostReq ? composts.find((x) => norm(x?.name).includes(cq)) : null);
    if (!compost) return { ok:false, error:`compost item not found: ${compostQuery}` };

    const ownedBefore = Number(game?.bank?.getQty?.(compost) ?? 0);
    if (!Number.isFinite(ownedBefore) || ownedBefore <= 0) {
        return { ok:false, error:`no ${compost?.name ?? compostQuery} in bank`, compost: compost?.name ?? compostQuery };
    }

    const currentLevel = Number(plot?.compostLevel ?? 0);
    if (currentLevel >= 100) {
        return {
            ok:false,
            error:"already applied",
            compost: compost?.name ?? compostQuery,
            compostLevel: currentLevel,
        };
    }

    const beforeLevel = Number(plot?.compostLevel ?? 0);
    const maxCompost = Math.ceil(100 / Number(compost?.compostValue ?? 1));
    try {
        const applied = !!farming.compostPlot(plot, compost, maxCompost);
        const afterLevel = Number(plot?.compostLevel ?? 0);
        const left = Number(game?.bank?.getQty?.(compost) ?? 0);
        const spent = Number.isFinite(left) ? Math.max(0, ownedBefore - left) : 0;
        if (!applied && afterLevel <= beforeLevel) {
            return { ok:false, error:"compost did not apply", compost: compost?.name ?? compostQuery, spent, left: Number.isFinite(left) ? left : null };
        }
        return {
            ok:true,
            category: category?.name ?? categoryName,
            plot: plotIndex,
            compost: compost?.name ?? compostQuery,
            compostLevelBefore: beforeLevel,
            compostLevelAfter: afterLevel,
            spent,
            left: Number.isFinite(left) ? left : null,
        };
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
}
"""

FARMING_HARVEST_ALL_GAME_JS = """
(pack) => {
    const farming = game?.farming;
    if (!farming) return { ok:false, error:"no farming" };
    const categoryName = String(pack?.category ?? "Allotments");
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const categories = Array.from(farming?.categories?.allObjects ?? []);
    const category = categories.find((c) => norm(c?.name) === norm(categoryName))
        || categories.find((c) => norm(c?.name).includes(norm(categoryName)));
    if (!category) return { ok:false, error:`farming category not found: ${categoryName}` };
    const plots = Array.from(farming?.getPlotsForCategory?.(category) ?? []);
    const harvestableBefore = plots.filter((p) => Number(p?.state) === 3 || Number(p?.state) === 4).length;
    if (harvestableBefore <= 0) {
        return { ok:false, error:"no harvestable or dead plots in selected category", category: category?.name ?? categoryName };
    }
    const gpBefore = Number(game?.gp?.amount ?? game?.gp ?? 0);
    try {
        farming.harvestAllOnClick(category);
        const harvestableAfter = plots.filter((p) => Number(p?.state) === 3 || Number(p?.state) === 4).length;
        const gpAfter = Number(game?.gp?.amount ?? game?.gp ?? 0);
        const changed = harvestableAfter < harvestableBefore || gpAfter < gpBefore;
        if (!changed) {
            return {
                ok:false,
                error:"harvest-all did not apply (no plots changed and no GP spent)",
                category: category?.name ?? categoryName,
            };
        }
        return {
            ok:true,
            category: category?.name ?? categoryName,
            gpCost: gpBefore > gpAfter ? gpBefore - gpAfter : 0,
            harvestedOrCleared: Math.max(0, harvestableBefore - harvestableAfter),
        };
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
}
"""

FARMING_HARVEST_PLOT_JS = """
(pack) => {
    const stateLabel = (s) => {
        if (s === 0) return "locked";
        if (s === 1) return "empty";
        if (s === 2) return "growing";
        if (s === 3) return "grown";
        if (s === 4) return "dead";
        return `unknown(${s})`;
    };
    const farming = game?.farming;
    if (!farming) return { ok:false, error:"no farming" };
    const categoryName = String(pack?.category ?? "Allotments");
    const plotIndex = Number(pack?.plot ?? 1);
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const categories = Array.from(farming?.categories?.allObjects ?? []);
    const category = categories.find((c) => norm(c?.name) === norm(categoryName))
        || categories.find((c) => norm(c?.name).includes(norm(categoryName)));
    if (!category) return { ok:false, error:`farming category not found: ${categoryName}` };
    const plots = Array.from(farming?.getPlotsForCategory?.(category) ?? []);
    const plot = (plotIndex >= 1 && plotIndex <= plots.length) ? plots[plotIndex - 1] : null;
    if (!plot) return { ok:false, error:"plot not found in selected category" };
    const beforeState = Number(plot?.state ?? -1);
    if (beforeState !== 3 && beforeState !== 4) {
        return { ok:false, error:"plot is not ready/dead", state: stateLabel(beforeState) };
    }
    try {
        farming.harvestPlotOnClick(plot);
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
    const afterState = Number(plot?.state ?? -1);
    const changed = afterState !== beforeState;
    if (!changed) return { ok:false, error:"harvest did not apply", state: stateLabel(afterState) };
    
    const action = beforeState === 3 ? "harvested crop" : (beforeState === 4 ? "cleared dead crop" : "plot updated");
    return {
        ok:true,
        category: category?.name ?? categoryName,
        plot: plotIndex,
        action,
        stateBefore: stateLabel(beforeState),
        stateAfter: stateLabel(afterState),
    };
}
"""

FARMING_PARSE_ARGS_JS = """
(argv) => {
    const parts = Array.isArray(argv) ? argv.map(String) : [];
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const catMap = { allotment:"Allotments", allotments:"Allotments", herb:"Herbs", herbs:"Herbs", tree:"Trees", trees:"Trees" };
    let category = "Allotments";
    let plot = 1;
    let seed = null;
    for (const tok of parts) {
        const t = String(tok ?? "");
        if (/^\d+$/.test(t)) plot = Number(t);
        else if (catMap[norm(t)]) category = catMap[norm(t)];
        else if (!seed) seed = t;
    }
    return { category, plot, seed };
}
"""

FARMING_PLANT_ALL_GAME_JS = """
(pack) => {
    const farming = game?.farming;
    if (!farming) return { ok:false, error:"no farming" };
    const categoryName = String(pack?.category ?? "Allotments");
    const seedQuery = String(pack?.seed ?? "");
    if (!seedQuery) return { ok:false, error:"seed is required" };
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const categories = Array.from(farming?.categories?.allObjects ?? []);
    const category = categories.find((c) => norm(c?.name) === norm(categoryName))
        || categories.find((c) => norm(c?.name).includes(norm(categoryName)));
    if (!category) return { ok:false, error:`farming category not found: ${categoryName}` };
    const plots = Array.from(farming?.getPlotsForCategory?.(category) ?? []);
    const before = plots.map((p) => Number(p?.state ?? -1));
    const gpBefore = Number(game?.gp?.amount ?? game?.gp ?? 0);
    const recipes = Array.from(farming?.getRecipesForCategory?.(category) ?? []);
    const exact = recipes.filter((r) => norm(r?.seedCost?.item?.name) === norm(seedQuery) || norm(r?.name) === norm(seedQuery));
    const picks = exact.length ? exact : recipes.filter((r) => {
        const a = norm(r?.seedCost?.item?.name);
        const b = norm(r?.name);
        const q = norm(seedQuery);
        return q && (a.includes(q) || b.includes(q));
    });
    if (picks.length !== 1) return { ok:false, error:"unknown or ambiguous seed" };
    const recipe = picks[0];
    try {
        farming.plantAllRecipe(recipe);
        const after = plots.map((p) => Number(p?.state ?? -1));
        let plantedPlots = 0;
        for (let i = 0; i < Math.min(before.length, after.length); i++) {
            const wasEmpty = before[i] === 1;
            const nowPlanted = after[i] === 2 || after[i] === 3;
            if (wasEmpty && nowPlanted) plantedPlots += 1;
        }
        const gpAfter = Number(game?.gp?.amount ?? game?.gp ?? 0);
        const gpCost = gpBefore > gpAfter ? gpBefore - gpAfter : 0;
        if (plantedPlots <= 0) {
            return {
                ok:false,
                error:"plant-all did not apply (no plots were planted)",
                category: category?.name ?? categoryName,
                recipe: recipe?.name ?? seedQuery,
                gpCost,
                plantedPlots: 0,
            };
        }
        return {
            ok:true,
            category: category?.name ?? categoryName,
            recipe: recipe?.name ?? seedQuery,
            gpCost,
            plantedPlots,
        };
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
}
"""

FARMING_PLANT_ALL_JS = """
(pack) => {
    const category = String(pack?.category ?? "Allotments");
    const seed = String(pack?.seed ?? "");
    if (!seed) return { ok:false, error:"plant-all requires seed name" };
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const chooseCategory = () => {
        const buttons = Array.from(document.querySelectorAll("farming-category-button"));
        for (const b of buttons) {
            const txt = norm((b.innerText || b.textContent || "").split("\n").find((x) => x.trim()) || "");
            if (txt === norm(category)) { b.click(); return true; }
        }
        return false;
    };
    const clickByText = (root, sel, rx) => {
        const nodes = Array.from((root || document).querySelectorAll(sel));
        for (const el of nodes) {
            const txt = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && rx.test(txt)) { el.click(); return true; }
        }
        return false;
    };
    chooseCategory();
    if (!clickByText(document, "#farming-category-options button", /plant all/i)) return { ok:false, error:"Plant All button not found" };
    const modal = document.querySelector("#modal-farming-seed.show");
    if (!modal) return { ok:false, error:"Seed modal did not open" };
    const escaped = seed.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (!clickByText(modal, ".btn-group-vertical button", new RegExp(escaped, "i"))) return { ok:false, error:"Seed not found in modal" };
    return { ok: clickByText(modal, "button", /plant selected|plant/i) };
}
"""

FARMING_PLANT_ALL_SELECTED_GAME_JS = """
(pack) => {
    const farming = game?.farming;
    if (!farming) return { ok:false, error:"no farming" };
    const categoryName = String(pack?.category ?? "Allotments");
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const categories = Array.from(farming?.categories?.allObjects ?? []);
    const category = categories.find((c) => norm(c?.name) === norm(categoryName))
        || categories.find((c) => norm(c?.name).includes(norm(categoryName)));
    if (!category) return { ok:false, error:`farming category not found: ${categoryName}` };
    const plots = Array.from(farming?.getPlotsForCategory?.(category) ?? []);
    const before = plots.map((p) => Number(p?.state ?? -1));
    const gpBefore = Number(game?.gp?.amount ?? game?.gp ?? 0);
    try {
        farming.plantAllSelectedOnClick(category);
        const after = plots.map((p) => Number(p?.state ?? -1));
        let plantedPlots = 0;
        for (let i = 0; i < Math.min(before.length, after.length); i++) {
            const wasEmpty = before[i] === 1;
            const nowPlanted = after[i] === 2 || after[i] === 3;
            if (wasEmpty && nowPlanted) plantedPlots += 1;
        }
        const gpAfter = Number(game?.gp?.amount ?? game?.gp ?? 0);
        const gpCost = gpBefore > gpAfter ? gpBefore - gpAfter : 0;
        if (plantedPlots <= 0) {
            return {
                ok:false,
                error:"plant-all-selected did not apply (no plots were planted)",
                category: category?.name ?? categoryName,
                gpCost,
                plantedPlots: 0,
            };
        }
        return {
            ok:true,
            category: category?.name ?? categoryName,
            gpCost,
            plantedPlots,
        };
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
}
"""

FARMING_PLOT_ACTION_JS = """
(pack) => {
    const category = String(pack?.category ?? "Allotments");
    const plot = Number(pack?.plot ?? 1);
    const labelRegex = String(pack?.labelRegex ?? "");
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const clickByText = (root, sel, rx) => {
        const nodes = Array.from((root || document).querySelectorAll(sel));
        for (const el of nodes) {
            const txt = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && rx.test(txt)) { el.click(); return true; }
        }
        return false;
    };
    const chooseCategory = () => {
        const buttons = Array.from(document.querySelectorAll("farming-category-button"));
        for (const b of buttons) {
            const txt = norm((b.innerText || b.textContent || "").split("\n").find((x) => x.trim()) || "");
            if (txt === norm(category)) { b.click(); return true; }
        }
        return false;
    };
    chooseCategory();
    const visiblePlots = Array.from(document.querySelectorAll("farming-plot:not(.d-none)"))
        .filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    const p = (plot >= 1 && plot <= visiblePlots.length) ? visiblePlots[plot - 1] : null;
    if (!p) return { ok:false, error:"Plot not found in selected category" };
    if (!labelRegex) return { ok:false, error:"missing labelRegex" };
    return { ok: clickByText(p, "button", new RegExp(labelRegex, "i")) };
}
"""

FARMING_SELECT_SEED_JS = """
(pack) => {
    const categoryName = String(pack?.category ?? "Allotments");
    const plotIndex = Number(pack?.plot ?? 1);
    const seedQuery = String(pack?.seed ?? "");
    const doPlant = !!pack?.doPlant;
    if (!seedQuery) return { ok:false, error:"seed is required" };
    const farming = game?.farming;
    if (!farming) return { ok:false, error:"no farming" };
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();

    const categories = Array.from(farming?.categories?.allObjects ?? []);
    const category = categories.find((c) => norm(c?.name) === norm(categoryName))
        || categories.find((c) => norm(c?.name).includes(norm(categoryName)));
    if (!category) return { ok:false, error:`farming category not found: ${categoryName}` };
    const plots = Array.from(farming?.getPlotsForCategory?.(category) ?? []);
    const plot = (plotIndex >= 1 && plotIndex <= plots.length) ? plots[plotIndex - 1] : null;
    if (!plot) return { ok:false, error:"plot not found in selected category" };
    if (Number(plot?.state) === 0) return { ok:false, error:"plot is locked" };

    const recipes = Array.from(farming?.getRecipesForCategory?.(category) ?? []);
    const exact = recipes.filter((r) => norm(r?.seedCost?.item?.name) === norm(seedQuery) || norm(r?.name) === norm(seedQuery));
    const picks = exact.length ? exact : recipes.filter((r) => {
        const a = norm(r?.seedCost?.item?.name);
        const b = norm(r?.name);
        const q = norm(seedQuery);
        return q && (a.includes(q) || b.includes(q));
    });
    if (picks.length !== 1) {
        return { ok:false, error:`unknown or ambiguous seed for category ${category?.name ?? categoryName}` };
    }
    const recipe = picks[0];

    const needed = Number(farming?.getRecipeSeedCost?.(recipe) ?? 0);
    const owned = Number(game?.bank?.getQty?.(recipe?.seedCost?.item) ?? 0);
    if (!Number.isFinite(needed) || needed <= 0) return { ok:false, error:"could not resolve seed cost" };
    if (owned < needed) {
        return { ok:false, error:`not enough seeds: need ${needed}, have ${owned}` };
    }

    if (!doPlant) {
        try { farming.setPlantAllSelected(plot, recipe); } catch (e) { return { ok:false, error:String(e?.message ?? e) }; }
        return { ok:true, selected:true, recipe: recipe?.name ?? seedQuery, plot: plotIndex, category: category?.name ?? categoryName };
    }
    if (Number(plot?.state) !== 1) return { ok:false, error:"plot is not empty" };

    try {
        farming.plantRecipe(recipe, plot);
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
    const stateAfter = Number(plot?.state ?? -1);
    const planted = stateAfter === 2 || stateAfter === 3;
    if (!planted) return { ok:false, error:"plant did not apply" };
    return { ok:true, planted:true, recipe: recipe?.name ?? seedQuery, plot: plotIndex, category: category?.name ?? categoryName };
}
"""

FARMING_UNLOCK_JS = """
(pack) => {
    const farming = game?.farming;
    if (!farming) return { ok:false, error:"no farming" };
    const categoryName = String(pack?.category ?? "Allotments");
    const plotIndex = Number(pack?.plot ?? 1);
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const categories = Array.from(farming?.categories?.allObjects ?? []);
    const category = categories.find((c) => norm(c?.name) === norm(categoryName))
        || categories.find((c) => norm(c?.name).includes(norm(categoryName)));
    if (!category) return { ok:false, error:`farming category not found: ${categoryName}` };
    const plots = Array.from(farming?.getPlotsForCategory?.(category) ?? []);
    const plot = (plotIndex >= 1 && plotIndex <= plots.length) ? plots[plotIndex - 1] : null;
    if (!plot) return { ok:false, error:"plot not found in selected category" };
    const state = Number(plot?.state ?? -1);
    if (state !== 0) return { ok:false, error:"plot is not locked" };
    const unlockable = !!farming?.canUnlockPlot?.(plot);
    if (!unlockable) return { ok:false, error:"plot is locked but not unlockable yet" };
    try {
        farming.unlockPlotOnClick(plot);
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
    const stateAfter = Number(plot?.state ?? -1);
    if (stateAfter === 0) return { ok:false, error:"unlock did not apply" };
    return { ok:true, via:"farming.unlockPlotOnClick", category: category?.name ?? categoryName, plot: plotIndex };
}
"""
