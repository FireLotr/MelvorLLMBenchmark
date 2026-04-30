from __future__ import annotations

COMBAT_STYLE_READ_JS = """() => {
    const p = game?.combat?.player;
    if (!p) return { ok:false, error:"no player" };
    let style = null;
    if (p.attackType === "melee") style = p.attackStyles?.melee?.name ?? null;
    if (p.attackType === "ranged") style = p.attackStyles?.ranged?.name ?? null;
    if (p.attackType === "magic") style = p.attackStyles?.magic?.name ?? null;
    return { ok:true, attackType: p.attackType ?? null, style };
}"""

COMBAT_AUTOEAT_READ_JS = """() => {
    const p = game?.combat?.player;
    if (!p) return { ok:false, error:"no player" };
    return {
        ok: true,
        autoEatThreshold: Number(p?.autoEatThreshold ?? p?.stats?._autoEatThreshold ?? 0),
        autoEatHPLimit: Number(p?.autoEatHPLimit ?? p?.stats?._autoEatHPLimit ?? 0),
    };
}"""

COMBAT_FOOD_SLOT_READ_JS = """() => {
    const p = game?.combat?.player;
    const f = p?.food;
    if (!f) return { ok:false, error:"no food" };
    const slots = f?.slots ?? [];
    const asSlotNum = (v) => {
        const n = Number(v);
        if (Number.isFinite(n) && n >= 0 && n < 3) return n + 1; // 0-based -> 1-based
        if (Number.isFinite(n) && n >= 1 && n <= 3) return n;    // already 1-based
        return null;
    };

    const fields = {
        selectedSlot: f?.selectedSlot ?? null,
        currentSlot: f?.currentSlot ?? null,
        activeSlot: f?.activeSlot ?? null,
    };
    for (const [name, raw] of Object.entries(fields)) {
        const slot = asSlotNum(raw);
        if (slot) return { ok:true, activeFoodSlot: slot, source: `food.${name}`, raw };
    }

    const sf = p?.selectedFood;
    const sid = String(sf?.slot?.id ?? sf?.slotID ?? "");
    const m = sid.match(/(\\d+)/);
    if (m) {
        const n = Number(m[1]);
        if (Number.isFinite(n) && n >= 1 && n <= 3) {
            return { ok:true, activeFoodSlot: n, source: "player.selectedFood.slot", raw: sid };
        }
    }

    const sfID = String(sf?.item?.id ?? "");
    const sfQty = Number(sf?.quantity ?? NaN);
    if (sfID) {
        for (let i = 0; i < slots.length; i++) {
            const s = slots[i];
            const id = String(s?.item?.id ?? "");
            const q = Number(s?.quantity ?? NaN);
            if (id && id === sfID && (!Number.isFinite(sfQty) || q === sfQty)) {
                return { ok:true, activeFoodSlot: i + 1, source: "selectedFood.item+qty", raw: sfID };
            }
        }
        for (let i = 0; i < slots.length; i++) {
            if (String(slots[i]?.item?.id ?? "") === sfID) {
                return { ok:true, activeFoodSlot: i + 1, source: "selectedFood.item", raw: sfID };
            }
        }
    }

    return { ok:false, error:"active_food_slot_unavailable" };
}"""

COMBAT_STATS_READ_JS = """() => {
    const p = game?.combat?.player;
    if (!p) return { ok:false, error:"no player" };
    const s = p?.stats ?? {};
    let dr = null;
    let drSource = null;
    try {
        const res = s?._resistances;
        if (res instanceof Map) {
            for (const [k, vRaw] of res.entries()) {
                if (k?.id === "melvorD:Normal") {
                    const v = Number(vRaw);
                    if (Number.isFinite(v)) {
                        dr = v;
                        drSource = "stats._resistances[melvorD:Normal]";
                    }
                    break;
                }
            }
        }
    } catch (e) {}
    if (!Number.isFinite(dr)) {
        const drCandidates = [
            ["stats.damageReduction", s?.damageReduction],
            ["stats._damageReduction", s?._damageReduction],
            ["player.damageReduction", p?.damageReduction],
            ["player._damageReduction", p?._damageReduction],
            ["stats.resistance", s?.resistance],
            ["stats._resistance", s?._resistance],
        ];
        for (const [src, val] of drCandidates) {
            const num = Number(val);
            if (Number.isFinite(num)) {
                dr = num;
                drSource = src;
                break;
            }
        }
    }
    const hc = Number(s.hitChance ?? s._hitChance ?? NaN);
    const inCombat = !!game?.combat?.isActive;
    const enemy = game?.combat?.enemy;
    const selectedMonster = game?.combat?.selectedMonster ?? null;
    const enemyReady = !!(enemy && Number(enemy?.stats?._maxHitpoints ?? enemy?.stats?.maxHitpoints ?? 0) > 0);
    let hitChance = Number.isFinite(hc) ? hc : null;
    // Outside active combat the game often reports placeholder 0 even when UI shows "-".
    if (!inCombat || !enemyReady) {
        if (hitChance === 0) hitChance = null;
    }
    const hitChanceTarget = (
        enemy?.monster?.name ??
        enemy?.name ??
        selectedMonster?.name ??
        null
    );
    const out = {
        ok:true,
        minHit: Number(s.minHit ?? 0),
        maxHit: Number(s.maxHit ?? 0),
        accuracy: Number(s.accuracy ?? 0),
        hitChance,
        hitChanceTarget,
        hitChanceInCombat: inCombat,
        evasionMelee: Number(s.evasion?.melee ?? s.evasionMelee ?? 0),
        evasionRanged: Number(s.evasion?.ranged ?? s.evasionRanged ?? 0),
        evasionMagic: Number(s.evasion?.magic ?? s.evasionMagic ?? 0),
        damageReduction: Number.isFinite(dr) ? dr : null,
        damageReductionSource: drSource,
    };
    if (!Number.isFinite(dr)) {
        out.ok = false;
        out.error = "damage_reduction_unavailable";
    }
    return out;
}"""

COMBAT_CURRENT_LOOT_JS = """() => {
    const loot = game?.combat?.loot ?? {};
    const lootRows = [];
    let occupiedNative = null;
    let usedSource = null;
    const pushLoot = (name, qty = null) => {
        const nm = String(name ?? "").trim();
        if (!nm) return;
        const qn = Number(qty);
        const existing = lootRows.find((r) => r.name === nm);
        if (existing) {
            if (Number.isFinite(qn)) existing.qty = Number(existing.qty ?? 0) + qn;
            return;
        }
        lootRows.push({ name: nm, qty: Number.isFinite(qn) ? qn : null });
    };
    const iterAny = (v, fn) => {
        if (!v) return;
        if (Array.isArray(v)) {
            for (const e of v) fn(e);
            return;
        }
        if (v instanceof Map) {
            for (const [k, val] of v.entries()) fn([k, val]);
            return;
        }
        if (typeof v[Symbol.iterator] === "function") {
            for (const e of v) fn(e);
            return;
        }
        if (typeof v === "object") {
            for (const e of Object.values(v)) fn(e);
        }
    };
    try {
        const sources = [loot?.drops, loot?.items, loot?.loot, loot?.sortedDropsArray];
        const sizeOf = (src) => {
            if (!src) return null;
            if (Array.isArray(src)) return src.length;
            if (src instanceof Map) return src.size;
            if (typeof src[Symbol.iterator] === "function") {
                try { return Array.from(src).length; } catch (e) {}
            }
            if (typeof src === "object") return Object.keys(src).length;
            return null;
        };
        for (const [idx, src] of sources.entries()) {
            const s = sizeOf(src);
            if (!Number.isFinite(s)) continue;
            occupiedNative = s;
            usedSource = ["drops", "items", "loot", "sortedDropsArray"][idx];
            iterAny(src, (e) => {
                if (Array.isArray(e) && e.length === 2) {
                    const k = e[0];
                    const v = e[1];
                    pushLoot(
                        k?.item?.name ?? k?.name ?? k?.itemName ?? v?.item?.name ?? v?.name ?? v?.itemName,
                        v?.quantity ?? v?.qty ?? v ?? null
                    );
                    return;
                }
                pushLoot(e?.item?.name ?? e?.name ?? e?.itemName, e?.quantity ?? e?.qty ?? null);
            });
            break;
        }
    } catch (e) {}
    if (!Number.isFinite(occupiedNative)) {
        return { ok:false, error:"native loot container unavailable" };
    }
    const occupiedSlots = Number.isFinite(occupiedNative) ? occupiedNative : lootRows.length;
    const maxCandidates = [
        loot?.maxLoot,
        loot?.maxSlots,
        loot?.maximumSlots,
        loot?.lootSlots,
        loot?._maxSlots,
        loot?._maximumSlots,
        loot?.maxLootSlots,
        game?.combat?.maxLootSlots,
    ];
    let maxSlots = NaN;
    for (const v of maxCandidates) {
        const n = Number(v);
        if (Number.isFinite(n) && n >= 0) {
            maxSlots = n;
            break;
        }
    }
    // Game versions may hide or rename max slot fields; still report loot + occupied count.
    if (!Number.isFinite(maxSlots) || maxSlots < 0) {
        return {
            ok: true,
            current_loot: lootRows,
            occupied_slots: occupiedSlots,
            free_slots: null,
            max_slots: null,
            source: usedSource,
            max_slots_unknown: true,
        };
    }
    const freeSlots = Math.max(0, maxSlots - occupiedSlots);
    return {
        ok: true,
        current_loot: lootRows,
        occupied_slots: occupiedSlots,
        free_slots: freeSlots,
        max_slots: Number.isFinite(maxSlots) ? maxSlots : null,
        source: usedSource,
    };
}"""

COMBAT_ENEMY_READ_JS = """() => {
    const c = game?.combat;
    if (!c?.isActive) return { ok:false, error:"not in combat" };
    const e = game?.combat?.enemy;
    if (!e) return { ok:false, error:"no enemy" };
    const ps = game?.combat?.player?.stats ?? {};
    const es = e?.stats ?? {};
    let enemyDR = null;
    try {
        const res = es?._resistances;
        if (res instanceof Map) {
            for (const [k, vRaw] of res.entries()) {
                if (k?.id === "melvorD:Normal") {
                    const v = Number(vRaw);
                    if (Number.isFinite(v)) enemyDR = v;
                    break;
                }
            }
        }
    } catch (err) {}
    if (!Number.isFinite(enemyDR)) {
        const drCandidates = [
            es?.damageReduction,
            es?._damageReduction,
            e?.damageReduction,
            e?._damageReduction,
            es?.resistance,
            es?._resistance,
        ];
        for (const v of drCandidates) {
            const n = Number(v);
            if (Number.isFinite(n)) {
                enemyDR = n;
                break;
            }
        }
    }
    const playerHitChance = Number(ps.hitChance ?? ps._hitChance ?? NaN);
    const enemyHitChance = Number(es.hitChance ?? es._hitChance ?? NaN);
    return {
        ok:true,
        name: e?.monster?.name ?? e?.name ?? null,
        hp: Number(e?.hitpoints ?? 0),
        maxHp: Number(e?.stats?._maxHitpoints ?? e?.stats?.maxHitpoints ?? 0),
        attackType: e?.attackType ?? null,
        minHit: Number(es?.minHit ?? e?.minHit ?? 0),
        maxHit: Number(es?.maxHit ?? e?.maxHit ?? 0),
        accuracy: Number(es?.accuracy ?? e?.accuracy ?? 0),
        defenceLevel: Number(es?.defenceLevel ?? es?.defence ?? e?.defenceLevel ?? 0),
        evasionMelee: Number(es?.evasion?.melee ?? es?.evasionMelee ?? 0),
        evasionRanged: Number(es?.evasion?.ranged ?? es?.evasionRanged ?? 0),
        evasionMagic: Number(es?.evasion?.magic ?? es?.evasionMagic ?? 0),
        damageReduction: Number.isFinite(enemyDR) ? enemyDR : null,
        playerHitChance: Number.isFinite(playerHitChance) ? playerHitChance : null,
        enemyHitChance: Number.isFinite(enemyHitChance) ? enemyHitChance : null,
    };
}"""

COMBAT_DUNGEON_COMPLETION_JS = """() => {
    const mgr = game?.combat?.player?.manager;
    if (!mgr) return { ok: false, error: "combat.player.manager missing", rows: [] };
    const dc = mgr.dungeonCompletion;
    const byId = Object.create(null);
    const record = (key, val) => {
        const n = Number(val);
        if (!Number.isFinite(n) || n < 0) return;
        if (key && typeof key === "object" && key.id) byId[key.id] = Math.max(byId[key.id] ?? 0, n);
        else if (typeof key === "string" && key.length) byId[key] = Math.max(byId[key] ?? 0, n);
    };
    if (dc instanceof Map) {
        for (const [k, v] of dc.entries()) record(k, v);
    } else if (dc && typeof dc === "object") {
        for (const [k, v] of Object.entries(dc)) record(k, v);
    }
    const resolveCount = (d) => {
        if (dc instanceof Map && dc.has(d)) {
            const n = Number(dc.get(d));
            if (Number.isFinite(n)) return n;
        }
        if (d?.id && byId[d.id] != null) return Number(byId[d.id]);
        if (typeof mgr.getDungeonCompleteCount === "function") {
            try {
                const n = Number(mgr.getDungeonCompleteCount(d));
                if (Number.isFinite(n)) return n;
            } catch (e) {}
        }
        return 0;
    };
    const rows = [];
    for (const d of game?.dungeons?.allObjects ?? []) {
        rows.push({ id: d?.id ?? "", name: d?.name ?? "Unknown", completions: resolveCount(d) });
    }
    rows.sort((a, b) => String(a.name).localeCompare(String(b.name)));
    return { ok: true, rows };
}"""

COMBAT_DROPS_JS = """(pack) => {
    const mode = String(pack?.mode ?? "").toLowerCase();
    const query = String(pack?.query ?? "").toLowerCase().trim();
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\\s+/g, " ").trim();
    const toNum = (v) => (typeof v === "number" ? Number(v) : null);

    const monsters = (game?.monsters?.allObjects ?? []).map((m) => {
        const drops = [];
        const loot = m?.lootTable?.sortedDropsArray ?? [];
        for (const entry of loot) {
            drops.push({
                name: entry?.item?.name ?? "Unknown",
                min: toNum(entry?.minQuantity),
                max: toNum(entry?.maxQuantity),
                source: "lootTable",
            });
        }
        if (m?.bones?.item) {
            const qty = toNum(m?.bones?.quantity);
            drops.push({ name: m.bones.item.name ?? "Bones", min: qty, max: qty, source: "bones" });
        }
        for (const c of (m?.currencyDrops ?? [])) {
            drops.push({
                name: c?.currency?.name ?? "Currency",
                min: toNum(c?.min),
                max: toNum(c?.max),
                source: "currency",
            });
        }
        return { id: m?.id ?? "", name: m?.name ?? "Unknown Monster", drops };
    });

    const dungeons = (game?.dungeons?.allObjects ?? []).map((d) => {
        const drops = [];
        for (const reward of (d?.rewards ?? [])) {
            if (!reward) continue;
            const rewardName = reward?.name ?? "Unknown Reward";
            drops.push({ name: rewardName, min: 1, max: 1, source: "dungeonReward" });
            const rewardDrops = reward?.dropTable?.sortedDropsArray ?? [];
            for (const entry of rewardDrops) {
                drops.push({
                    name: entry?.item?.name ?? "Unknown",
                    min: toNum(entry?.minQuantity),
                    max: toNum(entry?.maxQuantity),
                    source: `from ${rewardName}`,
                });
            }
        }
        return { id: d?.id ?? "", name: d?.name ?? "Unknown Dungeon", drops };
    });

    if (mode === "all") return { ok: true, mode, monsters, dungeons };
    if (mode === "monster") {
        const exact = monsters.filter((m) => norm(m.name) === query);
        const matches = exact.length ? exact : monsters.filter((m) => query && norm(m.name).includes(query));
        return { ok: true, mode, matches };
    }
    if (mode === "dungeon") {
        const exact = dungeons.filter((d) => norm(d.name) === query);
        const matches = exact.length ? exact : dungeons.filter((d) => query && norm(d.name).includes(query));
        return { ok: true, mode, matches };
    }
    return { ok: false, error: "Unknown drops mode. Use all|monster|dungeon." };
}"""
