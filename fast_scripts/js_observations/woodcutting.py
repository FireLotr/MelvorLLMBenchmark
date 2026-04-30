from __future__ import annotations

WOODCUTTING_LIST_JS = """() => {
    const wc = game?.woodcutting;
    if (!wc) return { ok: false, error: "no woodcutting" };
    const lvl = Number(wc?.level ?? 0);
    const active = wc?.activeTrees ? Array.from(wc.activeTrees).map((t) => t?.name ?? "Unknown") : [];
    const limit = Number(wc?.treeCutLimit ?? 1);
    const currentAxe = (() => {
        const displays = Array.from(document.querySelectorAll("upgrade-chain-display"));
        for (const d of displays) {
            const text = (d.textContent || "").replace(/\\s+/g, " ").trim();
            const m = text.match(/^Current Axe\\s+(.+)$/i);
            if (m) return m[1].trim();
        }
        return null;
    })();
    const trees = (wc?.actions?.allObjects ?? []).map((t) => {
        let unlocked = false;
        try { unlocked = !!wc?.isTreeUnlocked?.(t); } catch (e) {}
        return {
            name: t?.name ?? "Unknown",
            level: Number(t?.level ?? 0),
            xp: Number(t?.baseExperience ?? 0),
            interval: Number(t?.baseInterval ?? 0),
            unlocked,
        };
    });
    return { ok: true, lvl, active, limit, currentAxe, trees };
}"""
