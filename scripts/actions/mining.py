#!/usr/bin/env python3
"""
mining.py - Mining actions.

Usage:
  python scripts/actions/mining.py start "<rock name>"
  python scripts/actions/mining.py stop
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
    active = page.evaluate(
        """() => {
            try { return game?.mining?.activeRock?.name ?? null; }
            catch (e) { return null; }
        }"""
    )
    if not active:
        print("No active mining to stop.")
        return True
    card = page.locator("a.block").filter(has_text=active).first
    if card.count() == 0 or not card.is_visible():
        print(f"Could not find active rock card '{active}' to stop.")
        return False
    card.click()
    page.wait_for_timeout(350)
    active_after = page.evaluate(
        """() => {
            try { return game?.mining?.activeRock?.name ?? null; }
            catch (e) { return null; }
        }"""
    )
    if active_after:
        print(f"Could not stop mining; still active: {active_after}")
        return False
    print("Stopped mining.")
    return True


def start(page: Page, rock_query: str) -> bool:
    rows = page.evaluate(
        """() => {
            const m = game?.mining;
            const lvl = Number(m?.level ?? 0);
            return (m?.actions?.allObjects ?? []).map(a => ({
                name: a?.name ?? "Unknown",
                level: Number(a?.level ?? 0),
                unlocked: lvl >= Number(a?.level ?? 0),
            }));
        }"""
    )
    q = _norm(rock_query)
    exact = [r for r in rows if _norm(r["name"]) == q]
    target = exact[0] if exact else None
    if target is None:
        partial = [r for r in rows if q and q in _norm(r["name"])]
        if len(partial) == 1:
            target = partial[0]
        elif len(partial) > 1:
            print(f"Ambiguous rock '{rock_query}'. Matches: {', '.join(r['name'] for r in partial)}")
            return False
        else:
            print(f"Unknown rock: '{rock_query}'")
            return False

    if not target["unlocked"]:
        print(f"Rock '{target['name']}' is locked (requires level {int(target['level'])}).")
        return False

    if not stop(page):
        return False

    card = page.locator("a.block").filter(has_text=target["name"]).first
    if card.count() == 0 or not card.is_visible():
        print(f"Could not find rock card '{target['name']}'.")
        return False
    card.click()
    page.wait_for_timeout(350)
    active = page.evaluate(
        """() => {
            try { return game?.mining?.activeRock?.name ?? null; }
            catch (e) { return null; }
        }"""
    )
    if active != target["name"]:
        print(f"Tried to start '{target['name']}', but active rock is '{active}'.")
        return False
    print(f"Started mining: {target['name']}")
    return True


if __name__ == "__main__":
    log_action_call("mining.py", sys.argv[1:])
    if len(sys.argv) < 2:
        log_action_result("mining.py", sys.argv[1:], False, details="Missing command.")
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower().strip()
    action_label = f"mining_{cmd}"
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("mining", page=page, quiet=True):
            log_action_result("mining.py", sys.argv[1:], False, details="Navigate to Mining failed.")
            print("Could not navigate to Mining.")
            sys.exit(1)
        page.wait_for_timeout(200)
        if cmd == "stop":
            before = take_action_screenshot("before", action_label)
            ok = stop(page)
            after = take_action_screenshot("after", action_label)
            log_action_result("mining.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        elif cmd == "start":
            if len(sys.argv) < 3:
                log_action_result("mining.py", sys.argv[1:], False, details="Start missing rock name.")
                print("Usage: python scripts/actions/mining.py start \"<rock name>\"")
                sys.exit(1)
            rock = " ".join(sys.argv[2:]).strip()
            before = take_action_screenshot("before", f"{action_label}_{rock}")
            ok = start(page, rock)
            after = take_action_screenshot("after", f"{action_label}_{rock}")
            log_action_result("mining.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        else:
            log_action_result("mining.py", sys.argv[1:], False, details=f"Unknown command: {cmd}")
            print(f"Unknown command: '{cmd}'")
            print(__doc__)
            sys.exit(1)

