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

    const selected = f?.selectedAreaFish
        ? Array.from(f.selectedAreaFish.entries()).map(([area, fish]) => ({
              area: area?.name ?? "Unknown Area",
              fish: fish?.name ?? "Unknown Fish",
          }))
        : [];

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

    const areas = (f?.areas?.allObjects ?? []).map((area) => ({
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
            return {
                name: fish?.name ?? "Unknown Fish",
                level: Number(fish?.level ?? 0),
                xp: Number(fish?.baseExperience ?? 0),
                minMs: minInt,
                maxMs: maxInt,
                unlocked,
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
