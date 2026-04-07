#!/usr/bin/env python3
"""
cooking.py - Cooking actions.

Usage:
  python scripts/actions/cooking.py start "<recipe name>"
  python scripts/actions/cooking.py stop
"""

import os
import sys
from playwright.sync_api import sync_playwright, Page
from _action_screenshots import take_action_screenshot
from _action_logging import log_action_call, log_action_result
from navigate import navigate

os.environ.setdefault("NODE_NO_WARNINGS", "1")
CDP_URL = "http://localhost:9222"


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "melvor" in pg.url.lower():
                return pg
    return browser.contexts[0].pages[0]


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def stop(page: Page) -> bool:
    if not page.evaluate("() => !!game?.cooking?.isActive"):
        print("No active cooking to stop.")
        return True
    # Active Cook button toggles active cooking.
    btn = page.locator("#cooking-menu-container button.btn-success").first
    if btn.count() == 0 or not btn.is_visible():
        print("Could not find Active Cook button.")
        return False
    btn.click()
    page.wait_for_timeout(350)
    if page.evaluate("() => !!game?.cooking?.isActive"):
        print("Could not stop cooking.")
        return False
    print("Stopped cooking.")
    return True


def start(page: Page, recipe_query: str) -> bool:
    # Resolve recipe + unlock via game state.
    rows = page.evaluate(
        """() => {
            const c = game?.cooking;
            return (c?.actions?.allObjects ?? []).map(a => ({
                name: a?.name ?? "Unknown",
                unlocked: !!(c?.isMasteryActionUnlocked?.(a)),
                level: Number(a?.level ?? 0),
            }));
        }"""
    )
    q = _norm(recipe_query)
    exact = [r for r in rows if _norm(r["name"]) == q]
    target = exact[0] if exact else None
    if target is None:
        partial = [r for r in rows if q and q in _norm(r["name"])]
        if len(partial) == 1:
            target = partial[0]
        elif len(partial) > 1:
            print(f"Ambiguous recipe '{recipe_query}'. Matches: {', '.join(r['name'] for r in partial[:20])}")
            return False
        else:
            print(f"Unknown recipe: '{recipe_query}'")
            return False
    if not target["unlocked"]:
        print(f"Recipe '{target['name']}' is locked (requires level {int(target['level'])}).")
        return False

    # Select the recipe via game API (avoids UI modal and any dialogs).
    selected = page.evaluate(
        """(recipeName) => {
            const c = game?.cooking;
            if (!c) return { ok: false, error: 'game.cooking not found' };
            const recipe = (c.actions?.allObjects ?? []).find(a => a.name === recipeName);
            if (!recipe) return { ok: false, error: 'recipe not found: ' + recipeName };
            if (!c.isMasteryActionUnlocked?.(recipe)) return { ok: false, error: 'recipe locked' };
            try {
                c.onRecipeSelectionClick(recipe);
                return { ok: true, category: recipe.category?.id ?? null };
            } catch(e) {
                return { ok: false, error: String(e) };
            }
        }""",
        target["name"]
    )
    if not selected.get("ok"):
        print(f"Could not select recipe '{target['name']}': {selected.get('error')}")
        return False
    page.wait_for_timeout(300)

    # Find the station block for this recipe's category.
    category_id = selected.get("category") or ""
    stations = page.locator("#cooking-menu-container .block")
    station_idx = None
    for i in range(stations.count()):
        st = stations.nth(i)
        active_cook = st.locator("button.btn-success").filter(has_text="Active Cook").first
        if active_cook.count() > 0 and active_cook.is_visible():
            station_idx = i
            break

    if station_idx is None:
        print(f"Could not find Active Cook button for recipe '{target['name']}' (category: {category_id}).")
        return False

    if not stop(page):
        return False

    # Start active cook on the selected station.
    st = stations.nth(station_idx)
    start_btn = st.locator("button.btn-success").filter(has_text="Active Cook").first
    if start_btn.count() == 0 or not start_btn.is_visible():
        print("Could not find Active Cook button on selected station.")
        return False
    start_btn.click()
    page.wait_for_timeout(350)
    if not page.evaluate("() => !!game?.cooking?.isActive"):
        print(f"Tried to start cooking '{target['name']}', but cooking did not start.")
        return False
    print(f"Started cooking: {target['name']}")
    return True


if __name__ == "__main__":
    log_action_call("cooking.py", sys.argv[1:])
    if len(sys.argv) < 2:
        log_action_result("cooking.py", sys.argv[1:], False, details="Missing command.")
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower().strip()
    action_label = f"cooking_{cmd}"
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("cooking", page=page, quiet=True):
            log_action_result("cooking.py", sys.argv[1:], False, details="Navigate to Cooking failed.")
            print("Could not navigate to Cooking.")
            sys.exit(1)
        page.wait_for_timeout(200)
        if cmd == "stop":
            before = take_action_screenshot("before", action_label)
            ok = stop(page)
            after = take_action_screenshot("after", action_label)
            log_action_result("cooking.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        elif cmd == "start":
            if len(sys.argv) < 3:
                log_action_result("cooking.py", sys.argv[1:], False, details="Start missing recipe name.")
                print("Usage: python scripts/actions/cooking.py start \"<recipe name>\"")
                sys.exit(1)
            recipe = " ".join(sys.argv[2:]).strip()
            before = take_action_screenshot("before", f"{action_label}_{recipe}")
            ok = start(page, recipe)
            after = take_action_screenshot("after", f"{action_label}_{recipe}")
            log_action_result("cooking.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        else:
            log_action_result("cooking.py", sys.argv[1:], False, details=f"Unknown command: {cmd}")
            print(f"Unknown command: '{cmd}'")
            print(__doc__)
            sys.exit(1)

