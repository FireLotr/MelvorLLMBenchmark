#!/usr/bin/env python3
"""
firemaking.py - Firemaking actions.

Usage:
  python scripts/actions/firemaking.py select "<log name>"
      Only sets the log in the dropdown (selected recipe). Does not burn logs or light a bonfire.

  python scripts/actions/firemaking.py start "<log name>"
      Selects the log and starts burning it (clicks Burn).

  python scripts/actions/firemaking.py stop
      Stops burning logs (clicks Burn while active). Does not affect the bonfire.

  python scripts/actions/firemaking.py bonfire start ["<log name>"]
      Lights the skill bonfire using the selected log type. If a log name is given, selects it
      first (same as `select`) then lights the bonfire — you can still burn a different log afterward.

  python scripts/actions/firemaking.py bonfire stop
      Stops the skill bonfire (exits the bonfire bonus). Does not stop log burning.
"""

import os
import re
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


def _bonfire_is_lit(page: Page) -> bool:
    return page.evaluate(
        """() => {
            const bt = game?.firemaking?.bonfireTimer;
            if (bt && typeof bt === "object" && typeof bt.active === "boolean") {
                if (!bt.active) return false;
                const ticks = Number(bt._ticksLeft);
                if (Number.isFinite(ticks) && ticks <= 0) return false;
                return true;
            }
            return false;
        }"""
    )


# Melvor mounts bonfire controls here (avoids scanning hundreds of page buttons).
_BONFIRE_MENU = "#firemaking-bonfire-menu"


def _bonfire_light_locator(page: Page):
    root = page.locator(_BONFIRE_MENU)
    primary = root.locator("button.btn-primary").filter(has_text=re.compile(r"Light|Ignite", re.I))
    if primary.count() > 0:
        return primary.first
    return root.locator("button").filter(
        has_text=re.compile(r"(Light|Ignite).{0,60}Bonfire|Bonfire.{0,20}(Light|Ignite)", re.I)
    ).first


def _bonfire_stop_locator(page: Page):
    root = page.locator(_BONFIRE_MENU)
    danger = root.locator("button.btn-danger").filter(has_text=re.compile(r"Stop|Extinguish", re.I))
    if danger.count() > 0:
        return danger.first
    return root.locator("button").filter(has_text=re.compile(r"(Stop|Extinguish).{0,40}Bonfire", re.I)).first


def _select_log(page: Page, query: str) -> tuple[bool, str]:
    rows = page.evaluate(
        """() => {
            const f = game?.firemaking;
            return (f?.actions?.allObjects ?? []).map(a => ({
                name: a?.name ?? "Unknown",
                level: Number(a?.level ?? 0),
                unlocked: !!(f?.isMasteryActionUnlocked?.(a)),
            }));
        }"""
    )
    q = _norm(query)
    exact = [r for r in rows if _norm(r["name"]) == q]
    target = exact[0] if exact else None
    if target is None:
        partial = [r for r in rows if q and q in _norm(r["name"])]
        if len(partial) == 1:
            target = partial[0]
        elif len(partial) > 1:
            print(f"Ambiguous log '{query}'. Matches: {', '.join(r['name'] for r in partial)}")
            return False, ""
        else:
            print(f"Unknown log: '{query}'")
            return False, ""

    if not target["unlocked"]:
        print(f"Log '{target['name']}' is locked (requires level {int(target['level'])}).")
        return False, ""

    toggle = page.locator("button.dropdown-toggle").filter(has_text="Select your logs").first
    if toggle.count() == 0 or not toggle.is_visible():
        print("Could not find log selector dropdown.")
        return False, ""
    toggle.click()
    page.wait_for_timeout(250)

    options = page.locator(".dropdown-menu.show .dropdown-item, .dropdown-menu.show button")
    picked = None
    for i in range(options.count()):
        opt = options.nth(i)
        if _norm(target["name"]) in _norm(opt.text_content() or "") and opt.is_visible():
            picked = opt
            break
    if picked is None:
        page.keyboard.press("Escape")
        print(f"Could not find log option for '{target['name']}'.")
        return False, ""
    picked.click()
    page.wait_for_timeout(250)
    return True, target["name"]


def select_log_only(page: Page, log_name: str) -> bool:
    ok, selected = _select_log(page, log_name)
    if not ok:
        return False
    print(f"Selected log (dropdown only): {selected}")
    return True


def stop_burning(page: Page) -> bool:
    burn_btn = page.locator("button").filter(has_text="Burn").first
    if burn_btn.count() == 0 or not burn_btn.is_visible():
        print("Could not find Burn button.")
        return False
    is_active = page.evaluate("() => !!game?.firemaking?.isActive")
    if not is_active:
        print("Not burning logs (nothing to stop).")
        return True
    burn_btn.click()
    page.wait_for_timeout(350)
    if page.evaluate("() => !!game?.firemaking?.isActive"):
        print("Could not stop burning logs.")
        return False
    print("Stopped burning logs.")
    return True


def start_burning(page: Page, log_name: str) -> bool:
    ok, selected = _select_log(page, log_name)
    if not ok:
        return False
    burn_btn = page.locator("button").filter(has_text="Burn").first
    if burn_btn.count() == 0 or not burn_btn.is_visible():
        print("Could not find Burn button.")
        return False
    if page.evaluate("() => !!game?.firemaking?.isActive"):
        burn_btn.click()
        page.wait_for_timeout(300)
    burn_btn.click()
    page.wait_for_timeout(350)
    if not page.evaluate("() => !!game?.firemaking?.isActive"):
        print(f"Tried to start burning '{selected}', but firemaking did not start.")
        return False
    print(f"Started burning logs: {selected}")
    return True


def bonfire_start(page: Page, log_name: str | None) -> bool:
    if log_name and log_name.strip():
        ok, selected = _select_log(page, log_name.strip())
        if not ok:
            return False
    if _bonfire_is_lit(page):
        print("Bonfire already lit.")
        return True
    if page.locator(_BONFIRE_MENU).count() == 0:
        print("Could not find bonfire panel (#firemaking-bonfire-menu). Is Firemaking open?")
        return False
    btn = _bonfire_light_locator(page)
    if btn.count() == 0 or not btn.is_visible():
        print("Could not find Light/Ignite Bonfire button.")
        return False
    try:
        if btn.is_disabled():
            print("Light Bonfire control is disabled (check logs/costs).")
            return False
    except Exception:
        pass
    btn.click()
    page.wait_for_timeout(300)
    if not _bonfire_is_lit(page):
        print("Clicked light bonfire, but bonfire does not appear lit.")
        return False
    print("Started bonfire.")
    return True


def bonfire_stop(page: Page) -> bool:
    if not _bonfire_is_lit(page):
        print("Bonfire not lit (nothing to stop).")
        return True
    if page.locator(_BONFIRE_MENU).count() == 0:
        print("Could not find bonfire panel (#firemaking-bonfire-menu). Is Firemaking open?")
        return False
    btn = _bonfire_stop_locator(page)
    if btn.count() == 0 or not btn.is_visible():
        print("Could not find Stop Bonfire button.")
        return False
    btn.click()
    page.wait_for_timeout(300)
    if _bonfire_is_lit(page):
        print("Could not stop bonfire.")
        return False
    print("Stopped bonfire.")
    return True


if __name__ == "__main__":
    log_action_call("firemaking.py", sys.argv[1:])
    if len(sys.argv) < 2:
        log_action_result("firemaking.py", sys.argv[1:], False, details="Missing command.")
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1].lower().strip()

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("firemaking", page=page, quiet=True):
            log_action_result("firemaking.py", sys.argv[1:], False, details="Navigate to Firemaking failed.")
            print("Could not navigate to Firemaking.")
            sys.exit(1)
        page.wait_for_timeout(200)

        if cmd == "bonfire":
            if len(sys.argv) < 3:
                log_action_result("firemaking.py", sys.argv[1:], False, details="bonfire missing subcommand.")
                print("Usage: python scripts/actions/firemaking.py bonfire start [\"<log name>\"] | bonfire stop")
                sys.exit(1)
            sub = sys.argv[2].lower().strip()
            if sub == "start":
                rest = " ".join(sys.argv[3:]).strip()
                log_arg = rest if rest else None
                label = f"firemaking_bonfire_start_{log_arg}" if log_arg else "firemaking_bonfire_start"
                before = take_action_screenshot("before", label)
                ok = bonfire_start(page, log_arg)
                after = take_action_screenshot("after", label)
                log_action_result("firemaking.py", sys.argv[1:], ok, before, after)
                sys.exit(0 if ok else 1)
            if sub == "stop":
                before = take_action_screenshot("before", "firemaking_bonfire_stop")
                ok = bonfire_stop(page)
                after = take_action_screenshot("after", "firemaking_bonfire_stop")
                log_action_result("firemaking.py", sys.argv[1:], ok, before, after)
                sys.exit(0 if ok else 1)
            log_action_result("firemaking.py", sys.argv[1:], False, details=f"Unknown bonfire subcommand: {sub}")
            print(f"Unknown bonfire subcommand: '{sub}' (use start or stop).")
            sys.exit(1)

        action_label = f"firemaking_{cmd}"
        if cmd == "stop":
            before = take_action_screenshot("before", action_label)
            ok = stop_burning(page)
            after = take_action_screenshot("after", action_label)
            log_action_result("firemaking.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        if cmd == "select":
            if len(sys.argv) < 3:
                log_action_result("firemaking.py", sys.argv[1:], False, details="select missing log name.")
                print('Usage: python scripts/actions/firemaking.py select "<log name>"')
                sys.exit(1)
            log_name = " ".join(sys.argv[2:]).strip()
            before = take_action_screenshot("before", f"{action_label}_{log_name}")
            ok = select_log_only(page, log_name)
            after = take_action_screenshot("after", f"{action_label}_{log_name}")
            log_action_result("firemaking.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        if cmd == "start":
            if len(sys.argv) < 3:
                log_action_result("firemaking.py", sys.argv[1:], False, details="start missing log name.")
                print('Usage: python scripts/actions/firemaking.py start "<log name>"')
                sys.exit(1)
            log_name = " ".join(sys.argv[2:]).strip()
            before = take_action_screenshot("before", f"{action_label}_{log_name}")
            ok = start_burning(page, log_name)
            after = take_action_screenshot("after", f"{action_label}_{log_name}")
            log_action_result("firemaking.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)

        log_action_result("firemaking.py", sys.argv[1:], False, details=f"Unknown command: {cmd}")
        print(f"Unknown command: '{cmd}'")
        print(__doc__)
        sys.exit(1)
