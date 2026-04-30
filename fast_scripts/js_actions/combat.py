from __future__ import annotations

COMBAT_FOOD_SLOT_JS = """
(slot) => {
    const p = game?.combat?.player;
    const req = Number(slot);
    if (!Number.isFinite(req) || req < 1 || req > 3) {
        return { ok:false, error:"Food slot must be 1, 2, or 3" };
    }
    if (typeof p?.selectFood !== "function") {
        return { ok:false, error:"player.selectFood unavailable" };
    }
    const i = req - 1;
    try {
        p.selectFood(i);
        return { ok:true, slot:req };
    } catch (e) {
        return { ok:false, error:`player.selectFood failed: ${String(e)}` };
    }
}
"""

COMBAT_LIST_JS = """
() => {
    const monsters = (game?.monsters?.allObjects ?? []).map((m) => ({
        id: m?.id ?? "",
        name: m?.name ?? "Unknown",
        level: Number(m?.combatLevel ?? m?.level ?? 0),
    }));
    const dungeons = (game?.dungeons?.allObjects ?? []).map((d) => ({
        id: d?.id ?? "",
        name: d?.name ?? "Unknown",
    }));
    return { monsters, dungeons };
}
"""

COMBAT_LOOT_JS = """
() => {
    const combat = game?.combat;
    const loot = game?.combat?.loot;
    if (!loot) return { ok:false, error:"combat loot unavailable" };
    const bank = game?.bank;
    const usedSlots = Number(bank?.occupiedSlots ?? bank?.usedSlots ?? 0);
    const maxSlots = Number(bank?.maximumSlots ?? bank?.maxSlots ?? 0);
    if (Number.isFinite(usedSlots) && Number.isFinite(maxSlots) && maxSlots > 0 && usedSlots >= maxSlots) {
      return { ok:false, error:"bank is full" };
    }
    if (typeof loot?.lootAll !== "function") {
        return { ok:false, error:"loot.lootAll unavailable" };
    }
    try {
        loot.lootAll();
        return { ok:true };
    } catch (e) {
        return { ok:false, error:`lootAll failed: ${String(e)}` };
    }
}
"""

COMBAT_STOP_JS = """
() => {
    const combat = game?.combat;
    if (!combat.isActive) return { ok:false, error:"combat is not active" };
    if (!combat) return { ok:true, ran:false, message:"combat unavailable" };
    if (typeof combat?.stop !== "function") {
        return { ok:true, ran:false, message:"combat.stop unavailable" };
    }
    try {
        combat.stop();
        return { ok:true, ran:true };
    } catch (e) {
        const msg = String(e ?? "");
        if (/not active|not in combat|inactive/i.test(msg)) {
            return { ok:true, ran:false, message:msg || "combat not active" };
        }
        return { ok:false, error:`combat.stop failed: ${msg}` };
    }
}
"""

COMBAT_STYLE_JS = """
(label) => {
    const p = game?.combat?.player;
    if (!p) return { ok:false, error:"combat player unavailable" };
    if (typeof p?.setAttackStyle !== "function") {
        return { ok:false, error:"player.setAttackStyle unavailable" };
    }
    const q = String(label ?? "").toLowerCase().trim();
    const all = Array.from(game?.attackStyles?.allObjects ?? []);
    const style = all.find((s) => {
        const a = String(s?.name ?? "").toLowerCase().trim();
        return a === q;
    });
    if (!style) return { ok:false, error:`Unknown combat style: ${label}` };
    if (!style?.attackType) return { ok:false, error:`Style has no attackType: ${label}` };
    try {
        p.setAttackStyle(style.attackType, style);
        return { ok:true, style: style.name ?? style._name ?? label };
    } catch (e) {
        return { ok:false, error:`setAttackStyle failed: ${String(e)}` };
    }
}
"""

COMBAT_TARGET_JS = """
(target) => {
    const combat = game?.combat;
    if (!combat) return { ok:false, error:"combat unavailable" };
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const q = norm(target);

    const monsters = Array.from(game?.monsters?.allObjects ?? []);
    const monster = monsters.find((m) => norm(m?.name) === q) || monsters.find((m) => q && norm(m?.name).includes(q));
    if (monster) {
        const areas = Array.from(game?.combatAreas?.allObjects ?? []);
        const area = areas.find((a) => {
            const list = Array.from(a?.monsters ?? []);
            return list.some((mm) => mm === monster || String(mm?.id ?? "") === String(monster?.id ?? ""));
        });
        if (!area) return { ok:false, error:`Could not resolve area for monster: ${monster?.name ?? target}` };
        if (typeof combat?.selectMonster !== "function") {
            return { ok:false, error:"combat.selectMonster unavailable" };
        }
        try {
            combat.selectMonster(monster, area);
            return { ok:true, target: monster?.name ?? target };
        } catch (e) {
            return { ok:false, error:`selectMonster failed: ${String(e)}` };
        }
    }

    const dungeons = Array.from(game?.dungeons?.allObjects ?? []);
    const dungeon = dungeons.find((d) => norm(d?.name) === q) || dungeons.find((d) => q && norm(d?.name).includes(q));
    if (dungeon) {
        if (typeof combat?.selectDungeon !== "function") {
            return { ok:false, error:"combat.selectDungeon unavailable" };
        }
        try {
            combat.selectDungeon(dungeon);
            return { ok:true, dungeon: dungeon?.name ?? target };
        } catch (e) {
            return { ok:false, error:`selectDungeon failed: ${String(e)}` };
        }
    }

    return { ok:false, error:`Unknown or unavailable combat target: ${target}` };
}
"""

COMBAT_UNEQUIP_FOOD_JS = """
(slot) => {
    const p = game?.combat?.player;
    const f = p?.food;
    const req = Number(slot);
    if (!Number.isFinite(req) || req < 1 || req > 3) {
        return { ok:false, error:"Food slot must be 1, 2, or 3" };
    }
    const i = req - 1;
    const s = f?.slots?.[i];
    if (!s || s?.quantity <= 0) {
        return { ok:false, error:"slot already empty", slot:req };
    }
    try {
        p.selectFood(i);
        p.unequipFood();
        return { ok:true, slot:req };
    } catch (e) {
        return { ok:false, error:`unequip failed: ${String(e)}` };
    }
}
"""
