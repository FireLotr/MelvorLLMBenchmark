from __future__ import annotations

FIREMAKING_LIST_JS = """() => {
    const f = game?.firemaking;
    if (!f) return { ok: false, error: "no firemaking" };

    const readBonfireInfo = () => {
        let lit = null;
        let bonusLog = null;
        let bonusPct = null;
        try {
            const bt = f?.bonfireTimer;
            if (bt && typeof bt === "object" && typeof bt.active === "boolean") {
                lit = !!bt.active;
            }
        } catch (e) {}
        if (lit === null) {
            try {
                if (typeof f?.isBonfireLit === "function") lit = !!f.isBonfireLit();
                else if (typeof f?.isBonfireActive === "function") lit = !!f.isBonfireActive();
            } catch (e) {}
        }
        try {
            const r = f?.litBonfireRecipe;
            if (r && typeof r === "object") {
                bonusLog = r?.log?.name ?? r?.name ?? null;
                const b = Number(r?.bonfireXPBonus);
                bonusPct = Number.isFinite(b) ? b : null;
            }
        } catch (e) {}
        return { lit, bonusLog, bonusPct };
    };

    let active = null;
    let isBurning = false;
    try { active = f?.activeRecipe?.name ?? null; } catch (e) { active = null; }
    try { isBurning = !!f?.isActive; } catch (e) { isBurning = false; }

    const bonfire = readBonfireInfo();
    const rows = (f?.actions?.allObjects ?? []).map((a) => {
        let unlocked = false;
        try { unlocked = !!f?.isMasteryActionUnlocked?.(a); } catch (e) {}
        let interval = Number(a?.baseInterval ?? 0);
        try {
            if (typeof f?.modifyInterval === "function") {
                const realInterval = Number(f.modifyInterval(a?.baseInterval ?? 0, a));
                if (Number.isFinite(realInterval) && realInterval > 0) interval = realInterval;
            }
        } catch (e) {}
        return {
            name: a?.name ?? "Unknown",
            level: Number(a?.level ?? 0),
            xp: Number(a?.baseExperience ?? 0),
            interval,
            unlocked,
        };
    });

    return {
        ok: true,
        level: Number(f?.level ?? 0),
        active,
        isBurning,
        bonfireLit: bonfire.lit,
        bonfireBonusLog: bonfire.bonusLog,
        bonfireBonusPercent: bonfire.bonusPct,
        rows,
    };
}"""
