"""CDP session + sidebar navigation via in-page JavaScript (no Playwright locators for nav)."""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

CDP_URL = os.environ.get("MELVOR_CDP_URL", "http://localhost:9222")
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


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def connect_page(pw) -> Page:
    b = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in b.contexts:
        for p in ctx.pages:
            if "melvor" in p.url.lower():
                return p
    return b.contexts[0].pages[0]


def wait_game_ready(page: Page, *, predicate: str = "() => typeof game !== 'undefined' && !!game.bank") -> bool:
    try:
        page.wait_for_function(predicate, timeout=_READY_MS)
        return True
    except Exception:
        return False


def navigate_fast(page: Page, target: str, *, quiet: bool = False) -> bool:
    key = target.strip().lower()
    if key not in PAGES:
        print(f"Unknown page '{target}'. Use: {', '.join(sorted(PAGES))}")
        return False
    label = PAGES[key]
    if not wait_game_ready(page):
        print("Game not ready (no game.bank yet).")
        return False

    def on_target() -> bool:
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

    # One sidebar click is already done; wait for openPage in a single CDP wait (no 200ms polling loop).
    try:
        page.wait_for_function(
            f"""() => {{
                const o = String(game?.openPage?.id ?? '').toLowerCase();
                return o && o.includes('{key}');
            }}""",
            timeout=min(_VERIFY_MS, 8000),
        )
    except Exception:
        cur = page.evaluate("() => String(game?.openPage?.id ?? '')")
        print(f"Timeout: expected page containing '{key}', got id {cur!r}")
        return False

    if not quiet:
        print(f"Navigated to: {label}")
    return True


def with_page(fn, *, game_ready: str = "() => typeof game !== 'undefined' && !!game.bank"):
    """Run ``fn(page)`` inside one sync_playwright + CDP session."""

    def runner():
        with sync_playwright() as pw:
            page = connect_page(pw)
            if not page.evaluate("() => typeof game !== 'undefined'"):
                print("Melvor page found but `game` is not defined yet.")
                return fn(page)
            try:
                page.wait_for_function(game_ready, timeout=_READY_MS)
            except Exception:
                print("Game not ready within timeout.")
            return fn(page)

    return runner()
