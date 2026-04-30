from __future__ import annotations

MASTERY_STATE_JS = """(skillKey) => {
    const s = game?.[String(skillKey || "").toLowerCase()];
    if (!s) return { ok: false, error: `unknown skill: ${skillKey}` };
    const realm = s?.currentRealm ?? null;
    const realmName = realm?.name ?? "Unknown Realm";
    const poolXP = Number(s?.getMasteryPoolXP?.(realm) ?? 0);
    const poolCap = Number(s?.getMasteryPoolCap?.(realm) ?? 0);
    const poolProgress = Number(s?.getMasteryPoolProgress?.(realm) ?? 0);
    const totalLevel = Number(s?.getTotalCurrentMasteryLevelInRealm?.(realm) ?? 0);
    const maxTotalLevel = Number(s?.getTrueMaxTotalMasteryLevelInRealm?.(realm) ?? 0);
    const poolBonuses = Array.from((s?.masteryPoolBonuses ?? new Map()).entries())
        .filter(([r]) => !realm || r === realm)
        .flatMap(([r, arr]) =>
            (arr ?? []).map((b) => {
                const percent = Number(b?.percent ?? 0);
                const active = poolProgress >= (percent / 100);
                let effect = "Unknown";
                try {
                    const m = b?.modifiers?.[0];
                    const p = m?.print?.();
                    if (p && typeof p === "object" && p.text) effect = String(p.text);
                } catch (e) {}
                return { percent, active, effect };
            })
        )
        .sort((a, b) => a.percent - b.percent);
    const unlocks = (s?.masteryLevelUnlocks ?? [])
        .map((u) => ({
            level: Number(u?.level ?? 0),
            description: String(u?._description ?? u?.description ?? "Unknown"),
        }))
        .sort((a, b) => a.level - b.level);
    const actions = (s?.actions?.allObjects ?? []).map((a) => {
        const progress = s?.getMasteryProgress?.(a);
        let unlocked = false;
        try { unlocked = !!s?.isMasteryActionUnlocked?.(a); } catch (e) {}
        const rawPercent = Number(progress?.percent ?? 0);
        const toNextPercent = rawPercent <= 1 ? rawPercent * 100 : rawPercent;
        return {
            name: a?.name ?? "Unknown",
            levelReq: Number(a?.level ?? 0),
            masteryLevel: Number(s?.getMasteryLevel?.(a) ?? 0),
            toNextPercent,
            unlocked,
        };
    });
    return {
        ok: true,
        skillName: s?.name ?? String(skillKey || ""),
        realmName,
        poolXP,
        poolCap,
        poolProgress,
        totalLevel,
        maxTotalLevel,
        poolBonuses,
        unlocks,
        actions,
    };
}"""

MASTERY_UNLOCKS_JS = """(pack) => {
    const skillKey = pack?.skillKey;
    const query = pack?.query;
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\\s+/g, " ").trim();
    const s = game?.[String(skillKey || "").toLowerCase()];
    if (!s) return { ok:false, error:"unknown skill" };
    const unlocks = (s?.masteryLevelUnlocks ?? []).map((u) => ({
        level: Number(u?.level ?? 0),
        description: String(u?._description ?? u?.description ?? ""),
    }));
    const q = norm(query || "");
    if (!q) return { ok:true, unlocks };
    return { ok:true, unlocks: unlocks.filter((u) => norm(u.description).includes(q)) };
}"""
