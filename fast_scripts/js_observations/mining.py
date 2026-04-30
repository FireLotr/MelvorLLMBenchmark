from __future__ import annotations

MINING_LIST_JS = """() => {
    const m = game?.mining;
    if (!m) return { ok:false, error:"no mining" };
    const lvl = Number(m?.level ?? 0);
    let active = null;
    try { active = m?.activeRock?.name ?? null; } catch (e) { active = null; }
    const currentPickaxe = (() => {
        const displays = Array.from(document.querySelectorAll("upgrade-chain-display"));
        for (const d of displays) {
            const txt = (d.textContent || "").replace(/\\s+/g, " ").trim();
            const mm = txt.match(/^Current Pickaxe\\s+(.+)$/i);
            if (mm) return mm[1].trim();
        }
        return null;
    })();
    const cards = Array.from(
        document.querySelectorAll(
            "a.block.block-rounded.block-link-pop.border-top.border-mining.border-4x.pointer-enabled"
        )
    ).map((card) => (card.textContent || "").replace(/\\s+/g, " ").trim());
    const rows = (m?.actions?.allObjects ?? []).map(a => ({
        name: a?.name ?? "Unknown",
        level: Number(a?.level ?? 0),
        xp: Number(a?.baseExperience ?? 0),
        rockHP: Number(a?.maxHP ?? a?.currentHP ?? 0),
        respawnMs: Number(a?.baseRespawnInterval ?? 0),
        mineSec: (() => {
            const name = a?.name ?? "";
            for (const txt of cards) {
                if (!txt.includes(name)) continue;
                const sec = txt.match(/(\\d+(?:\\.\\d+)?)s/);
                if (sec) return Number(sec[1]);
            }
            try {
                if (typeof m?.getActionInterval === "function") {
                    const ms = Number(m.getActionInterval(a) ?? 0);
                    if (ms > 0) return ms / 1000;
                }
            } catch (e) {}
            const raw = Number(a?.baseInterval ?? 0);
            if (raw <= 0) return 0;
            return raw > 100 ? raw / 1000 : raw;
        })(),
        unlocked: lvl >= Number(a?.level ?? 0),
    }));
    return { ok:true, level:lvl, active, currentPickaxe, rows };
}"""

MINING_GLOVES_JS = """() => {
    const eq = (game?.combat?.player?.equipment?.equippedArray ?? [])
        .find((e) => String(e?.slot?.id ?? "").toLowerCase().includes("gloves"));
    const item = eq?.item ?? null;
    if (!item || String(item?.id ?? "").includes("Empty_Equipment")) {
        return { ok: true, equipped: false, name: null, charges: null };
    }
    let charges = null;
    try { charges = Number(game?.itemCharges?.getCharges?.(item) ?? 0); } catch (e) { charges = null; }
    return { ok: true, equipped: true, name: item?.name ?? "Unknown Gloves", charges };
}"""
