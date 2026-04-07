#!/usr/bin/env python3
"""
observations/firemaking.py - Read-only firemaking state.

Usage:
  python scripts/observations/firemaking.py list

Prints selected log (activeRecipe), whether a log burn is in progress (isActive),
and bonfire state: lit yes/no/unknown, and when lit the log type and skill XP bonus
percent from `bonfireTimer` / `litBonfireRecipe` when present, else DOM heuristics.
"""

import os
import sys
from playwright.sync_api import sync_playwright
from _navigate import navigate
from _observation_logging import log_observation, run_observation

os.environ.setdefault("NODE_NO_WARNINGS", "1")
CDP_URL = "http://localhost:9222"


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "melvor" in pg.url.lower():
                return pg
    return browser.contexts[0].pages[0]


def show_list() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("firemaking", page=page, quiet=True):
            print("Could not navigate to Firemaking.")
            return False
        page.wait_for_timeout(200)
        data = page.evaluate(
            """() => {
                const f = game?.firemaking;

                const tryDomBonfireMeta = (actionNames) => {
                    const bodyText = document.body.innerText || "";
                    const low = bodyText.toLowerCase();
                    const bonIdx = low.indexOf("bonfire");
                    if (bonIdx < 0) return { log: null, pct: null };
                    const slice = bodyText.slice(bonIdx, Math.min(bodyText.length, bonIdx + 900));
                    const lowSlice = slice.toLowerCase();
                    let pct = null;
                    const mPlus = slice.match(/\\+\\s*(\\d+(?:\\.\\d+)?)\\s*%/);
                    if (mPlus) pct = parseFloat(mPlus[1]);
                    const mBonus = lowSlice.match(/bonus[^\\d%]{0,60}(\\d+(?:\\.\\d+)?)\\s*%/);
                    if (mBonus) pct = parseFloat(mBonus[1]);
                    let log = null;
                    const sorted = [...actionNames].filter(Boolean).sort((a, b) => b.length - a.length);
                    for (const name of sorted) {
                        if (slice.includes(name)) {
                            log = name;
                            break;
                        }
                    }
                    return { log, pct: Number.isFinite(pct) ? pct : null };
                };

                const readLitBonfireRecipeMeta = () => {
                    let bonusLog = null;
                    let bonusPct = null;
                    try {
                        const r = f.litBonfireRecipe;
                        if (r && typeof r === "object") {
                            const ln = r.log?.name ?? r.name;
                            if (typeof ln === "string") bonusLog = ln;
                            const pb = Number(r.bonfireXPBonus);
                            if (Number.isFinite(pb)) bonusPct = pb;
                        }
                    } catch (e) {}
                    return { bonusLog, bonusPct };
                };

                const legacyBonfireLitBool = () => {
                    if (!f) return null;
                    const tryBool = (v) => (typeof v === "boolean" ? v : null);

                    const tryGame = () => {
                        try {
                            if (typeof f.isBonfireLit === "function") return !!f.isBonfireLit();
                            if (typeof f.isBonfireActive === "function") return !!f.isBonfireActive();
                        } catch (e) {}
                        try {
                            const b = tryBool(f.bonfireLit);
                            if (b !== null) return b;
                            const ia = tryBool(f.isBonfireActive);
                            if (ia !== null) return ia;
                        } catch (e) {}
                        try {
                            const n = Number(f.bonfireRemainingMilliseconds);
                            if (Number.isFinite(n)) return n > 0;
                        } catch (e) {}
                        try {
                            const o = f.bonfire ?? f.activeBonfire ?? f.skillBonfire ?? f.firemakingBonfire;
                            if (o != null && typeof o === "object") {
                                if (typeof o.isLit === "function") return !!o.isLit();
                                if (typeof o.isActive === "function") return !!o.isActive();
                                const x = tryBool(o.lit);
                                if (x !== null) return x;
                                const y = tryBool(o.active);
                                if (y !== null) return y;
                                const tr = Number(o.ticksRemaining ?? o.remainingTicks);
                                if (Number.isFinite(tr)) return tr > 0;
                                const t = o.timer;
                                if (t && typeof t === "object") {
                                    const left = Number(t.ticksLeft ?? t.remaining ?? t.ms);
                                    if (Number.isFinite(left)) return left > 0;
                                }
                            }
                        } catch (e) {}
                        try {
                            for (const k of Object.keys(f)) {
                                if (!/bonfire|bon_fire/i.test(k)) continue;
                                const v = f[k];
                                if (typeof v === "boolean") return v;
                                if (typeof v === "number") return v > 0;
                                if (v && typeof v === "object") {
                                    for (const prop of ["active", "lit", "isActive", "isLit"]) {
                                        const p = v[prop];
                                        if (typeof p === "function") {
                                            try {
                                                return !!p();
                                            } catch (e2) {}
                                        } else if (typeof p === "boolean") return p;
                                    }
                                    const tr2 = Number(v.ticksRemaining ?? v.remainingTicks);
                                    if (Number.isFinite(tr2)) return tr2 > 0;
                                }
                            }
                        } catch (e) {}
                        return null;
                    };

                    const tryDomLit = () => {
                        const bodyText = document.body.innerText || "";
                        const low = bodyText.toLowerCase();
                        const bonIdx = low.indexOf("bonfire");
                        const timeIdx = low.indexOf("time left");
                        if (bonIdx >= 0 && timeIdx >= 0 && Math.abs(bonIdx - timeIdx) < 500) return true;
                        if (bonIdx >= 0) {
                            const slice = low.slice(bonIdx, bonIdx + 280);
                            if (slice.includes("time left")) return true;
                            if (slice.includes("bonfire bonus")) return true;
                            if (slice.includes("active bonfire")) return true;
                        }
                        if (low.includes("bonfire is lit") || low.includes("bonfire: lit")) return true;

                        const candidates = document.querySelectorAll("button, a.btn, [role='button']");
                        for (const b of candidates) {
                            const t = (b.textContent || "").replace(/\\s+/g, " ").trim();
                            if (!/bonfire/i.test(t) || !/(light|ignite)/i.test(t)) continue;
                            const r = b.getBoundingClientRect();
                            if (r.width <= 0 || r.height <= 0) continue;
                            const st = window.getComputedStyle(b);
                            if (st.display === "none" || st.visibility === "hidden") continue;
                            if (b.disabled) continue;
                            return false;
                        }
                        return null;
                    };

                    const g = tryGame();
                    if (g !== null) return g;
                    return tryDomLit();
                };

                const readBonfireInfo = (actionNames) => {
                    const empty = { lit: null, bonusLog: null, bonusPct: null };
                    if (!f) return empty;
                    try {
                        const bt = f.bonfireTimer;
                        if (bt && typeof bt === "object" && typeof bt.active === "boolean") {
                            if (!bt.active) return { lit: false, bonusLog: null, bonusPct: null };
                            const ticks = Number(bt._ticksLeft);
                            if (Number.isFinite(ticks) && ticks <= 0) {
                                return { lit: false, bonusLog: null, bonusPct: null };
                            }
                            const meta = readLitBonfireRecipeMeta();
                            let { bonusLog, bonusPct } = meta;
                            if (bonusLog == null || bonusPct == null) {
                                const dom = tryDomBonfireMeta(actionNames);
                                if (bonusLog == null) bonusLog = dom.log;
                                if (bonusPct == null) bonusPct = dom.pct;
                            }
                            return { lit: true, bonusLog, bonusPct };
                        }
                    } catch (e) {}
                    const lit = legacyBonfireLitBool();
                    if (lit !== true) return { lit, bonusLog: null, bonusPct: null };
                    let { bonusLog, bonusPct } = readLitBonfireRecipeMeta();
                    if (bonusLog == null || bonusPct == null) {
                        const dom = tryDomBonfireMeta(actionNames);
                        if (bonusLog == null) bonusLog = dom.log;
                        if (bonusPct == null) bonusPct = dom.pct;
                    }
                    return { lit: true, bonusLog, bonusPct };
                };

                let active = null;
                try { active = f?.activeRecipe?.name ?? null; } catch (e) { active = null; }
                let isBurning = false;
                try { isBurning = !!f?.isActive; } catch (e) { isBurning = false; }

                const actionNames = (f?.actions?.allObjects ?? []).map((a) => a?.name).filter(Boolean);
                const bonfire = readBonfireInfo(actionNames);

                const rows = (f?.actions?.allObjects ?? []).map(a => {
                    let unlocked = false;
                    try { unlocked = !!f?.isMasteryActionUnlocked?.(a); } catch (e) {}
                    return {
                        name: a?.name ?? "Unknown",
                        level: Number(a?.level ?? 0),
                        xp: Number(a?.baseExperience ?? 0),
                        interval: Number(a?.baseInterval ?? 0),
                        unlocked,
                    };
                });
                return {
                    level: Number(f?.level ?? 0),
                    active,
                    isBurning,
                    bonfireLit: bonfire.lit,
                    bonfireBonusLog: bonfire.bonusLog,
                    bonfireBonusPercent: bonfire.bonusPct,
                    rows,
                };
            }"""
        )

    print(f"Firemaking Level: {int(data['level'])}")
    print(f"Active log (selected): {data['active'] or 'none'}")
    if data.get("isBurning"):
        name = data.get("active")
        extra = f" — {name}" if name else ""
        print(f"Currently burning: yes{extra}")
    else:
        print("Currently burning: no")

    bl = data.get("bonfireLit")
    blog = data.get("bonfireBonusLog")
    bpct = data.get("bonfireBonusPercent")

    def _fmt_pct(p):
        if p is None:
            return None
        try:
            x = float(p)
        except (TypeError, ValueError):
            return None
        if abs(x - round(x)) < 1e-9:
            return str(int(round(x)))
        return f"{x:g}"

    if bl is True:
        ps = _fmt_pct(bpct)
        if blog and ps is not None:
            print(f"Bonfire lit: yes — {blog}, +{ps}% skill XP")
        elif blog:
            print(f"Bonfire lit: yes — {blog}")
        elif ps is not None:
            print(f"Bonfire lit: yes — +{ps}% skill XP")
        else:
            print("Bonfire lit: yes")
    elif bl is False:
        print("Bonfire lit: no")
    else:
        print("Bonfire lit: unknown")

    print("Logs:")
    for r in data["rows"]:
        state = "UNLOCKED" if r["unlocked"] else "LOCKED"
        interval = f"{(r['interval'] / 1000):.2f}s" if r["interval"] else "?"
        print(f"- {r['name']}: {state} | level {int(r['level'])} | {int(r['xp'])} XP | {interval}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1].lower().strip() != "list":
        log_observation("firemaking.py", sys.argv[1:], False, "Unknown/missing command.")
        print(__doc__)
        sys.exit(1)
    ok, out = run_observation(show_list)
    log_observation("firemaking.py", sys.argv[1:], ok, out)
    sys.exit(0 if ok else 1)

