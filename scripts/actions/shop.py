#!/usr/bin/env python3
"""
shop.py — Buy shop upgrades/items.

Usage:
  python scripts/actions/shop.py buy "extra bank slot" 5

Behavior:
  - Auto-navigates to Shop if needed (scripts/actions/navigate.py).
  - Sets current shop buy quantity to X (via Shop UI dropdown)
  - Clicks the matched visible shop card once at that quantity
"""

import sys
import os

os.environ.setdefault("NODE_NO_WARNINGS", "1")
from playwright.sync_api import sync_playwright

import navigate as _navigate
from _action_logging import log_action_call, log_action_result
from _action_screenshots import take_action_screenshot

CDP_URL = "http://localhost:9222"


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for page in ctx.pages:
            if "melvor" in page.url.lower():
                return page
    return None


def ensure_game_ready(page) -> bool:
    try:
        page.wait_for_function("() => typeof game !== 'undefined' && !!game.shop", timeout=10000)
        return True
    except Exception:
        return False


def is_on_shop_page(page) -> bool:
    """Match navigate.py: game.openPage.id; DOM fallback if a category is already open (no 'Select Shop Category' visible)."""
    try:
        oid = page.evaluate("() => String(game?.openPage?.id ?? '').toLowerCase()")
        if oid and "shop" in oid:
            return True
        if page.locator("button.shop-buy-qty-btn").count() == 0:
            return False
        sel = page.locator("button").filter(has_text="Select Shop Category").first
        return sel.is_visible()
    except Exception:
        return False


def buy_item(name: str, qty: int) -> bool:
    if qty <= 0:
        print("Quantity must be greater than 0.")
        return False

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False
        if not is_on_shop_page(page):
            if not _navigate.navigate("shop", page=page):
                print("Could not navigate to the Shop page.")
                return False
            page.wait_for_timeout(400)
        if not is_on_shop_page(page):
            print("Still not on the Shop page after navigation.")
            return False

        # 1) Set buy quantity via visible shop dropdown.
        qty_btn = page.locator("button.shop-buy-qty-btn").first
        if not qty_btn.is_visible():
            print("Could not find Shop buy quantity control.")
            return False
        qty_btn.click()
        page.wait_for_timeout(150)

        custom_input = page.locator(".dropdown-menu.show input[id^='dropdown-content-custom-amount-']").first
        if not custom_input.is_visible():
            print("Could not open Shop quantity input.")
            return False
        custom_input.fill(str(qty))
        custom_input.press("Enter")
        page.wait_for_timeout(200)

        applied = qty_btn.text_content() or ""
        if f"x{qty:,}" not in applied and f"x{qty}" not in applied:
            print(f"Failed to apply buy quantity {qty}.")
            return False

        # Close the quantity dropdown so it does not block shop card clicks.
        if page.locator(".dropdown-menu.show").count() > 0:
            page.keyboard.press("Escape")
            page.wait_for_timeout(120)
        if page.locator(".dropdown-menu.show").count() > 0:
            page.mouse.click(5, 5)
            page.wait_for_timeout(120)
        if page.locator(".dropdown-menu.show").count() > 0:
            print("Could not close Shop quantity dropdown.")
            return False

        # 2) Find visible shop card by name (exact first, then partial).
        cards = page.locator("a.block.block-content.block-rounded.block-link-pop.pointer-enabled.border.border-2x")
        exact = cards.filter(has_text=name).all()
        target = None
        if len(exact) == 1:
            target = exact[0]
        elif len(exact) > 1:
            print(f"Ambiguous exact match for '{name}'.")
            return False
        else:
            # case-insensitive partial matching from visible card texts
            key = name.strip().lower()
            matches = []
            total = cards.count()
            for i in range(total):
                c = cards.nth(i)
                if not c.is_visible():
                    continue
                txt = (c.text_content() or "").lower()
                if key in txt:
                    matches.append(c)
            if len(matches) == 1:
                target = matches[0]
            elif len(matches) > 1:
                print(f"Ambiguous: '{name}' matches {len(matches)} visible shop entries.")
                return False
            else:
                print(f"Shop item not found in current category view: '{name}'.")
                return False

        # 3) Click purchase card, then handle popup if one appears.
        target.click()
        page.wait_for_timeout(350)

        popup = page.locator(".swal2-popup")
        confirm = page.locator(".swal2-confirm")
        if popup.is_visible():
            popup_text = (popup.text_content() or "").strip().lower()
            if confirm.is_visible():
                confirm.click()
                page.wait_for_timeout(250)
            if any(
                key in popup_text
                for key in ("not enough", "cannot afford", "insufficient", "locked", "requirements")
            ):
                print(f"Could not buy {name} x{qty}: {popup_text}")
                return False
        elif confirm.is_visible():
            confirm.click()
            page.wait_for_timeout(250)
    print(f"Buy click sent for {qty}x {name}.")
    return True


if __name__ == "__main__":
    log_action_call("shop.py", sys.argv[1:])
    if len(sys.argv) < 4:
        log_action_result("shop.py", sys.argv[1:], False, details="Missing required arguments.")
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower().strip()
    name = sys.argv[2]

    if cmd != "buy":
        log_action_result("shop.py", sys.argv[1:], False, details=f"Unknown command: {cmd}")
        print(f"Unknown command: '{cmd}'. Use 'buy'.")
        sys.exit(1)

    try:
        qty = int(sys.argv[3])
    except ValueError:
        log_action_result("shop.py", sys.argv[1:], False, details="Quantity is not an integer.")
        print(f"Error: quantity must be a number, got '{sys.argv[3]}'")
        sys.exit(1)

    action_label = f"shop_buy_{name}_{qty}"
    before = take_action_screenshot("before", action_label)
    ok = buy_item(name, qty)
    after = take_action_screenshot("after", action_label)
    log_action_result("shop.py", sys.argv[1:], ok, before, after)
    sys.exit(0 if ok else 1)
