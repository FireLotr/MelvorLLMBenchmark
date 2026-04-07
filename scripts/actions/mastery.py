#!/usr/bin/env python3
"""
actions/mastery.py - Spend mastery pool on a specific action.

Usage:
  python scripts/actions/mastery.py spend <skill> "<action name>" <levels>
  python scripts/actions/mastery.py claim <skill>

Examples:
  python scripts/actions/mastery.py spend fishing "Raw Shrimp" 3
  python scripts/actions/mastery.py spend mining "Rune Essence" 5
  python scripts/actions/mastery.py claim woodcutting
"""

import os
import re
import sys
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright
from _action_screenshots import take_action_screenshot
from _action_logging import log_action_call, log_action_result
from navigate import navigate

os.environ.setdefault("NODE_NO_WARNINGS", "1")
CDP_URL = "http://localhost:9222"

SKILL_ALIASES = {
    "fishing": "fishing",
    "mining": "mining",
    "woodcutting": "woodcutting",
    "firemaking": "firemaking",
    "cooking": "cooking",
    "smithing": "smithing",
    "farming": "farming",
}

SKILL_PAGE_LABELS = {
    "fishing": "Fishing",
    "mining": "Mining",
    "woodcutting": "Woodcutting",
    "firemaking": "Firemaking",
    "cooking": "Cooking",
    "smithing": "Smithing",
    "farming": "Farming",
}


def _is_skill_page_open(page: Page, skill_key: str) -> bool:
    try:
        open_page_id = page.evaluate("() => String(game?.openPage?.id ?? '')")
    except Exception:
        return False
    return skill_key in str(open_page_id).lower()


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "melvor" in pg.url.lower():
                return pg
    return browser.contexts[0].pages[0]


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _resolve_skill(skill: str) -> str | None:
    return SKILL_ALIASES.get(_norm(skill))


def clear_ui_blockers(page: Page, close_modals: bool = True) -> None:
    """Best-effort cleanup for modals/overlays/dropdowns that block clicks."""
    for _ in range(4):
        changed = False

        popup = page.locator(".swal2-popup")
        if popup.count() > 0 and popup.first.is_visible():
            for btn in (
                page.locator(".swal2-confirm"),
                page.locator(".swal2-cancel"),
                page.locator(".swal2-close"),
            ):
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click()
                    page.wait_for_timeout(120)
                    changed = True
                    break
            if not changed:
                page.keyboard.press("Escape")
                page.wait_for_timeout(120)
                changed = True

        if close_modals:
            modal_close = _first_visible(page.locator(".modal.show .btn-block-option, .modal.show [data-dismiss='modal']"))
            if modal_close is not None:
                modal_close.click()
                page.wait_for_timeout(120)
                changed = True

        open_menus = page.locator(".dropdown-menu.show")
        if open_menus.count() > 0 and open_menus.first.is_visible():
            page.keyboard.press("Escape")
            page.wait_for_timeout(100)
            if open_menus.count() > 0 and open_menus.first.is_visible():
                page.mouse.click(5, 5)
                page.wait_for_timeout(100)
            changed = True

        close_menu_btn = page.locator("button").filter(has_text="Close Menu")
        if close_menu_btn.count() > 0 and close_menu_btn.first.is_visible():
            try:
                close_menu_btn.first.scroll_into_view_if_needed(timeout=300)
            except Exception:
                pass
            try:
                close_menu_btn.first.click(timeout=500)
                page.wait_for_timeout(120)
                changed = True
            except Exception:
                # If the button is visible but outside viewport/blocked, do not stall for 30s.
                page.keyboard.press("Escape")
                page.wait_for_timeout(120)
                changed = True

        overlay = page.locator("#page-overlay")
        if overlay.count() > 0 and overlay.first.is_visible():
            page.keyboard.press("Escape")
            page.wait_for_timeout(120)
            if overlay.first.is_visible():
                page.mouse.click(5, 5)
                page.wait_for_timeout(120)
            changed = True

        if not changed:
            break


def _close_sidebar_if_open(page: Page):
    try:
        btn = page.locator("#sidebar-btn")
        if btn.count() > 0 and btn.is_visible():
            # Toggle button closes open side-overlay on small viewport layouts.
            btn.click(timeout=500)
            page.wait_for_timeout(120)
    except Exception:
        pass


def _ensure_skill_page(page: Page, skill_key: str) -> bool:
    if skill_key not in SKILL_PAGE_LABELS:
        print(f"No page label mapping for skill '{skill_key}'.")
        return False
    if _is_skill_page_open(page, skill_key):
        return True
    clear_ui_blockers(page)
    ok = navigate(skill_key, page=page, quiet=True)
    if not ok:
        print(f"Navigation failed for skill '{skill_key}'.")
        return False
    page.wait_for_timeout(200)
    return True


def _first_visible(locator):
    for i in range(locator.count()):
        el = locator.nth(i)
        if el.is_visible():
            return el
    return None


def _open_spend_modal(page: Page):
    clear_ui_blockers(page)
    _close_sidebar_if_open(page)
    btn = _first_visible(page.locator("button").filter(has_text="Spend Mastery Pool XP"))
    if btn is None:
        print("Could not find visible 'Spend Mastery Pool XP' button on this skill page.")
        return None
    try:
        btn.scroll_into_view_if_needed(timeout=500)
    except Exception:
        pass
    try:
        btn.click(timeout=800)
    except PlaywrightTimeoutError:
        btn.click(timeout=800, force=True)
    page.wait_for_timeout(300)
    modal = page.locator("#modal-spend-mastery-xp.show").first
    if modal.count() == 0 or not modal.is_visible():
        print("Spend Mastery modal did not open.")
        return None
    return modal


def _close_modal(page: Page):
    close_btn = _first_visible(page.locator("#modal-spend-mastery-xp.show .btn-block-option"))
    if close_btn is not None:
        close_btn.click()
        page.wait_for_timeout(150)
    else:
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)


def _extract_pool_text(modal) -> str:
    txt = (modal.locator("mastery-pool-display").first.text_content() or "").strip()
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*/\s*([\d,]+(?:\.\d+)?)\s*\(([\d.]+%)\)", txt)
    return f"{m.group(1)}/{m.group(2)} ({m.group(3)})" if m else txt


def _resolve_action_row(modal, query: str):
    q = _norm(query)
    rows = modal.locator("spend-mastery-menu-item")
    candidates = []
    for i in range(rows.count()):
        row = rows.nth(i)
        row_text = " ".join((row.text_content() or "").split())
        m = re.match(r"^(.*?)\s+\d[\d,]*\s+\d[\d,]*\s+XP\b", row_text, flags=re.IGNORECASE)
        name = m.group(1).strip() if m else ""
        if not name and row_text:
            name = row_text.split(" XP")[0].strip()
        if not name:
            continue
        candidates.append((row, name))

    exact = [(r, n) for r, n in candidates if _norm(n) == q]
    if exact:
        return exact[0][0], exact[0][1], None
    partial = [(r, n) for r, n in candidates if q and q in _norm(n)]
    if len(partial) == 1:
        return partial[0][0], partial[0][1], None
    if len(partial) > 1:
        return None, "", f"Ambiguous action '{query}'. Matches: {', '.join(n for _, n in partial[:20])}"
    return None, "", f"Unknown action in mastery modal: '{query}'"


def _extract_row_level(row, name: str) -> int | None:
    txt = " ".join((row.text_content() or "").split())
    m = re.search(rf"{re.escape(name)}\s+(\d+)\b", txt)
    return int(m.group(1)) if m else None


def _set_increment(modal, step: int) -> bool:
    btn = _first_visible(modal.locator("button.btn.btn-sm.btn-success.m-1").filter(has_text=f"+{step}"))
    if btn is None:
        print(f"Could not find increment button +{step}.")
        return False
    btn.click()
    modal.page.wait_for_timeout(80)
    return True


def _click_row_spend_button(row) -> bool:
    buttons = row.locator("button.btn.btn-sm.btn-success")
    if buttons.count() == 0:
        return False
    btn = buttons.first
    try:
        btn.scroll_into_view_if_needed()
    except Exception:
        pass
    if not btn.is_visible() or not btn.is_enabled():
        return False
    btn.click()
    row.page.wait_for_timeout(100)
    return True


def spend_pool(page: Page, skill_key: str, action_query: str, levels: int) -> bool:
    if levels <= 0:
        print("Levels must be a positive integer.")
        return False

    clear_ui_blockers(page)
    if not _ensure_skill_page(page, skill_key):
        return False

    modal = _open_spend_modal(page)
    if modal is None:
        return False

    row, action_name, err = _resolve_action_row(modal, action_query)
    if err:
        _close_modal(page)
        print(err)
        return False

    before_pool = _extract_pool_text(modal)
    before_level = _extract_row_level(row, action_name)

    remaining = levels
    click_count = 0
    for step in (10, 5, 1):
        if remaining < step:
            continue
        if not _set_increment(modal, step):
            _close_modal(page)
            return False
        while remaining >= step:
            modal = page.locator("#modal-spend-mastery-xp.show").first
            if modal.count() == 0 or not modal.is_visible():
                print("Spend Mastery modal closed unexpectedly.")
                return False
            # Re-resolve row each click in case list rerenders.
            row, _, _ = _resolve_action_row(modal, action_name)
            if row is None or not _click_row_spend_button(row):
                remaining = 0
                break
            remaining -= step
            click_count += 1

    # Give the UI one beat before final read.
    page.wait_for_timeout(150)
    row_after, _, _ = _resolve_action_row(modal, action_name)
    after_level = _extract_row_level(row_after, action_name) if row_after is not None else None
    after_pool = _extract_pool_text(modal)
    _close_modal(page)

    if click_count == 0:
        print(f"No mastery pool spend performed for '{action_name}' (pool may be too low or action capped).")
        return False

    if before_level is not None and after_level is not None:
        gain = after_level - before_level
        if gain <= 0:
            print(f"No mastery levels added for '{action_name}' (pool may be too low or action capped).")
            return False
        print(f"Skill: {SKILL_PAGE_LABELS[skill_key]}")
        print(f"Action: {action_name}")
        print(f"Mastery: {before_level} -> {after_level} (+{gain})")
        print(f"Pool: {before_pool} -> {after_pool}")
        return True

    print(f"Skill: {SKILL_PAGE_LABELS[skill_key]}")
    print(f"Action: {action_name}")
    print(f"Requested spend: {levels} level(s) using UI clicks.")
    print(f"Pool: {before_pool} -> {after_pool}")
    return True


def _parse_bank_claim_count(text: str) -> int | None:
    m = re.search(r"\((\d+)\)", text or "")
    return int(m.group(1)) if m else None


def claim_tokens_in_bank(page: Page, skill_key: str) -> bool:
    clear_ui_blockers(page)
    if not _ensure_skill_page(page, skill_key):
        return False
    clear_ui_blockers(page)

    modal = _open_spend_modal(page)
    if modal is None:
        return False

    btn = _first_visible(
        modal.locator("button, [role='button'], a.btn").filter(
            has_text=re.compile(r"claim tokens in bank", re.IGNORECASE)
        )
    )
    if btn is None:
        print("Could not find visible 'Claim Tokens in Bank' button.")
        _close_modal(page)
        return False

    before_txt = " ".join((btn.text_content() or "").split())
    before = _parse_bank_claim_count(before_txt)
    if before is not None and before <= 0:
        print(f"No bank mastery tokens to claim for {SKILL_PAGE_LABELS[skill_key]}.")
        _close_modal(page)
        return False

    btn.click()
    page.wait_for_timeout(220)
    clear_ui_blockers(page, close_modals=False)

    modal_after = page.locator("#modal-spend-mastery-xp.show").first
    if modal_after.count() == 0 or not modal_after.is_visible():
        print("Claim executed (Spend Mastery modal closed).")
        return True

    btn_after = _first_visible(
        modal_after.locator("button, [role='button'], a.btn").filter(
            has_text=re.compile(r"claim tokens in bank", re.IGNORECASE)
        )
    )
    after = None
    if btn_after is not None:
        after_txt = " ".join((btn_after.text_content() or "").split())
        after = _parse_bank_claim_count(after_txt)

    if before is not None and after is not None and after >= before:
        print(f"Claim did not reduce bank token count ({before} -> {after}).")
        _close_modal(page)
        return False

    if before is not None and after is not None:
        print(
            f"Claimed {before - after} bank mastery token(s) via "
            f"{SKILL_PAGE_LABELS[skill_key]} mastery interface."
        )
    else:
        print(f"Claimed bank mastery tokens via {SKILL_PAGE_LABELS[skill_key]} mastery interface.")
    _close_modal(page)
    return True


if __name__ == "__main__":
    log_action_call("mastery.py", sys.argv[1:])
    if len(sys.argv) < 3:
        log_action_result("mastery.py", sys.argv[1:], False, details="Missing required arguments.")
        print(__doc__)
        sys.exit(1)

    cmd = _norm(sys.argv[1])
    if cmd not in {"spend", "claim"}:
        log_action_result("mastery.py", sys.argv[1:], False, details=f"Unknown command: {cmd}")
        print(f"Unknown command: '{cmd}'")
        print(__doc__)
        sys.exit(1)

    if cmd == "spend" and len(sys.argv) < 5:
        log_action_result("mastery.py", sys.argv[1:], False, details="Missing required arguments for spend.")
        print(__doc__)
        sys.exit(1)

    skill_key = _resolve_skill(sys.argv[2])
    if not skill_key:
        log_action_result("mastery.py", sys.argv[1:], False, details=f"Unknown skill: {sys.argv[2]}")
        print(f"Unknown skill: '{sys.argv[2]}'")
        print(f"Supported skills: {', '.join(sorted(SKILL_ALIASES.keys()))}")
        sys.exit(1)

    action_name = ""
    levels = 0
    if cmd == "spend":
        action_name = sys.argv[3].strip()
        try:
            levels = int(sys.argv[4])
        except ValueError:
            log_action_result("mastery.py", sys.argv[1:], False, details="Levels is not an integer.")
            print("Levels must be an integer.")
            sys.exit(1)

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if cmd == "spend":
            action_label = f"mastery_spend_{skill_key}_{action_name}_{levels}"
            before = take_action_screenshot("before", action_label, page=page)
            ok = spend_pool(page, skill_key, action_name, levels)
            after = take_action_screenshot("after", action_label, page=page)
            log_action_result("mastery.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)

        if len(sys.argv) >= 4:
            log_action_result("mastery.py", sys.argv[1:], False, details="Claim does not accept quantity.")
            print("Usage: python scripts/actions/mastery.py claim <skill>")
            sys.exit(1)
        action_label = f"mastery_claim_{skill_key}"
        before = take_action_screenshot("before", action_label, page=page)
        ok = claim_tokens_in_bank(page, skill_key)
        after = take_action_screenshot("after", action_label, page=page)
        log_action_result("mastery.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)
