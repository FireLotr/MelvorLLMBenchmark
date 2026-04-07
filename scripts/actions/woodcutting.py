#!/usr/bin/env python3
"""
woodcutting.py - Woodcutting actions.

Usage:
  python scripts/actions/woodcutting.py start "<tree>"
  python scripts/actions/woodcutting.py start "<tree1>, <tree2>"
  python scripts/actions/woodcutting.py stop

Notes:
- Auto-navigates to Woodcutting if needed.
- `start` always stops currently active tree/tree(s) first, then starts requested tree/tree(s).
- Multiple trees are comma-separated.
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


def _wc_state(page: Page) -> dict:
    return page.evaluate(
        """() => {
            const wc = game?.woodcutting;
            const lvl = Number(game?.woodcutting?.level ?? 0);
            const active = wc?.activeTrees ? Array.from(wc.activeTrees).map(t => t.name) : [];
            const limit = Number(wc?.treeCutLimit ?? 1);
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
                    unlocked,
                };
            });
            return { active, limit, trees, lvl };
        }"""
    )


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _resolve_targets(state: dict, requested: list[str]) -> tuple[bool, list[str]]:
    tree_names = [t["name"] for t in state["trees"]]
    normalized = {_norm(n): n for n in tree_names}
    resolved = []

    for raw in requested:
        key = _norm(raw)
        if not key:
            continue
        if key in normalized:
            resolved.append(normalized[key])
            continue
        partial = [n for n in tree_names if key in _norm(n)]
        if len(partial) == 1:
            resolved.append(partial[0])
            continue
        if len(partial) > 1:
            print(f"Ambiguous tree '{raw}'. Matches: {', '.join(partial)}")
            return False, []
        print(f"Unknown tree: '{raw}'")
        return False, []

    # de-duplicate while preserving order
    deduped = []
    seen = set()
    for n in resolved:
        if n not in seen:
            deduped.append(n)
            seen.add(n)
    return True, deduped


def _click_tree_card(page: Page, tree_name: str) -> bool:
    tree = page.locator("woodcutting-tree").filter(has_text=tree_name).first
    if tree.count() == 0:
        return False
    card = tree.locator("a.pointer-enabled").first
    if card.count() == 0 or not card.is_visible():
        return False
    card.click()
    page.wait_for_timeout(350)
    return True


def stop_cutting(page: Page) -> bool:
    state = _wc_state(page)
    active = state.get("active", [])
    if not active:
        print("No active woodcutting to stop.")
        return True

    for tree_name in list(active):
        if not _click_tree_card(page, tree_name):
            print(f"Could not stop '{tree_name}' (tree card not clickable).")
            return False

    after = _wc_state(page).get("active", [])
    if after:
        print(f"Could not fully stop woodcutting. Still active: {', '.join(after)}")
        return False

    print("Stopped current woodcutting.")
    return True


def start_cutting(page: Page, target_arg: str) -> bool:
    parts = [p.strip() for p in target_arg.split(",")]
    parts = [p for p in parts if p]
    if not parts:
        print("Usage: python scripts/actions/woodcutting.py start \"<tree>[, <tree2>]\"")
        return False

    state = _wc_state(page)
    ok, targets = _resolve_targets(state, parts)
    if not ok:
        return False
    if not targets:
        print("No valid trees requested.")
        return False

    limit = int(state.get("limit", 1))
    if len(targets) > limit:
        print(f"Requested {len(targets)} trees but your current limit is {limit}.")
        return False

    by_name = {t["name"]: t for t in state["trees"]}
    for t in targets:
        info = by_name.get(t)
        if info is None:
            print(f"Tree not available: {t}")
            return False
        if not info.get("unlocked", False):
            print(f"Tree '{t}' is locked (requires level {int(info.get('level', 0))}).")
            return False

    # Always stop first to avoid UI switching edge-cases.
    if not stop_cutting(page):
        return False

    started = []
    for t in targets:
        if not _click_tree_card(page, t):
            print(f"Could not start cutting '{t}' (tree card not clickable).")
            return False
        started.append(t)

    after_active = _wc_state(page).get("active", [])
    missing = [t for t in targets if t not in after_active]
    if missing:
        print(f"Tried to start: {', '.join(started)}")
        print(f"But not active after click: {', '.join(missing)}")
        return False

    print(f"Started cutting: {', '.join(targets)}")
    return True


if __name__ == "__main__":
    log_action_call("woodcutting.py", sys.argv[1:])
    if len(sys.argv) < 2:
        log_action_result("woodcutting.py", sys.argv[1:], False, details="Missing command.")
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower().strip()
    action_label = f"woodcutting_{cmd}"

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("woodcutting", page=page, quiet=True):
            log_action_result("woodcutting.py", sys.argv[1:], False, details="Navigate to Woodcutting failed.")
            print("Could not navigate to Woodcutting.")
            sys.exit(1)
        page.wait_for_timeout(200)

        if cmd == "stop":
            before = take_action_screenshot("before", action_label)
            ok = stop_cutting(page)
            after = take_action_screenshot("after", action_label)
            log_action_result("woodcutting.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        elif cmd == "start":
            if len(sys.argv) < 3:
                log_action_result("woodcutting.py", sys.argv[1:], False, details="Start missing tree name.")
                print("Usage: python scripts/actions/woodcutting.py start \"<tree>[, <tree2>]\"")
                sys.exit(1)
            arg = " ".join(sys.argv[2:]).strip()
            before = take_action_screenshot("before", f"{action_label}_{arg}")
            ok = start_cutting(page, arg)
            after = take_action_screenshot("after", f"{action_label}_{arg}")
            log_action_result("woodcutting.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        else:
            log_action_result("woodcutting.py", sys.argv[1:], False, details=f"Unknown command: {cmd}")
            print(f"Unknown command: '{cmd}'")
            print(__doc__)
            sys.exit(1)

