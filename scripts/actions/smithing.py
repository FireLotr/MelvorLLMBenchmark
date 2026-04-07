#!/usr/bin/env python3
"""
smithing.py - Smithing actions.

Usage:
  python scripts/actions/smithing.py start "<recipe name>"
  python scripts/actions/smithing.py stop
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


def _first_visible(locator):
    for i in range(locator.count()):
        item = locator.nth(i)
        if item.is_visible():
            return item
    return None


def stop(page: Page) -> bool:
    if not page.evaluate("() => !!game?.smithing?.isActive"):
        print("No active smithing to stop.")
        return True
    create_btn = _first_visible(page.locator("button").filter(has_text="Create"))
    if create_btn is None:
        print("Could not find Create button to stop smithing.")
        return False
    create_btn.click()
    page.wait_for_timeout(300)
    if page.evaluate("() => !!game?.smithing?.isActive"):
        print("Could not stop smithing.")
        return False
    print("Stopped smithing.")
    return True


def start(page: Page, recipe_query: str) -> bool:
    rows = page.evaluate(
        """() => {
            const s = game?.smithing;
            return (s?.actions?.allObjects ?? []).map(a => ({
                name: a?.name ?? "Unknown",
                level: Number(a?.level ?? 0),
                unlocked: !!(s?.isMasteryActionUnlocked?.(a)),
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

    # Ensure category list is open/visible.
    cat_btn = page.locator("button").filter(has_text="Select Smithing Category").first
    if cat_btn.count() > 0 and cat_btn.is_visible():
        cat_btn.click()
        page.wait_for_timeout(250)

    # Iterate categories until target recipe becomes visible.
    recipe_link = page.locator("a.block").filter(has_text=target["name"]).first
    cat_links = page.locator("#smithing-category-menu a")
    for i in range(cat_links.count()):
        if recipe_link.count() > 0 and recipe_link.is_visible():
            break
        link = cat_links.nth(i)
        if not link.is_visible():
            continue
        link.click()
        page.wait_for_timeout(250)

    if recipe_link.count() == 0 or not recipe_link.is_visible():
        print(f"Recipe '{target['name']}' is not visible in the current smithing list.")
        return False
    recipe_link.click()
    page.wait_for_timeout(250)

    if not stop(page):
        return False
    create_btn = _first_visible(page.locator("button").filter(has_text="Create"))
    if create_btn is None:
        print("Could not find Create button.")
        return False
    create_btn.click()
    page.wait_for_timeout(350)
    if not page.evaluate("() => !!game?.smithing?.isActive"):
        print(
            f"Tried to start '{target['name']}', but smithing did not start "
            "(likely missing materials or other requirements)."
        )
        return False
    print(f"Started smithing: {target['name']}")
    return True


if __name__ == "__main__":
    log_action_call("smithing.py", sys.argv[1:])
    if len(sys.argv) < 2:
        log_action_result("smithing.py", sys.argv[1:], False, details="Missing command.")
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower().strip()
    action_label = f"smithing_{cmd}"
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("smithing", page=page, quiet=True):
            log_action_result("smithing.py", sys.argv[1:], False, details="Navigate to Smithing failed.")
            print("Could not navigate to Smithing.")
            sys.exit(1)
        page.wait_for_timeout(200)
        if cmd == "stop":
            before = take_action_screenshot("before", action_label)
            ok = stop(page)
            after = take_action_screenshot("after", action_label)
            log_action_result("smithing.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        elif cmd == "start":
            if len(sys.argv) < 3:
                log_action_result("smithing.py", sys.argv[1:], False, details="Start missing recipe name.")
                print("Usage: python scripts/actions/smithing.py start \"<recipe name>\"")
                sys.exit(1)
            recipe = " ".join(sys.argv[2:]).strip()
            before = take_action_screenshot("before", f"{action_label}_{recipe}")
            ok = start(page, recipe)
            after = take_action_screenshot("after", f"{action_label}_{recipe}")
            log_action_result("smithing.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        else:
            log_action_result("smithing.py", sys.argv[1:], False, details=f"Unknown command: {cmd}")
            print(f"Unknown command: '{cmd}'")
            print(__doc__)
            sys.exit(1)

