from __future__ import annotations

WOODCUTTING_START_JS = """
(treeNames) => {
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const wc = game?.woodcutting;
    if (!wc) return { ok:false, error:"no woodcutting" };
    const actions = wc?.actions?.allObjects ?? [];
    const selectTree = (tree) => {
        if (typeof wc?.selectTree === "function") {
            wc.selectTree(tree);
            return true;
        }
        if (typeof wc?.onTreeSelection === "function") {
            wc.onTreeSelection(tree);
            return true;
        }
        return false;
    };

    // Always stop first so new requested trees are applied deterministically.
    try {
        if (typeof wc?.stop === "function") wc.stop();
        else if (typeof wc?.stopAction === "function") wc.stopAction();
        else if (typeof wc?.stopCutting === "function") wc.stopCutting();
        else {
            const active = wc?.activeTrees ? Array.from(wc.activeTrees) : [];
            for (const t of active) {
                if (typeof wc?.onTreeSelection === "function") wc.onTreeSelection(t);
                else if (typeof wc?.selectTree === "function") wc.selectTree(t);
            }
        }
    } catch (e) {
        return { ok:false, error:`Could not stop woodcutting first: ${String(e?.message ?? e)}` };
    }

    for (const name of treeNames) {
        const t = actions.find((x) => norm(x?.name) === norm(name));
        if (!t) return { ok:false, error:`Tree not found: ${name}` };
        try {
            if (!selectTree(t)) return { ok:false, error:`No pure JS tree selection API for: ${name}` };
        } catch (e) {
            return { ok:false, error:`Could not select tree ${name}: ${String(e?.message ?? e)}` };
        }
    }
    return {
        ok:true,
        trees: treeNames,
        active: wc?.activeTrees ? Array.from(wc.activeTrees).map((t) => t?.name ?? "Unknown") : [],
    };
}
"""

WOODCUTTING_STATE_JS = """
() => {
    const wc = game?.woodcutting;
    return {
        limit: Number(wc?.treeCutLimit ?? 1),
        trees: (wc?.actions?.allObjects ?? []).map(t => ({
            id: t?.id ?? "",
            name: t?.name ?? "Unknown",
            unlocked: !!wc?.isTreeUnlocked?.(t),
            level: Number(t?.level ?? 0),
        })),
    };
}
"""

WOODCUTTING_STOP_JS = """
() => {
    const wc = game?.woodcutting;
    if (!wc) return { ok:false, error:"no woodcutting" };
    const methods = ["stop", "stopAction", "stopCutting"];
    for (const m of methods) {
        if (typeof wc?.[m] === "function") {
            try { wc[m](); return { ok:true, via:m }; } catch (e) {}
        }
    }
    try {
        const active = wc?.activeTrees ? Array.from(wc.activeTrees) : [];
        if (!active.length) return { ok:true, message:"already stopped" };
        for (const t of active) {
            if (typeof wc?.onTreeSelection === "function") wc.onTreeSelection(t);
        }
        return { ok:true, via:"onTreeSelection" };
    } catch (e) {}
    return { ok:true, message:"no direct stop route" };
}
"""
