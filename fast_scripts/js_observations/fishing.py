from __future__ import annotations

FISHING_LIST_JS = """() => {
    const f = game?.fishing;
    if (!f) return { ok: false, error: "no fishing" };
    const level = Number(f?.level ?? 0);
    const currentRod = (() => {
        const displays = Array.from(document.querySelectorAll("upgrade-chain-display"));
        for (const d of displays) {
            const text = (d.textContent || "").replace(/\\s+/g, " ").trim();
            const m = text.match(/^Current Rod\\s+(.+)$/i);
            if (m) return m[1].trim();
        }
        return null;
    })();

    /** Matches Fishing.renderAreaUnlock — areas hidden in UI are not listable/startable here. */
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

    const selected = f?.selectedAreaFish
        ? Array.from(f.selectedAreaFish.entries())
              .filter(([area]) => isFishingAreaUnlocked(f, area))
              .map(([area, fish]) => ({
                  area: area?.name ?? "Unknown Area",
                  fish: fish?.name ?? "Unknown Fish",
              }))
        : [];

    const clampValue = (val, min, max) => Math.min(Math.max(val, min), max);

    /** Same logic as Fishing.getAreaChances(area), but for an explicit fish (modifier query / mastery). */
    const chancesForFish = (fishing, area, fish) => {
        let fishP = Number(area.fishChance ?? 0);
        let specialP = Number(area.specialChance ?? 0);
        let junkP = Number(area.junkChance ?? 0);
        const g = fishing.game ?? game;
        const fishToSpecialShift = Number(g.modifiers.fishingSpecialChance ?? 0);
        const query = fishing.getActionModifierQuery(fish);
        const noJunk = g.modifiers.getValue("melvorD:cannotFishJunk", query);
        const bonusSpecialChance = Number(g.modifiers.getValue("melvorD:bonusFishingSpecialChance", query) ?? 0);

        const addBonusSpecialChance = (amount) => {
            let a = amount;
            const junkToSpecialShift = clampValue(a, -specialP, junkP);
            junkP -= junkToSpecialShift;
            specialP += junkToSpecialShift;
            a -= junkToSpecialShift;
            const fishToSpec = clampValue(a, -specialP, fishP);
            fishP -= fishToSpec;
            specialP += fishToSpec;
        };
        addBonusSpecialChance(Number.isFinite(bonusSpecialChance) ? bonusSpecialChance : 0);

        const sfs = clampValue(fishToSpecialShift, -specialP, fishP);
        fishP -= sfs;
        specialP += sfs;

        if (noJunk) {
            const jtf = clampValue(junkP, -fishP, junkP);
            junkP -= jtf;
            fishP += jtf;
        }

        const r2 = (n) => Math.round(Number(n) * 100) / 100;
        return {
            fish: r2(fishP),
            junk: r2(junkP),
            special: r2(specialP),
            areaBase: {
                fish: r2(Number(area.fishChance ?? 0)),
                junk: r2(Number(area.junkChance ?? 0)),
                special: r2(Number(area.specialChance ?? 0)),
            },
        };
    };

    const enrichFishingFishFromGame = (areaRef, fishRef) => {
        let a = areaRef;
        let fish = fishRef;
        if (f.activeFishingArea && f.selectedAreaFish) {
            try {
                const hit = f.selectedAreaFish.get(f.activeFishingArea);
                if (hit?.name) fish = fish || hit.name;
            } catch (e) {}
        }
        if (!a && f.activeFishingArea) a = f.activeFishingArea.name ?? a;
        fish = fish || f.activeRecipe?.name || f.selectedFish?.name || null;
        if (!fish && f.selectedAreaFish && a) {
            for (const [ar, fi] of f.selectedAreaFish.entries()) {
                if ((ar?.name ?? "") === a) {
                    fish = fi?.name ?? null;
                    break;
                }
            }
        }
        if (!fish && selected.length === 1) {
            fish = selected[0].fish;
            a = a || selected[0].area;
        }
        return { area: a, fish };
    };

    const areas = (f?.areas?.allObjects ?? [])
        .filter((area) => isFishingAreaUnlocked(f, area))
        .map((area) => ({
        name: area?.name ?? "Unknown Area",
        fish: (area?.fish ?? []).map((fish) => {
            let unlocked = false;
            try {
                unlocked = !!f?.isMasteryActionUnlocked?.(fish);
            } catch (e) {}
            let minInt = null;
            let maxInt = null;
            try { minInt = Number(f?.getMinFishInterval?.(fish)); } catch (e) {}
            try { maxInt = Number(f?.getMaxFishInterval?.(fish)); } catch (e) {}
            let catchChances = null;
            try {
                catchChances = chancesForFish(f, area, fish);
            } catch (e) {
                catchChances = { error: String(e?.message ?? e) };
            }
            return {
                name: fish?.name ?? "Unknown Fish",
                level: Number(fish?.level ?? 0),
                xp: Number(fish?.baseExperience ?? 0),
                minMs: minInt,
                maxMs: maxInt,
                unlocked,
                catchChances,
            };
        }),
    }));

    let isFishing = false;
    let fishingArea = null;
    let fishingFish = null;
    const menus = Array.from(document.querySelectorAll("fishing-area-menu"));
    for (const menu of menus) {
        const btns = menu.querySelectorAll("button");
        for (const b of btns) {
            const t = (b.textContent || "").replace(/\\s+/g, " ").trim();
            if (!/stop\\s+fishing/i.test(t)) continue;
            isFishing = true;
            const blob = (menu.textContent || "").replace(/\\s+/g, " ");
            const areaObjs = f?.areas?.allObjects ?? [];
            for (const a of areaObjs) {
                const n = a?.name;
                if (n && blob.includes(n)) {
                    fishingArea = n;
                    break;
                }
            }
            const enriched = enrichFishingFishFromGame(fishingArea, fishingFish);
            fishingArea = enriched.area;
            fishingFish = enriched.fish;
            break;
        }
        if (isFishing) break;
    }
    if (!isFishing && f?.isActive) {
        isFishing = true;
        const enriched = enrichFishingFishFromGame(fishingArea, fishingFish);
        fishingArea = enriched.area;
        fishingFish = enriched.fish;
    } else if (isFishing) {
        const enriched = enrichFishingFishFromGame(fishingArea, fishingFish);
        fishingArea = enriched.area;
        fishingFish = enriched.fish;
    }

    return { ok: true, level, currentRod, isFishing, fishingArea, fishingFish, selected, areas };
}"""
