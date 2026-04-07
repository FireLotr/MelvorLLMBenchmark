#!/usr/bin/env python3
"""
observations/mining.py - Read-only mining state.

Usage:
  python scripts/observations/mining.py list
  python scripts/observations/mining.py gloves
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
        if not navigate("mining", page=page, quiet=True):
            print("Could not navigate to Mining.")
            return False
        page.wait_for_timeout(200)
        data = page.evaluate(
            """() => {
                const m = game?.mining;
                const lvl = Number(m?.level ?? 0);
                let active = null;
                try { active = m?.activeRock?.name ?? null; } catch (e) { active = null; }
                const currentPickaxe = (() => {
                    const displays = Array.from(document.querySelectorAll("upgrade-chain-display"));
                    for (const d of displays) {
                        const text = (d.textContent || "").replace(/\\s+/g, " ").trim();
                        const m = text.match(/^Current Pickaxe\\s+(.+)$/i);
                        if (m) return m[1].trim();
                    }
                    return null;
                })();
                const cards = Array.from(document.querySelectorAll("a.block.block-rounded.block-link-pop.border-top.border-mining.border-4x.pointer-enabled"))
                    .map(card => (card.textContent || "").replace(/\\s+/g, " ").trim());
                const rows = (m?.actions?.allObjects ?? []).map(a => {
                    const name = a?.name ?? "Unknown";
                    let mineSec = 0;
                    for (const txt of cards) {
                        if (!txt.includes(name)) continue;
                        const sec = txt.match(/(\\d+(?:\\.\\d+)?)s/);
                        if (sec) {
                            mineSec = Number(sec[1]);
                            break;
                        }
                    }
                    return {
                    name,
                    level: Number(a?.level ?? 0),
                    xp: Number(a?.baseExperience ?? 0),
                    rockHP: Number(a?.maxHP ?? a?.currentHP ?? 0),
                    respawnMs: Number(a?.baseRespawnInterval ?? 0),
                    mineSec,
                    unlocked: lvl >= Number(a?.level ?? 0),
                }});
                return {
                    level: lvl,
                    active,
                    currentPickaxe,
                    rows,
                };
            }"""
        )

    print(f"Mining Level: {int(data['level'])}")
    print(f"Current Pickaxe: {data.get('currentPickaxe') or 'Unknown'}")
    print(f"Active Rock: {data['active'] or 'none'}")
    print("Rocks:")
    for r in data["rows"]:
        state = "UNLOCKED" if r["unlocked"] else "LOCKED"
        mine_time = f"{float(r['mineSec']):.2f}s" if r["mineSec"] else "?"
        respawn = f"{(int(r['respawnMs']) / 1000):.2f}s" if r["respawnMs"] else "?"
        print(
            f"- {r['name']}: {state} | level {int(r['level'])} | "
            f"{int(r['xp'])} XP | mine {mine_time} | respawn {respawn} | rock HP {int(r['rockHP'])}"
        )
    return True


def show_gloves() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("mining", page=page, quiet=True):
            print("Could not navigate to Mining.")
            return False
        page.wait_for_timeout(200)
        data = page.evaluate(
            """() => {
                const eq = (game?.combat?.player?.equipment?.equippedArray ?? [])
                    .find((e) => String(e?.slot?.id ?? "").toLowerCase().includes("gloves"));
                const item = eq?.item ?? null;
                if (!item || String(item?.id ?? "").includes("Empty_Equipment")) {
                    return {
                        equipped: false,
                        name: null,
                        charges: null,
                    };
                }
                let charges = null;
                try {
                    charges = Number(game?.itemCharges?.getCharges?.(item) ?? 0);
                } catch (e) {
                    charges = null;
                }
                return {
                    equipped: true,
                    name: item?.name ?? "Unknown Gloves",
                    charges,
                };
            }"""
        )

    if not data.get("equipped"):
        print("Mining Gloves: none equipped")
        return True

    name = data.get("name") or "Mining Gloves"
    charges = data.get("charges")
    if isinstance(charges, (int, float)):
        print(f"Mining Gloves: {name} | Charges: {int(charges):,}")
    else:
        print(f"Mining Gloves: {name} | Charges: unknown")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log_observation("mining.py", sys.argv[1:], False, "Unknown/missing command.")
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower().strip()
    if cmd == "list":
        ok, out = run_observation(show_list)
        log_observation("mining.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    if cmd == "gloves":
        ok, out = run_observation(show_gloves)
        log_observation("mining.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)

    log_observation("mining.py", sys.argv[1:], False, f"Unknown command: {cmd}")
    print("Unknown command. Use: list | gloves")
    sys.exit(1)

