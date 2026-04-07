#!/usr/bin/env python3
"""
fishing.py - Fishing actions.

Usage:
  python scripts/actions/fishing.py start "<fish name>"
  python scripts/actions/fishing.py stop

Notes:
- Auto-navigates to Fishing if needed.
- `start` selects the fish and clicks Start Fishing; the game overrides any current fishing (no need to stop first).
- Handles collapsed area cards by expanding the target area if needed.
- `stop` looks for a Stop Fishing control (game `activeFishingArea` alone is not reliable — it can stay set when idle).
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


def _resolve_fish(page: Page, query: str):
    data = page.evaluate(
        """() => {
            const f = game?.fishing;
            return (f?.areas?.allObjects ?? []).flatMap(area =>
                (area?.fish ?? []).map(fish => {
                    let unlocked = false;
                    try { unlocked = !!f?.isMasteryActionUnlocked?.(fish); } catch (e) {}
                    return {
                        fishName: fish?.name ?? "Unknown Fish",
                        areaName: area?.name ?? "Unknown Area",
                        level: Number(fish?.level ?? 0),
                        unlocked,
                    };
                })
            );
        }"""
    )
    q = _norm(query)
    exact = [r for r in data if _norm(r["fishName"]) == q]
    if exact:
        return exact[0], None
    partial = [r for r in data if q and q in _norm(r["fishName"])]
    if len(partial) == 1:
        return partial[0], None
    if len(partial) > 1:
        return None, f"Ambiguous fish '{query}'. Matches: {', '.join(r['fishName'] for r in partial)}"
    return None, f"Unknown fish: '{query}'"


def _fishing_active_area_name(page: Page) -> str | None:
    try:
        name = page.evaluate("() => game?.fishing?.activeFishingArea?.name ?? null")
        return str(name).strip() if name else None
    except Exception:
        return None


def _click_stop_fishing_if_visible(page: Page) -> bool:
    """Click visible Stop Fishing; return True if click attempted and button disappeared."""
    stop_btn = page.locator("fishing-area-menu button").filter(has_text="Stop Fishing").first
    if stop_btn.count() == 0 or not stop_btn.is_visible():
        return False
    stop_btn.click()
    page.wait_for_timeout(350)
    again = page.locator("fishing-area-menu button").filter(has_text="Stop Fishing").first
    if again.count() > 0 and again.is_visible():
        print("Could not stop fishing.")
        return False
    print("Stopped fishing.")
    return True


def _expand_fishing_area_menu(page: Page, area_menu) -> None:
    """Open a collapsed fishing area card so inner controls (e.g. Stop Fishing) can show."""
    for sel in (".block-header", ".block-title", ".block.pointer-enabled", ".block"):
        header = area_menu.locator(sel).first
        if header.count() > 0 and header.is_visible():
            header.click()
            page.wait_for_timeout(400)
            return


def stop_fishing(page: Page) -> bool:
    if _click_stop_fishing_if_visible(page):
        return True

    # `activeFishingArea` often stays set as the last selected area even when not fishing.
    # Only treat fishing as active if the UI actually exposes Stop Fishing somewhere.
    stop_loc = page.locator("fishing-area-menu button").filter(has_text="Stop Fishing")
    if stop_loc.count() == 0:
        print("No active fishing to stop.")
        return True

    active = _fishing_active_area_name(page)

    # Collapsed area: Stop Fishing is in the DOM but hidden until the card is expanded.
    if active:
        area = page.locator("fishing-area-menu").filter(has_text=active).first
        if area.count() > 0:
            _expand_fishing_area_menu(page, area)
            if _click_stop_fishing_if_visible(page):
                return True

    menus = page.locator("fishing-area-menu")
    for i in range(min(menus.count(), 24)):
        men = menus.nth(i)
        if men.locator("button").filter(has_text="Stop Fishing").count() == 0:
            continue
        stop_here = men.locator("button").filter(has_text="Stop Fishing").first
        if stop_here.count() == 0 or not stop_here.is_visible():
            _expand_fishing_area_menu(page, men)
        if _click_stop_fishing_if_visible(page):
            return True

    print("Stop Fishing is on the page but could not be clicked (try expanding the area on screen).")
    return False


def _select_fish_in_area(page: Page, area_name: str, fish_name: str) -> bool:
    area = page.locator("fishing-area-menu").filter(has_text=area_name).first
    if area.count() == 0:
        print(f"Could not find area card: {area_name}")
        return False

    fish_link = area.locator("a").filter(has_text=fish_name).first
    if fish_link.count() == 0 or not fish_link.is_visible():
        # Area may be collapsed; click its header/title block first.
        header = area.locator(".block-header, .block-title, .block").first
        if header.count() > 0 and header.is_visible():
            header.click()
            page.wait_for_timeout(350)
        fish_link = area.locator("a").filter(has_text=fish_name).first

    if fish_link.count() == 0 or not fish_link.is_visible():
        print(f"Could not select fish '{fish_name}' in area '{area_name}' (area may be collapsed/hidden).")
        return False

    fish_link.click()
    page.wait_for_timeout(250)
    return True


def start_fishing(page: Page, fish_query: str) -> bool:
    target, err = _resolve_fish(page, fish_query)
    if err:
        print(err)
        return False
    if not target["unlocked"]:
        print(f"Fish '{target['fishName']}' is locked (requires level {int(target['level'])}).")
        return False

    if not _select_fish_in_area(page, target["areaName"], target["fishName"]):
        return False

    area = page.locator("fishing-area-menu").filter(has_text=target["areaName"]).first
    start_btn = area.locator("button").filter(has_text="Start Fishing").first
    if start_btn.count() == 0 or not start_btn.is_visible():
        print(f"Start Fishing button not visible for area '{target['areaName']}'.")
        return False
    start_btn.click()
    page.wait_for_timeout(350)

    active = _fishing_active_area_name(page)
    if active != target["areaName"]:
        print(f"Tried to start '{target['fishName']}' in '{target['areaName']}', but active area is '{active}'.")
        return False

    print(f"Started fishing: {target['fishName']} ({target['areaName']})")
    return True


if __name__ == "__main__":
    log_action_call("fishing.py", sys.argv[1:])
    if len(sys.argv) < 2:
        log_action_result("fishing.py", sys.argv[1:], False, details="Missing command.")
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower().strip()
    action_label = f"fishing_{cmd}"
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("fishing", page=page, quiet=True):
            log_action_result("fishing.py", sys.argv[1:], False, details="Navigate to Fishing failed.")
            print("Could not navigate to Fishing.")
            sys.exit(1)
        page.wait_for_timeout(200)

        if cmd == "stop":
            before = take_action_screenshot("before", action_label)
            ok = stop_fishing(page)
            after = take_action_screenshot("after", action_label)
            log_action_result("fishing.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        if cmd == "start":
            if len(sys.argv) < 3:
                log_action_result("fishing.py", sys.argv[1:], False, details="Start missing fish name.")
                print("Usage: python scripts/actions/fishing.py start \"<fish name>\"")
                sys.exit(1)
            query = " ".join(sys.argv[2:]).strip()
            before = take_action_screenshot("before", f"{action_label}_{query}")
            ok = start_fishing(page, query)
            after = take_action_screenshot("after", f"{action_label}_{query}")
            log_action_result("fishing.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)

        log_action_result("fishing.py", sys.argv[1:], False, details=f"Unknown command: {cmd}")
        print(f"Unknown command: '{cmd}'")
        print(__doc__)
        sys.exit(1)

