#!/usr/bin/env python3
"""
observations/cooking.py - Read-only cooking state.

Usage:
  python scripts/observations/cooking.py list
  python scripts/observations/cooking.py gloves

`list` uses `game.cooking` only (no DOM reads for activity): selected recipe from
`activeRecipe`, in-progress cooking from `isActive` (same as `actions/cooking.py`).
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
        if not navigate("cooking", page=page, quiet=True):
            print("Could not navigate to Cooking.")
            return False
        page.wait_for_timeout(200)
        data = page.evaluate(
            """() => {
                const c = game?.cooking;
                let selectedRecipe = null;
                try {
                    selectedRecipe = c?.activeRecipe?.name ?? null;
                } catch (e) {
                    selectedRecipe = null;
                }
                let isCooking = false;
                try {
                    isCooking = !!c?.isActive;
                } catch (e) {
                    isCooking = false;
                }
                const rows = (c?.actions?.allObjects ?? []).map(a => {
                    let unlocked = false;
                    try { unlocked = !!c?.isMasteryActionUnlocked?.(a); } catch (e) {}
                    let interval = null;
                    try { interval = Number(c?.getRecipeCookingInterval?.(a)); } catch (e) {}
                    return {
                        name: a?.name ?? "Unknown",
                        category: a?.category?.name ?? a?.category?.id ?? "Unknown",
                        level: Number(a?.level ?? 0),
                        xp: Number(a?.baseExperience ?? 0),
                        interval,
                        unlocked,
                    };
                });
                return {
                    level: Number(c?.level ?? 0),
                    selectedRecipe,
                    isCooking,
                    rows,
                };
            }"""
        )

    print(f"Cooking Level: {int(data['level'])}")
    sel = data.get("selectedRecipe")
    print(f"Selected recipe: {sel or 'none'}")
    if data.get("isCooking"):
        if sel:
            print(f"Currently cooking: yes — {sel}")
        else:
            print("Currently cooking: yes — (unknown recipe)")
    else:
        print("Currently cooking: no")
    print("Recipes:")
    for r in data["rows"]:
        state = "UNLOCKED" if r["unlocked"] else "LOCKED"
        interval = f"{(r['interval'] / 1000):.2f}s" if r["interval"] else "?"
        print(
            f"- {r['name']} [{r['category']}]: {state} | level {int(r['level'])} | "
            f"{int(r['xp'])} XP | {interval}"
        )
    return True


def show_gloves() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("cooking", page=page, quiet=True):
            print("Could not navigate to Cooking.")
            return False
        page.wait_for_timeout(200)
        data = page.evaluate(
            """() => {
                const eq = (game?.combat?.player?.equipment?.equippedArray ?? [])
                    .find((e) => String(e?.slot?.id ?? "").toLowerCase().includes("gloves"));
                const item = eq?.item ?? null;
                if (!item || String(item?.id ?? "").includes("Empty_Equipment")) {
                    return { equipped: false, name: null, charges: null };
                }
                const name = String(item?.name ?? "Unknown Gloves");
                let charges = null;
                try {
                    charges = Number(game?.itemCharges?.getCharges?.(item) ?? 0);
                } catch (e) {
                    charges = null;
                }
                return { equipped: true, name, charges };
            }"""
        )

    if not data.get("equipped"):
        print("Cooking Gloves: none equipped")
        return True

    name = data.get("name") or "Cooking Gloves"
    if "cooking" not in name.lower():
        print(f"Cooking Gloves: not equipped (currently: {name})")
        return True

    charges = data.get("charges")
    if isinstance(charges, (int, float)):
        print(f"Cooking Gloves: {name} | Charges: {int(charges):,}")
    else:
        print(f"Cooking Gloves: {name} | Charges: unknown")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log_observation("cooking.py", sys.argv[1:], False, "Unknown/missing command.")
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower().strip()
    if cmd == "list":
        ok, out = run_observation(show_list)
        log_observation("cooking.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    if cmd == "gloves":
        ok, out = run_observation(show_gloves)
        log_observation("cooking.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    log_observation("cooking.py", sys.argv[1:], False, f"Unknown command: {cmd}")
    print("Unknown command. Use: list | gloves")
    sys.exit(1)

