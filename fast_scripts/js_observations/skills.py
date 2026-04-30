from __future__ import annotations

SKILLS_LEVELS_JS = """() => {
    const cumulativeXpForLevel = (level) => {
        const L = Math.floor(Number(level) || 0);
        if (L <= 1) return 0;
        let points = 0;
        for (let lv = 1; lv < L; lv++) points += Math.floor(lv + 300 * Math.pow(2, lv / 7));
        return Math.floor(points / 4);
    };
    const skillsSource = game.skills instanceof Map ? Array.from(game.skills.values()) : (game.skills?.allObjects ?? game.skills ?? []);
    const skills = skillsSource.map((s) => {
        const level = Math.floor(Number(s?.level ?? 0));
        const rawCap = Math.floor(Number(s?._currentLevelCap ?? 99));
        const cap = rawCap > 0 ? rawCap : 99;
        const curXp = Number(s?._xp ?? s?.xp ?? 0);
        let xpToNext = null;
        if (level < cap) {
            const need = cumulativeXpForLevel(level + 1);
            xpToNext = Math.max(0, Math.ceil(need - curXp - 1e-9));
        }
        return {
            name: s?.name ?? "Unknown Skill",
            level,
            xp: curXp,
            xpToNext,
        };
    });
    skills.sort((a, b) => a.name.localeCompare(b.name));
    return { ok: true, skills };
}"""

SKILLS_ACTIVE_JS = """() => {
    const activities = [];
    const fishingDetailFromGame = (g) => {
        if (!g) return "active";
        const area = g.activeFishingArea?.name ?? null;
        let fish = null;
        if (g.activeFishingArea && g.selectedAreaFish) {
            try {
                const hit = g.selectedAreaFish.get(g.activeFishingArea);
                if (hit?.name) fish = hit.name;
            } catch (e) {}
        }
        fish = fish || g.activeRecipe?.name || g.selectedFish?.name || null;
        if (fish && area) return `${fish} @ ${area}`;
        if (fish) return String(fish);
        if (area) return String(area);
        return "active";
    };
    const com = game?.combat;
    if (com?.isActive) {
        const parts = [];
        if (com.dungeon?.name) parts.push(String(com.dungeon.name));
        const areaName = com.player?.combatArea?.name ?? com.player?.slayerArea?.name ?? com.selectedArea?.name ?? null;
        if (areaName) parts.push(String(areaName));
        const mon = com.enemy?.name ?? com.enemy?.monster?.name ?? com.selectedMonster?.name ?? null;
        let detail = parts.length ? parts.join(" — ") : "";
        if (mon) detail = detail ? `${detail} — vs ${mon}` : `vs ${mon}`;
        activities.push({ skill: "Combat", detail: detail || "active" });
    }
    const gameKeyByLocal = {Woodcutting:"woodcutting",Fishing:"fishing",Firemaking:"firemaking",Cooking:"cooking",Mining:"mining",Smithing:"smithing",Thieving:"thieving",Fletching:"fletching",Crafting:"crafting",Runecrafting:"runecrafting",Herblore:"herblore",Agility:"agility",Summoning:"summoning",Astrology:"astrology",Magic:"magic",Township:"township"};
    const skillsSource = game.skills instanceof Map ? Array.from(game.skills.values()) : (game.skills?.allObjects ?? []);
    for (const s of skillsSource) {
        const lid = s?._localID;
        if (!lid || s.isActive !== true) continue;
        const gk = gameKeyByLocal[lid];
        if (!gk) continue;
        const g = game[gk];
        let detail = "active";
        try {
            if (lid === "Woodcutting") {
                const names = g?.activeTrees ? Array.from(g.activeTrees).map((t) => t?.name).filter(Boolean) : [];
                if (names.length) detail = names.join(", ");
            } else if (lid === "Fishing") {
                detail = fishingDetailFromGame(g);
            } else if (lid === "Firemaking" || lid === "Cooking" || lid === "Smithing") {
                if (g?.activeRecipe?.name) detail = String(g.activeRecipe.name);
            } else if (lid === "Mining") {
                const rn = g?.activeProgressRock?.name ?? g?.selectedRock?.name ?? null;
                if (rn) detail = String(rn);
            } else if (g?.activeRecipe?.name) detail = String(g.activeRecipe.name);
        } catch (e) {}
        activities.push({ skill: lid, detail });
    }
    return { ok: true, activities };
}"""
