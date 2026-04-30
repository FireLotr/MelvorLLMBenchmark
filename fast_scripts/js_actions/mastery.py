from __future__ import annotations

MASTERY_SPEND_JS = """
(pack) => {
    const query = String(pack?.query ?? "").toLowerCase().trim();
    const levels = Number(pack?.levels ?? 0);
    if (!query || !Number.isFinite(levels) || levels <= 0) return { ok:false, error:"invalid spend args" };
    const skill = game?.[String(pack?.skill ?? "").toLowerCase()];
    if (!skill) return { ok:false, error:"unknown skill object" };
    const action = (skill?.actions?.allObjects ?? []).find((a) => {
        const n = String(a?.name ?? "").toLowerCase().replace(/\s+/g, " ").trim();
        return n === query || n.includes(query);
    });
    if (!action) return { ok:false, error:"Mastery action not found" };

    const getLevel = () => Number(skill?.getMasteryLevel?.(action) ?? 1);
    const getXP = () => Number(skill?.getMasteryXP?.(action) ?? 0);
    const getPool = () => Number(skill?.getMasteryPoolXP?.(action?.realm) ?? 0);
    let levelsSpent = 0;
    let xpSpent = 0;
    const poolBefore = getPool();
    for (let i = 0; i < levels; i++) {
        const before = getLevel();
        const currentXP = getXP();
        const nextLevel = Math.min(99, before + 1);
        const nextXP = Number(exp?.levelToXP?.(nextLevel) ?? 0) + 1;
        const xpToAdd = nextXP - currentXP;
        if (!Number.isFinite(xpToAdd) || xpToAdd <= 0) {
            return levelsSpent > 0
                ? { ok:true, levelsSpent, xpSpent, poolBefore, poolAfter:getPool(), note:"stopped: could not resolve XP required for next level" }
                : { ok:false, error:"could not resolve XP required for next mastery level" };
        }
        const poolXP = getPool();
        if (!Number.isFinite(poolXP) || poolXP < xpToAdd) {
            const needNextLevel = Math.ceil(xpToAdd);
            const havePool = Math.floor(Number.isFinite(poolXP) ? poolXP : 0);
            return levelsSpent > 0
                ? {
                    ok:true,
                    levelsSpent,
                    xpSpent,
                    poolBefore,
                    poolAfter:getPool(),
                    note:`stopped: insufficient mastery pool XP for next level (need ${needNextLevel}, have ${havePool})`,
                }
                : {
                    ok:false,
                    error:`insufficient mastery pool XP for next level (need ${needNextLevel}, have ${havePool})`,
                };
        }
        try {
            skill.exchangePoolXPForActionXP(action, xpToAdd);
        } catch (e) {
            return levelsSpent > 0
                ? { ok:true, levelsSpent, xpSpent, poolBefore, poolAfter:getPool(), note:String(e?.message ?? e) }
                : { ok:false, error:String(e?.message ?? e) };
        }
        const after = getLevel();
        if (!Number.isFinite(after) || after <= before) {
            return levelsSpent > 0
                ? { ok:true, levelsSpent, xpSpent, poolBefore, poolAfter:getPool(), note:"stopped: pool too low or action capped" }
                : { ok:false, error:"no mastery pool spend performed (pool may be too low or action capped)" };
        }
        xpSpent += xpToAdd;
        levelsSpent += 1;
    }
    return { ok:true, levelsSpent, xpSpent, poolBefore, poolAfter:getPool() };
}
"""
