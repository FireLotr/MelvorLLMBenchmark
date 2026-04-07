#!/usr/bin/env python3
"""
observations/smithing.py - Read-only smithing state.

Usage:
  python scripts/observations/smithing.py list    # full recipe table + activity
  python scripts/observations/smithing.py status  # level, active recipe, in-progress only
  python scripts/observations/smithing.py gloves

`list` / `status` use `game.smithing.activeRecipe` and `game.smithing.isActive` (same signal as
`actions/smithing.py` start/stop) — no DOM for that state. `status` does not open the Smithing page.
`list` includes each recipe's input items from `action.itemCosts` (quantity × item name).
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


def _format_item_costs(costs: list) -> str:
    if not costs:
        return "needs: (unknown)"
    parts: list[str] = []
    for c in costs:
        q = int(c.get("quantity", 0))
        name = (c.get("name") or "").strip() or (c.get("id") or "").strip() or "?"
        parts.append(f"{q}× {name}")
    return "needs: " + ", ".join(parts)


def _print_smithing_activity(data: dict) -> None:
    print(f"Smithing Level: {int(data['level'])}")
    active = data.get("active")
    print(f"Active recipe: {active or 'none'}")
    if data.get("isSmithing"):
        if active:
            print(f"Currently smithing: yes — {active}")
        else:
            print("Currently smithing: yes — (unknown recipe)")
    else:
        print("Currently smithing: no")


def show_status() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        data = page.evaluate(
            """() => {
                const s = game?.smithing;
                if (!s) return { ok: false, error: "game.smithing not available" };
                let isSmithing = false;
                try {
                    isSmithing = !!s.isActive;
                } catch (e) {
                    isSmithing = false;
                }
                let active = null;
                try {
                    active = s.activeRecipe?.name ?? null;
                } catch (e) {
                    active = null;
                }
                return {
                    ok: true,
                    level: Number(s.level ?? 0),
                    active,
                    isSmithing,
                };
            }"""
        )

    if not data.get("ok"):
        print(data.get("error", "Could not read smithing state."))
        return False
    _print_smithing_activity(data)
    return True


def show_list() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("smithing", page=page, quiet=True):
            print("Could not navigate to Smithing.")
            return False
        page.wait_for_timeout(200)
        data = page.evaluate(
            """() => {
                const s = game?.smithing;
                const rows = (s?.actions?.allObjects ?? []).map((a) => {
                    let unlocked = false;
                    try { unlocked = !!s?.isMasteryActionUnlocked?.(a); } catch (e) {}
                    const costs = [];
                    try {
                        for (const ic of a?.itemCosts ?? []) {
                            costs.push({
                                quantity: Number(ic?.quantity ?? 0),
                                name: ic?.item?.name ?? "",
                                id: ic?.item?.id ?? "",
                            });
                        }
                    } catch (e) {}
                    return {
                        name: a?.name ?? "Unknown",
                        level: Number(a?.level ?? 0),
                        xp: Number(a?.baseExperience ?? 0),
                        unlocked,
                        itemCosts: costs,
                    };
                });
                let isSmithing = false;
                try {
                    isSmithing = !!s?.isActive;
                } catch (e) {
                    isSmithing = false;
                }
                let active = null;
                try {
                    active = s?.activeRecipe?.name ?? null;
                } catch (e) {
                    active = null;
                }
                return {
                    level: Number(s?.level ?? 0),
                    active,
                    isSmithing,
                    rows,
                };
            }"""
        )

    _print_smithing_activity(data)
    print("Recipes:")
    for r in data["rows"]:
        state = "UNLOCKED" if r["unlocked"] else "LOCKED"
        costs = r.get("itemCosts") or []
        need = _format_item_costs(costs)
        print(
            f"- {r['name']}: {state} | level {int(r['level'])} | {int(r['xp'])} XP | {need}"
        )
    return True


def show_gloves() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("smithing", page=page, quiet=True):
            print("Could not navigate to Smithing.")
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
        print("Smithing Gloves: none equipped")
        return True

    name = data.get("name") or "Smithing Gloves"
    if "smithing" not in name.lower():
        print(f"Smithing Gloves: not equipped (currently: {name})")
        return True

    charges = data.get("charges")
    if isinstance(charges, (int, float)):
        print(f"Smithing Gloves: {name} | Charges: {int(charges):,}")
    else:
        print(f"Smithing Gloves: {name} | Charges: unknown")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log_observation("smithing.py", sys.argv[1:], False, "Unknown/missing command.")
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower().strip()
    if cmd == "list":
        ok, out = run_observation(show_list)
        log_observation("smithing.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    if cmd == "status":
        ok, out = run_observation(show_status)
        log_observation("smithing.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    if cmd == "gloves":
        ok, out = run_observation(show_gloves)
        log_observation("smithing.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    log_observation("smithing.py", sys.argv[1:], False, f"Unknown command: {cmd}")
    print("Unknown command. Use: list | status | gloves")
    sys.exit(1)

