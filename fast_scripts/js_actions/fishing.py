from __future__ import annotations

FISHING_START_JS = """
(query) => {
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const f = game?.fishing;
    if (!f) return { ok:false, error:"no fishing" };
    const isFishingAreaUnlocked = (skill, area) => {
        try {
            if (!area) return false;
            if (area.isSecret && !skill.secretAreaUnlocked) return false;
            const g = skill.game ?? game;
            if (area.requiredItem !== undefined && !g?.combat?.player?.equipment?.checkForItem?.(area.requiredItem)) return false;
            if (area.poiRequirement !== undefined && !area.poiRequirement.isMet?.()) return false;
            if (area.realm !== undefined && skill.currentRealm !== undefined && area.realm !== skill.currentRealm) return false;
            return true;
        } catch (e) {
            return false;
        }
    };
    const areas = Array.from(f?.areas?.allObjects ?? []).filter((area) => isFishingAreaUnlocked(f, area));
    const all = areas.flatMap(area =>
        Array.from(area?.fish ?? []).map(fish => ({
            fish,
            area,
            fishName: fish?.name ?? "Unknown Fish",
            areaName: area?.name ?? "Unknown Area",
            unlocked: !!(f?.isMasteryActionUnlocked?.(fish)),
        }))
    );
    const exact = all.filter((r) => norm(r.fishName) === query);
    const picks = exact.length ? exact : all.filter((r) => query && norm(r.fishName).includes(query));
    if (picks.length !== 1) return { ok:false, error:"Unknown or ambiguous fish" };
    const t = picks[0];
    if (!t.unlocked) return { ok:false, error:`Fish locked: ${t.fishName}` };
    try {
        f.onAreaFishSelection(t.area, t.fish);
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }

    const activeArea = f?.activeFishingArea ?? null;
    const activeFish = activeArea ? (f?.selectedAreaFish?.get?.(activeArea) ?? null) : null;
    if (f?.isActive && activeArea === t.area && activeFish === t.fish) {
        return { ok:true, alreadyActive:true, fish:t.fishName, area:t.areaName };
    }

    try {
        f.onAreaStartButtonClick(t.area);
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
    if (!f?.isActive) return { ok:false, error:"start did not apply" };
    return { ok:true, started:true, fish:t.fishName, area:t.areaName };
}
"""

FISHING_STOP_JS = """
() => {
    const f = game?.fishing;
    if (!f) return { ok:false, error:"no fishing" };
    if (!f?.isActive) return { ok:false, error:"not fishing now" };
    const activeArea = f?.activeFishingArea ?? null;
    if (!activeArea) return { ok:false, error:"could not resolve active fishing area" };
    try {
        f.onAreaStartButtonClick(activeArea);
    } catch (e) {
        return { ok:false, error:String(e?.message ?? e) };
    }
    if (f?.isActive) return { ok:false, error:"stop did not apply" };
    return { ok:true, stopped:true, area:activeArea?.name ?? "Unknown Area" };
}
"""
