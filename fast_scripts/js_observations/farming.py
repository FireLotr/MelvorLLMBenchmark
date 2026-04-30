from __future__ import annotations

FARMING_PLOTS_JS = '''() => {
    const f = game?.farming;
    if (!f) return { ok:false, error:"no farming" };
    const categories = f?.categories?.allObjects ?? [];
    const getBankQty = (ids, fallbackNamePart) => {
        try {
            let item = null;
            for (const id of ids) {
                item = game?.items?.getObjectByID?.(id);
                if (item) break;
            }
            if (!item && fallbackNamePart) {
                const all = game?.items?.allObjects ?? [];
                const needle = String(fallbackNamePart).toLowerCase();
                item = all.find((it) => String(it?.name ?? "").toLowerCase().includes(needle)) ?? null;
            }
            if (!item) return 0;
            return Number(game?.bank?.getQty?.(item) ?? 0);
        } catch (e) {
            return 0;
        }
    };
    const out = {
        ok: true,
        level: Number(f?.level ?? 0),
        resources: {
            compost: getBankQty(["melvorD:Compost"], "compost"),
            weirdGloop: getBankQty(["melvorD:Weird_Gloop"], "weird gloop"),
        },
        categories: [],
    };
    const readUnlockRequirements = (plot) => {
        const reqParts = [];
        const levelReq = Number(plot?.level ?? 0);
        if (Number.isFinite(levelReq) && levelReq > 1) reqParts.push(`Farming Level ${levelReq}`);
        try {
            const costs = typeof f.getPlotUnlockCosts === "function" ? f.getPlotUnlockCosts(plot) : null;
            const currencies = costs?._currencies;
            if (currencies instanceof Map) {
                for (const [currency, qty] of currencies.entries()) {
                    const n = Number(qty);
                    if (!Number.isFinite(n) || n <= 0) continue;
                    reqParts.push(`${n.toLocaleString()} ${currency?.name ?? "Currency"}`);
                }
            }
        } catch (e) {}
        return reqParts.join(", ") || "?";
    };
    const formatGrowing = (ms) => {
        const totalSec = Math.max(0, Math.floor(Number(ms || 0) / 1000));
        const h = Math.floor(totalSec / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const s = totalSec % 60;
        if (h > 0) return `${h}h ${m}m`;
        if (m > 0) return `${m}m ${s}s`;
        return `${s}s`;
    };

    for (const cat of categories) {
        const plotsSrc = typeof f.getPlotsForCategory === "function" ? (f.getPlotsForCategory(cat) ?? []) : [];
        const plots = [];
        plotsSrc.forEach((plot, i) => {
            const idx = i + 1;
            const stateNum = Number(plot?.state ?? 0);
            if (stateNum === 0) {
                let canUnlock = false;
                try { canUnlock = typeof f.canUnlockPlot === "function" ? !!f.canUnlockPlot(plot) : false; } catch (e) {}
                plots.push({
                    index: idx,
                    locked: true,
                    state: "locked",
                    requirements: readUnlockRequirements(plot),
                    can_unlock: canUnlock,
                });
                return;
            }
            const selected = plot?.selectedRecipe?.seedCost?.item?.name ?? plot?.selectedRecipe?.name ?? "?";
            const planted = plot?.plantedRecipe?.name ?? "—";
            const compost = plot?.compostItem?.name ?? "none";
            const compostLevel = Number(plot?.compostLevel ?? 0);
            const recipe = plot?.plantedRecipe ?? plot?.selectedRecipe ?? null;
            const xp = Number(recipe?.baseExperience ?? 0);
            const intervalMs = Number(recipe?.baseInterval ?? 0);
            let state = "empty";
            if (plot?.plantedRecipe) {
                const growthLeft = Number(
                    (typeof f?.getPlotGrowthTime === "function" ? f.getPlotGrowthTime(plot) : 0) ?? 0
                );
                if (Number.isFinite(growthLeft) && growthLeft > 0) state = `growing (${formatGrowing(growthLeft)})`;
                else state = "ready";
            } else if (stateNum >= 3) {
                state = "dead";
            }
            plots.push({
                index: idx,
                locked: false,
                state,
                selected_seed: selected,
                planted,
                compost,
                compostLevel,
                xp,
                intervalMs,
            });
        });

        out.categories.push({ name: cat?.name ?? "Unknown", plots });
    }
    return out;
}'''
