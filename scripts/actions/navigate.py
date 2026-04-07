#!/usr/bin/env python3
"""
navigate.py — Change the active game page via `sidebar.category(...).item(...).click()`.

Intended for desktop layout (sidebar always visible). No hamburger / overlay handling.

Other action scripts may call navigate(..., page=existing_page, quiet=True) to avoid nesting
sync_playwright() or printing navigation messages.

Usage:
  python scripts/actions/navigate.py bank
  python scripts/actions/navigate.py woodcutting
  (see PAGES keys below)
"""

import os
import sys

os.environ.setdefault("NODE_NO_WARNINGS", "1")
from playwright.sync_api import Page, sync_playwright

from _action_logging import log_action_call, log_action_result
from _action_screenshots import take_action_screenshot

CDP_URL = "http://localhost:9222"
_READY_MS = int(os.environ.get("NAVIGATE_GAME_READY_MS", "20000"))
_VERIFY_MS = int(os.environ.get("NAVIGATE_VERIFY_MS", "8000"))

PAGES = {
    "attack": "Attack",
    "strength": "Strength",
    "defence": "Defence",
    "hitpoints": "Hitpoints",
    "farming": "Farming",
    "woodcutting": "Woodcutting",
    "fishing": "Fishing",
    "firemaking": "Firemaking",
    "cooking": "Cooking",
    "mining": "Mining",
    "smithing": "Smithing",
    "bank": "Bank",
    "shop": "Shop",
    "combat": "Combat",
}

_NAV_JS = r"""
(targetKey) => {
  const out = { ok: false, error: "", tried: [] };
  if (typeof sidebar === "undefined" || !sidebar || typeof sidebar.category !== "function") {
    out.error = "sidebar API missing";
    return out;
  }
  const tryFns = (label, fns) => {
    for (const fn of fns) {
      try {
        fn();
        out.ok = true;
        out.tried.push(label);
        return true;
      } catch (e) {
        out.tried.push(label + ": " + (e && e.message ? e.message : String(e)));
      }
    }
    return false;
  };
  const k = String(targetKey || "").toLowerCase();
  const combat = (id) => () => sidebar.category("Combat").item(id).click();
  const nonCombat = (id) => () => {
    try { sidebar.category("Non-Combat").toggle(true); } catch (e) {}
    sidebar.category("Non-Combat").item(id).click();
  };

  if (k === "attack") tryFns("a", [combat("melvorD:Attack")]);
  else if (k === "strength") tryFns("s", [combat("melvorD:Strength")]);
  else if (k === "defence") tryFns("d", [combat("melvorD:Defence")]);
  else if (k === "hitpoints") tryFns("h", [combat("melvorD:Hitpoints")]);
  else if (k === "farming") tryFns("f", [
    () => { try { sidebar.category("Passive").toggle(true); } catch (e) {} sidebar.category("Passive").item("melvorD:Farming").click(); },
    nonCombat("melvorD:Farming"),
  ]);
  else if (k === "woodcutting") tryFns("w", [nonCombat("melvorD:Woodcutting")]);
  else if (k === "fishing") tryFns("fi", [nonCombat("melvorD:Fishing")]);
  else if (k === "firemaking") tryFns("fm", [nonCombat("melvorD:Firemaking")]);
  else if (k === "cooking") tryFns("c", [nonCombat("melvorD:Cooking")]);
  else if (k === "mining") tryFns("m", [nonCombat("melvorD:Mining")]);
  else if (k === "smithing") tryFns("sm", [nonCombat("melvorD:Smithing")]);
  else if (k === "bank") tryFns("b", [
    () => sidebar.category("").item("melvorD:Bank").click(),
    () => sidebar.category("General").item("melvorD:Bank").click(),
  ]);
  else if (k === "shop") tryFns("sh", [
    () => sidebar.category("").item("melvorD:Shop").click(),
    () => sidebar.category("General").item("melvorD:Shop").click(),
  ]);
  else if (k === "combat") tryFns("co", [
    () => sidebar.category("Combat").item("melvorD:Combat").click(),
    () => sidebar.category("General").item("melvorD:Combat").click(),
  ]);
  else {
    out.error = "unknown: " + k;
    return out;
  }
  if (!out.ok) out.error = out.tried[out.tried.length - 1] || "failed";
  return out;
}
"""


def _page(pw):
    b = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in b.contexts:
        for p in ctx.pages:
            if "melvor" in p.url.lower():
                return p
    return b.contexts[0].pages[0]


def _navigate_on_page(page: Page, key: str, *, quiet: bool = False) -> bool:
    """Sidebar navigation using an existing CDP page (no nested sync_playwright)."""
    label = PAGES[key]
    try:
        page.wait_for_function(
            "() => typeof game !== 'undefined' && !!game.bank",
            timeout=_READY_MS,
        )
    except Exception:
        print("Game not ready (no game.bank yet).")
        return False

    def on_target():
        try:
            oid = page.evaluate("() => String(game?.openPage?.id ?? '').toLowerCase()")
        except Exception:
            return False
        return bool(oid) and key in oid

    if on_target():
        if not quiet:
            print(f"Navigated to: {label}")
        return True

    r = page.evaluate(_NAV_JS, key)
    if not isinstance(r, dict) or not r.get("ok"):
        print("Navigate failed:", (r or {}).get("error", r))
        return False

    for _ in range(max(1, _VERIFY_MS // 200)):
        if on_target():
            if not quiet:
                print(f"Navigated to: {label}")
            return True
        page.wait_for_timeout(200)

    cur = page.evaluate("() => String(game?.openPage?.id ?? '')")
    print(f"Timeout: expected page containing '{key}', got id {cur!r}")
    return False


def navigate(
    target: str,
    *,
    page: Page | None = None,
    quiet: bool = False,
) -> bool:
    key = target.strip().lower()
    if key not in PAGES:
        print(f"Unknown page '{target}'. Use: {', '.join(sorted(PAGES))}")
        return False

    if page is not None:
        return _navigate_on_page(page, key, quiet=quiet)

    with sync_playwright() as pw:
        return _navigate_on_page(_page(pw), key, quiet=quiet)


if __name__ == "__main__":
    log_action_call("navigate.py", sys.argv[1:])
    if len(sys.argv) < 2:
        log_action_result("navigate.py", sys.argv[1:], False, details="missing arg")
        print(__doc__)
        sys.exit(1)
    tag = f"navigate_{sys.argv[1]}"
    before = take_action_screenshot("before", tag)
    ok = navigate(sys.argv[1])
    after = take_action_screenshot("after", tag)
    log_action_result("navigate.py", sys.argv[1:], ok, before, after)
    sys.exit(0 if ok else 1)
