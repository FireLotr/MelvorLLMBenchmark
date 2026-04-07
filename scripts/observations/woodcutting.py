#!/usr/bin/env python3
"""
observations/woodcutting.py - Read-only woodcutting state.

Usage:
  python scripts/observations/woodcutting.py trees

Works from any page (navigates to Woodcutting internally if needed).
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


def show_trees() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("woodcutting", page=page, quiet=True):
            print("Could not navigate to Woodcutting.")
            return False
        page.wait_for_timeout(200)

        data = page.evaluate(
            """() => {
                const wc = game?.woodcutting;
                const lvl = Number(game?.woodcutting?.level ?? 0);
                const active = wc?.activeTrees ? Array.from(wc.activeTrees).map(t => t.name) : [];
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
                const trees = (wc?.actions?.allObjects ?? []).map(t => {
                    let unlocked = false;
                    try {
                        unlocked = !!wc?.isTreeUnlocked?.(t);
                    } catch (e) {
                        unlocked = false;
                    }
                    const levelReq = Number(t?.level ?? 0);
                    return {
                        name: t?.name ?? "Unknown",
                        level: levelReq,
                        xp: Number(t?.baseExperience ?? 0),
                        interval: Number(t?.baseInterval ?? 0),
                        unlocked,
                    };
                });
                return { lvl, active, limit, currentAxe, trees };
            }"""
        )

    print(f"Woodcutting Level: {int(data['lvl'])}")
    print(f"Current Axe: {data.get('currentAxe') or 'Unknown'}")
    print(f"Tree Cut Limit: {int(data['limit'])}")
    if data["active"]:
        print(f"Currently Cutting: {', '.join(data['active'])}")
    else:
        print("Currently Cutting: none")

    print("\nTrees:")
    for t in data["trees"]:
        status = "UNLOCKED" if t["unlocked"] else "LOCKED"
        interval = f"{(t['interval'] / 1000):.2f}s" if t["interval"] else "?"
        if t["unlocked"]:
            print(
                f"- {t['name']}: {status} (requires level {int(t['level'])}) | "
                f"{int(t['xp'])} XP | {interval}"
            )
        else:
            remain = max(0, int(t["level"]) - int(data["lvl"]))
            print(
                f"- {t['name']}: {status} (unlocks at level {int(t['level'])}, {remain} level(s) to go) | "
                f"{int(t['xp'])} XP | {interval}"
            )
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1].lower().strip() != "trees":
        log_observation("woodcutting.py", sys.argv[1:], False, "Unknown/missing command.")
        print(__doc__)
        sys.exit(1)
    ok, out = run_observation(show_trees)
    log_observation("woodcutting.py", sys.argv[1:], ok, out)
    sys.exit(0 if ok else 1)

