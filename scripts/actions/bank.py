#!/usr/bin/env python3
"""
bank.py — Sell, equip, upgrade, or open items in the Bank via UI clicks.

Usage:
  python scripts/actions/bank.py sell "potatoes" 50        # sell 50 Potatoes (qty required)
  python scripts/actions/bank.py sellmulti "potatoes" 50 "bones" 10  # sell multiple pairs in one command
  python scripts/actions/bank.py sell "bones" 10
  python scripts/actions/bank.py equip "bronze dagger"       # equip weapon/armour only
  python scripts/actions/bank.py equipfood "potatoes"        # equip all as food (qty optional)
  python scripts/actions/bank.py equipfood "potatoes" 20     # equip 20 as food
  python scripts/actions/bank.py upgrade "rope" 1          # upgrade item in bank panel (qty default 1)
  python scripts/actions/bank.py open "bird nest" 10       # open openable item (qty default 1)
  python scripts/actions/bank.py claim "mastery token (woodcutting)" 1  # claim token item (qty default 1)

Must be on the Bank page first (use navigate.py bank).

Notes:
  - sell: quantity is REQUIRED, no default to avoid confusion
  - sellmulti: pass repeated "<item>" <qty> pairs; captures one before/after screenshot for the batch
  - equip: weapon/armour only (uses "Equip to:"); quantity not used
  - equipfood: food only (uses "Equip Food"); quantity defaults to all if omitted
  - upgrade: quantity defaults to 1; modal uses x1/x10/… if present; if no exact tier, uses x1 (not All)
  - open: quantity defaults to 1; uses bank open UI button/input when available
  - claim: quantity defaults to 1; uses bank claim token UI button/input when available
"""

import re
import sys, os
os.environ.setdefault("NODE_NO_WARNINGS", "1")
from playwright.sync_api import Locator, Page, sync_playwright
from _action_screenshots import take_action_screenshot
from _action_logging import log_action_call, log_action_result

CDP_URL = "http://localhost:9222"


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "melvor" in pg.url.lower():
                return pg
    return browser.contexts[0].pages[0]


def is_on_bank_page(page: Page) -> bool:
    search = page.locator('input[name="searchTextbox"]')
    return search.count() > 0 and search.is_visible()


def clear_bank_search(page: Page) -> None:
    """Clear bank search input so post-action screenshots show full bank."""
    search = page.locator('input[name="searchTextbox"]')
    if search.count() == 0:
        return
    try:
        if search.is_visible():
            search.click(force=True)
            search.press("Control+A")
            search.press("Backspace")
            search.fill("")
            search.press("Enter")
        page.wait_for_timeout(120)
    except Exception:
        # Best-effort cleanup; do not fail the action because cleanup failed.
        pass


def id_to_name(item_id: str) -> str:
    """'melvorD:Bronze_Dagger' -> 'Bronze Dagger'"""
    return item_id.split(":")[-1].replace("_", " ")


def close_item_menu(page: Page) -> None:
    """Best-effort close of the bank item side panel."""
    close_btn = page.locator("button").filter(has_text="Close Menu").first
    try:
        if close_btn.count() > 0 and close_btn.is_visible():
            try:
                close_btn.scroll_into_view_if_needed(timeout=300)
            except Exception:
                pass
            try:
                close_btn.click(timeout=500)
            except Exception:
                close_btn.click(force=True, timeout=500)
            page.wait_for_timeout(120)
    except Exception:
        # Never fail command flow on menu close cleanup.
        pass


# Close Menu lives *outside* ``bank-selected-item-menu`` in current Melvor builds; do not only scan the custom element.
_BANK_PANEL_OPEN_JS = """() => {
    const bi = game?.bank?.selectedBankItem;
    if (bi && (bi.item?.id || bi.item?.name || bi.id)) return true;
    const m = document.querySelector('bank-selected-item-menu');
    if (!m) return false;
    const actionBtns = [
        'sellItemButton',
        'openItemButton',
        'upgradeButton',
        'equipFoodButton',
        'claimTokenButton',
        'buryItemButton',
        'sellAllButton',
    ];
    for (const name of actionBtns) {
        const el = m[name];
        if (el && typeof el.getBoundingClientRect === 'function') {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) return true;
        }
    }
    for (const el of document.querySelectorAll('button, [role="button"]')) {
        const t = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
        if (!t.includes('Close Menu')) continue;
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) return true;
    }
    return false;
}"""


def _wait_bank_item_panel_open(page: Page, item: Locator) -> None:
    """Wait until the bank side panel is open (Close Menu has a real layout box).

    If the first click opened the panel but Playwright never saw ``visible``, we must not click
    again — that toggles the stack off. Only second-click after wait_for_function times out."""
    try:
        page.wait_for_function(_BANK_PANEL_OPEN_JS, timeout=3500)
        return
    except Exception:
        pass
    try:
        item.click(timeout=3000)
        page.wait_for_function(_BANK_PANEL_OPEN_JS, timeout=3500)
    except Exception:
        pass


def find_and_click_item(page: Page, item_name: str) -> bool:
    """Search the bank for item_name, click it. Returns False if not found."""
    # Close lingering upgrade modal if present.
    close_upgrade_modal(page)

    # Close any open item panel first
    close_item_menu(page)

    # press_sequentially fires keyboard events Melvor listens to for search filtering.
    # delay=0 removes the artificial per-character pause while still firing all events.
    search = page.locator('input[name="searchTextbox"]')
    search.click()
    search.select_text()
    search.press_sequentially(item_name, delay=0)
    page.wait_for_timeout(80)

    # Gather visible bank items after filtering.
    icons = page.locator("bank-item-icon:visible")
    icon_count = icons.count()
    if icon_count == 0:
        print(f"Item not found in bank: '{item_name}'")
        return False

    # Fast-path: filtered view usually leaves exactly one match.
    if icon_count == 1:
        target_id = icons.first.get_attribute("data-item-id")
        if not target_id:
            print(f"Item not found in bank: '{item_name}'")
            return False
        print(f"Found: {id_to_name(target_id)} ({target_id})")
        item = page.locator(f'[data-item-id="{target_id}"]')
        item.click()
        _wait_bank_item_panel_open(page, item)
        return True

    item_ids = []
    for i in range(min(icon_count, 30)):
        try:
            item_id = icons.nth(i).get_attribute("data-item-id")
            if item_id:
                item_ids.append(item_id)
        except Exception:
            continue

    if not item_ids:
        print(f"Item not found in bank: '{item_name}'")
        return False

    # Try exact match first (case-insensitive), then partial
    target_id = None
    key = item_name.strip().lower()
    exact = [i for i in item_ids if id_to_name(i).lower() == key]
    if len(exact) == 1:
        target_id = exact[0]
    elif len(exact) > 1:
        print(f"Multiple exact matches for '{item_name}': {[id_to_name(i) for i in exact]}")
        return False
    else:
        partial = [i for i in item_ids if key in id_to_name(i).lower()]
        if len(partial) == 1:
            target_id = partial[0]
        elif len(partial) > 1:
            print(f"Ambiguous: '{item_name}' matches: {[id_to_name(i) for i in partial]}")
            return False
        else:
            print(f"Item not found in bank: '{item_name}'")
            return False

    print(f"Found: {id_to_name(target_id)} ({target_id})")
    item = page.locator(f'[data-item-id="{target_id}"]')
    item.click()
    _wait_bank_item_panel_open(page, item)
    return True


def set_food_slider(page: Page, qty: int) -> None:
    """Click the food equip slider track to set an approximate quantity."""
    # Panel opens with slider at max (equip all) — reading value gives us the max
    try:
        max_qty = int(page.locator('[name="bank-rangeslider-food"]').input_value())
    except (ValueError, TypeError):
        return

    if qty >= max_qty:
        return

    # Scope to the form-group that contains the food slider input
    track = page.locator(".form-group:has([name='bank-rangeslider-food']) .irs-line")
    box = track.bounding_box()
    if not box:
        return

    ratio = (qty - 1) / max(max_qty - 1, 1)
    x = box["x"] + ratio * box["width"]
    y = box["y"] + box["height"] / 2
    page.mouse.click(x, y)
    page.wait_for_timeout(200)


def _set_open_quantity(page: Page, qty: int) -> bool:
    """Set open quantity via BankRangeSlider.setSliderPosition() — the authoritative API."""
    target = max(1, qty)

    # Use the game's own BankRangeSlider.setSliderPosition() which updates both
    # the ion.rangeSlider display and the _sliderValue that openItemOnClick reads.
    # Direct sliderInstance.update() only updates the display and is NOT sufficient.
    result = page.evaluate("""(target) => {
        const menu = document.querySelector('bank-selected-item-menu');
        if (!menu || !menu.openItemQuantitySlider) return null;
        const slider = menu.openItemQuantitySlider;
        slider.setSliderPosition(target);
        return slider.quantity;
    }""", target)

    if result is not None and result == target:
        return True

    # If clamped to max (fewer items in bank than requested), still accept it.
    if result is not None and result > 0:
        return True

    return False


def _set_sell_quantity(page: Page, qty: int) -> bool:
    """Set sell quantity via ``sellItemQuantitySlider`` (BankRangeSlider), then ``customSellQuantity`` input.

    Live game (CDP): ``bank-sell-x`` exists but is often not Playwright-visible (ion range slider UI);
    prefer slider + ``customSellQuantity`` on ``bank-selected-item-menu``.
    """
    target = max(1, qty)
    result = page.evaluate(
        """(target) => {
            const menu = document.querySelector('bank-selected-item-menu');
            if (!menu) return null;

            const slider = menu.sellItemQuantitySlider;
            if (slider && typeof slider.setSliderPosition === 'function') {
                slider.setSliderPosition(target);
                return slider.quantity;
            }

            const custom = menu.customSellQuantity;
            if (custom && custom.tagName === 'INPUT') {
                custom.focus();
                custom.value = String(target);
                custom.dispatchEvent(new Event('input', { bubbles: true }));
                custom.dispatchEvent(new Event('change', { bubbles: true }));
                const v = Number(custom.value);
                return Number.isFinite(v) && v > 0 ? v : target;
            }

            const findSellInput = (root) => {
                const sels = [
                    'input[name="bank-sell-x"]',
                    'input[name="bankSellX"]',
                    'input[id*="bank-sell"]',
                    'input[id*="sell"][type="text"]',
                    'input[type="text"][name*="sell"]',
                ];
                const tryRoot = (r) => {
                    if (!r || !r.querySelector) return null;
                    for (const sel of sels) {
                        try {
                            const el = r.querySelector(sel);
                            if (el) return el;
                        } catch (e) {}
                    }
                    const nodes = r.querySelectorAll ? r.querySelectorAll('*') : [];
                    for (const n of nodes) {
                        if (n.shadowRoot) {
                            const el = tryRoot(n.shadowRoot);
                            if (el) return el;
                        }
                    }
                    return null;
                };
                return tryRoot(root) || tryRoot(menu.shadowRoot);
            };

            const inp = findSellInput(menu);
            if (inp) {
                inp.focus();
                inp.value = String(target);
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
                const v = Number(inp.value);
                return Number.isFinite(v) && v > 0 ? v : target;
            }
            return null;
        }""",
        target,
    )

    if result is not None and int(result) == target:
        return True
    if result is not None and int(result) > 0:
        return True
    return False


def _find_sell_button(page: Page):
    loc = page.locator("button.btn-danger, button, [role='button'], a.btn").filter(
        has_text=re.compile(r"sell\s*item", re.IGNORECASE)
    ).first
    try:
        if loc.is_visible() and loc.is_enabled():
            return loc
    except Exception:
        pass
    return None


def _find_open_button(page: Page):
    """Find Open Item control; same visibility quirks as Equip / Upgrade."""
    locs = page.locator("button, [role='button'], a.btn, a[class*='btn']").filter(
        has_text=re.compile(r"open\s*item", re.IGNORECASE)
    )
    try:
        locs.first.wait_for(state="attached", timeout=3500)
    except Exception:
        pass
    n = locs.count()
    for i in range(min(n, 12)):
        loc = locs.nth(i)
        try:
            if loc.is_visible() and loc.is_enabled():
                return loc
        except Exception:
            continue
    return None


def _click_open_item_dom(page: Page) -> bool:
    """``bank-selected-item-menu.openItemButton`` or visible Open Item label."""
    return bool(
        page.evaluate(
            """() => {
                const menu = document.querySelector('bank-selected-item-menu');
                if (!menu) return false;
                const b = menu.openItemButton;
                if (b && !b.disabled) {
                    b.click();
                    return true;
                }
                for (const el of menu.querySelectorAll(
                    'button, a.btn, a[class*="btn"], a.btn-sm, [role="button"]'
                )) {
                    const t = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                    if (!/open\\s*item/i.test(t)) continue;
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }"""
        )
    )


def _find_claim_button(page: Page):
    """Find visible/enabled claim button in bank item panel."""
    loc = page.locator("button, [role='button'], a.btn").filter(
        has_text=re.compile(r"claim token", re.IGNORECASE)
    ).first
    try:
        if loc.is_visible() and loc.is_enabled():
            return loc
    except Exception:
        pass
    return None


def _set_claim_quantity(page: Page, qty: int) -> bool:
    """Set claim quantity using the bank token claim slider API."""
    target = max(1, qty)
    result = page.evaluate(
        """(target) => {
            const menu = document.querySelector('bank-selected-item-menu');
            if (!menu || !menu.claimTokenQuantitySlider) return null;
            const slider = menu.claimTokenQuantitySlider;
            slider.setSliderPosition(target);
            return slider.quantity;
        }""",
        target,
    )
    return result is not None and int(result) == target


def open_item(item_name: str, qty: int | None) -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)

        if not is_on_bank_page(page):
            print("Not on the Bank page. Run: python scripts/actions/navigate.py bank")
            return False

        try:
            if not find_and_click_item(page, item_name):
                return False

            try:
                page.locator("bank-selected-item-menu").wait_for(state="attached", timeout=3500)
            except Exception:
                pass
            page.wait_for_timeout(200)

            open_btn = _find_open_button(page)

            open_qty = 1 if qty is None else max(1, qty)
            if not _set_open_quantity(page, open_qty):
                print(
                    f"Could not safely set open quantity to {open_qty}. "
                    "Aborting to avoid opening wrong amount."
                )
                return False

            if open_btn is not None:
                open_btn.click()
            elif not _click_open_item_dom(page):
                print(f"Item '{item_name}' is not openable (no Open Item control found).")
                return False
            page.wait_for_timeout(120)

            popup_text, is_error = _dismiss_popup(page)
            if is_error:
                print(f"Open failed for '{item_name}': {popup_text}")
                return False

            close_item_menu(page)

            if popup_text:
                print(f"Open result: {popup_text}")
            else:
                print(f"Opened '{item_name}' x{open_qty}.")
            return True
        finally:
            clear_bank_search(page)


def claim_token(item_name: str, qty: int | None) -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)

        if not is_on_bank_page(page):
            print("Not on the Bank page. Run: python scripts/actions/navigate.py bank")
            return False

        try:
            if not find_and_click_item(page, item_name):
                return False

            page.wait_for_timeout(80)
            claim_btn = _find_claim_button(page)
            if claim_btn is None:
                print(f"Item '{item_name}' is not claimable (no Claim Token button visible).")
                return False

            claim_qty = 1 if qty is None else max(1, qty)
            if not _set_claim_quantity(page, claim_qty):
                print(
                    f"Could not safely set claim quantity to {claim_qty}. "
                    "Aborting to avoid claiming wrong amount."
                )
                return False

            claim_btn.click()
            page.wait_for_timeout(120)

            popup_text, is_error = _dismiss_popup(page)
            if is_error:
                print(f"Claim failed for '{item_name}': {popup_text}")
                return False

            close_item_menu(page)

            if popup_text:
                print(f"Claim result: {popup_text}")
            else:
                print(f"Claimed '{item_name}' x{claim_qty}.")
            return True
        finally:
            clear_bank_search(page)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def sell(item_name: str, qty: int) -> bool:
    return _sell_on_page(item_name, qty)


def _sell_on_page(item_name: str, qty: int, page: Page | None = None) -> bool:
    owns_page = page is None
    pw = None
    if owns_page:
        pw = sync_playwright().start()
        page = get_melvor_page(pw)

    assert page is not None

    if not is_on_bank_page(page):
        if owns_page:
            print("Not on the Bank page. Run: python scripts/actions/navigate.py bank")
        return False

    try:
        if not find_and_click_item(page, item_name):
            return False

        try:
            page.locator("bank-selected-item-menu").wait_for(state="attached", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(200)

        sell_qty = max(1, int(qty))
        if not _set_sell_quantity(page, sell_qty):
            qty_input = page.locator("bank-selected-item-menu").locator('input[name="bank-sell-x"]').first
            if qty_input.count() == 0:
                qty_input = page.locator('input[name="bank-sell-x"]').first
            try:
                qty_input.wait_for(state="visible", timeout=3000)
                qty_input.click(click_count=3)
                qty_input.fill(str(sell_qty))
            except Exception:
                print(
                    "Could not set sell quantity (no slider/input found). "
                    "Item may not be sellable or bank panel layout changed."
                )
                return False
            page.wait_for_timeout(200)

        sell_btn = _find_sell_button(page)
        if sell_btn is not None:
            sell_btn.click()
        else:
            clicked = page.evaluate(
                """() => {
                    const m = document.querySelector('bank-selected-item-menu');
                    const b = m?.sellItemButton;
                    if (b && !b.disabled) {
                        b.click();
                        return true;
                    }
                    return false;
                }"""
            )
            if not clicked:
                print("Sell Item button not found — item may not be sellable.")
                return False
        page.wait_for_timeout(400)

        # Confirm the SweetAlert2 popup
        confirm = page.locator(".swal2-confirm")
        if confirm.is_visible():
            confirm.click()
            page.wait_for_timeout(300)
            print(f"Sold {sell_qty}x {item_name}.")
        else:
            print("Confirm popup did not appear — sell may have failed.")
            return False

        return True
    finally:
        clear_bank_search(page)
        if owns_page and pw is not None:
            pw.stop()


def sell_multi(item_qty_pairs: list[tuple[str, int]]) -> bool:
    if not item_qty_pairs:
        print("Error: sellmulti requires at least one <item> <qty> pair.")
        return False
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not is_on_bank_page(page):
            print("Not on the Bank page. Run: python scripts/actions/navigate.py bank")
            return False
        for item_name, qty in item_qty_pairs:
            if qty <= 0:
                print(f"Skipping invalid quantity for '{item_name}': {qty}")
                return False
            if not _sell_on_page(item_name, qty, page=page):
                print(f"Stopped batch on failure: '{item_name}' x{qty}")
                return False
        print(f"Completed sellmulti batch: {len(item_qty_pairs)} item(s).")
        return True


def _handle_equip_popup(page: Page, item_name: str) -> bool:
    """After an equip click: dismiss SweetAlert if shown. Return False on error-style popup."""
    popup = page.locator(".swal2-popup")
    if not popup.is_visible():
        return True

    title_txt = (
        page.locator(".swal2-popup #swal2-title, .swal2-popup .swal2-title").first.text_content() or ""
    )
    content_txt = (
        page.locator(".swal2-popup #swal2-content, .swal2-popup .swal2-html-container").first.text_content()
        or ""
    )
    merged = f"{title_txt} {content_txt}".strip()
    popup_text = " ".join(merged.split())
    if not popup_text:
        popup_text = " ".join(((popup.text_content() or "").strip()).split())
    low = popup_text.lower()
    is_error = (
        page.locator(".swal2-icon.swal2-error").is_visible()
        or any(k in low for k in ("locked", "cannot", "can't", "requires", "not available", "demo"))
    )

    dismissed = False
    for btn in (
        page.locator(".swal2-confirm"),
        page.locator(".swal2-cancel"),
        page.locator(".swal2-close"),
    ):
        if btn.is_visible():
            btn.click()
            page.wait_for_timeout(200)
            dismissed = True
            break
    if not dismissed:
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    if popup.is_visible():
        page.mouse.click(5, 5)
        page.wait_for_timeout(200)

    close_item_menu(page)

    if is_error:
        print(f"Equip failed for '{item_name}': {popup_text}")
        return False
    return True


def _find_equip_gear_button(page: Page):
    """First *Playwright-visible* gear equip control (Melvor often uses <a class='btn'>)."""
    locs = page.locator(
        "button, [role='button'], a.btn, a[class*='btn']"
    ).filter(has_text=re.compile(r"equip\s+to", re.IGNORECASE))
    try:
        locs.first.wait_for(state="attached", timeout=8000)
    except Exception:
        pass
    n = locs.count()
    for i in range(min(n, 15)):
        loc = locs.nth(i)
        try:
            if loc.is_visible():
                return loc
        except Exception:
            continue
    return None


def _click_equip_gear_dom(page: Page) -> str | None:
    """Click gear equip by label inside bank-selected-item-menu (bypasses flaky is_visible)."""
    label = page.evaluate(
        """() => {
            const menu = document.querySelector('bank-selected-item-menu');
            if (!menu) return null;
            const nodes = menu.querySelectorAll(
                'button, [role="button"], a.btn, a[class*="btn"], a.btn-sm'
            );
            for (const el of nodes) {
                const t = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                if (!/equip\\s+to/i.test(t)) continue;
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    el.click();
                    return t;
                }
            }
            return null;
        }"""
    )
    return (label or "").strip() or None


def equip(item_name: str) -> bool:
    """Equip weapon/armour from bank (\"Equip to:\" only)."""
    with sync_playwright() as pw:
        page = get_melvor_page(pw)

        if not is_on_bank_page(page):
            print("Not on the Bank page. Run: python scripts/actions/navigate.py bank")
            return False

        try:
            if not find_and_click_item(page, item_name):
                return False

            try:
                page.locator("bank-selected-item-menu").wait_for(state="attached", timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(250)

            food_btn = (
                page.locator("button.btn-warning, a.btn.btn-warning")
                .filter(has_text=re.compile(r"equip\s+food", re.IGNORECASE))
                .first
            )
            if food_btn.is_visible():
                print(
                    f"'{item_name}' is food in the bank UI. Use: "
                    f"python scripts/actions/bank.py equipfood \"{item_name}\" [qty]"
                )
                close_item_menu(page)
                return False

            equip_btn = _find_equip_gear_button(page)
            if equip_btn is not None:
                slot_text = equip_btn.text_content().strip()
                equip_btn.click()
            else:
                slot_text = _click_equip_gear_dom(page)
                if not slot_text:
                    print(
                        f"No gear equip control for '{item_name}' — not equipment, or cannot equip from bank."
                    )
                    return False
            page.wait_for_timeout(300)

            if not _handle_equip_popup(page, item_name):
                return False

            close_item_menu(page)
            print(f"Equipped {item_name} ({slot_text}).")
            return True
        finally:
            clear_bank_search(page)


def equip_food(item_name: str, qty: int | None) -> bool:
    """Equip food from bank (\"Equip Food\" only). Quantity defaults to all if None."""
    with sync_playwright() as pw:
        page = get_melvor_page(pw)

        if not is_on_bank_page(page):
            print("Not on the Bank page. Run: python scripts/actions/navigate.py bank")
            return False

        try:
            if not find_and_click_item(page, item_name):
                return False

            food_btn = (
                page.locator("button.btn-warning, a.btn.btn-warning")
                .filter(has_text=re.compile(r"equip\s+food", re.IGNORECASE))
                .first
            )
            if not food_btn.is_visible():
                print(
                    f"No 'Equip Food' for '{item_name}'. Use: python scripts/actions/bank.py equip \"...\" for weapons/armour."
                )
                return False

            if qty is not None:
                set_food_slider(page, qty)
            food_btn.click()
            page.wait_for_timeout(300)

            if qty is not None:
                success_msg = f"Equipped {qty}x {item_name} as food."
            else:
                success_msg = f"Equipped all {item_name} as food."

            if not _handle_equip_popup(page, item_name):
                return False

            close_item_menu(page)
            print(success_msg)
            return True
        finally:
            clear_bank_search(page)


def _dismiss_popup(page: Page):
    popup = page.locator(".swal2-popup")
    if not popup.is_visible():
        return "", False
    title_txt = (
        page.locator(".swal2-popup #swal2-title, .swal2-popup .swal2-title")
        .first.text_content()
        or ""
    )
    content_txt = (
        page.locator(".swal2-popup #swal2-content, .swal2-popup .swal2-html-container")
        .first.text_content()
        or ""
    )
    merged = f"{title_txt} {content_txt}".strip()
    popup_text = " ".join(merged.split())
    if not popup_text:
        popup_text = " ".join(((popup.text_content() or "").strip()).split())
    popup_text = re.sub(r"\b(OK|No|Cancel)\b", "", popup_text, flags=re.IGNORECASE)
    popup_text = " ".join(popup_text.split()).strip()
    for btn in (
        page.locator(".swal2-confirm"),
        page.locator(".swal2-cancel"),
        page.locator(".swal2-close"),
    ):
        if btn.is_visible():
            btn.click()
            page.wait_for_timeout(200)
            break
    if popup.is_visible():
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
    if popup.is_visible():
        page.mouse.click(5, 5)
        page.wait_for_timeout(150)
    is_error = (
        page.locator(".swal2-icon.swal2-error").is_visible()
        or any(k in popup_text.lower() for k in ("cannot", "can't", "not enough", "insufficient", "requires", "locked"))
    )
    return popup_text, is_error


def close_upgrade_modal(page: Page):
    modal = page.locator("#modal-item-upgrade.show").first
    if modal.count() == 0 or not modal.is_visible():
        return
    # Prefer explicit "Close", then X button, then Escape.
    close_btn = modal.locator("button").filter(has_text="Close").first
    if close_btn.count() > 0 and close_btn.is_visible():
        close_btn.click(force=True)
        page.wait_for_timeout(150)
    else:
        x_btn = modal.locator(".btn-block-option, [data-dismiss='modal']").first
        if x_btn.count() > 0 and x_btn.is_visible():
            x_btn.click(force=True)
            page.wait_for_timeout(150)
        else:
            page.keyboard.press("Escape")
            page.wait_for_timeout(150)


def _select_upgrade_quantity(page: Page, qty: int) -> bool:
    modal = page.locator("#modal-item-upgrade.show").first
    if modal.count() == 0 or not modal.is_visible():
        return False
    for label in (f"x{qty:,}", f"x{qty}"):
        btn = modal.locator("button").filter(has_text=label).first
        if btn.count() > 0 and btn.is_visible():
            btn.click()
            page.wait_for_timeout(220)
            return True
    btn = modal.locator("button").filter(has_text="x1").first
    if btn.count() > 0 and btn.is_visible():
        btn.click()
        page.wait_for_timeout(220)
        return True
    return False


def _find_upgrade_item_button(page: Page):
    """Bank upgrade control; Melvor may omit btn-warning or use a link-styled control."""
    locs = page.locator(
        "button.btn-warning, button, a.btn, a[class*='btn'], [role='button']"
    ).filter(has_text=re.compile(r"upgrade\s*item", re.IGNORECASE))
    try:
        locs.first.wait_for(state="attached", timeout=3500)
    except Exception:
        pass
    n = locs.count()
    for i in range(min(n, 12)):
        loc = locs.nth(i)
        try:
            if loc.is_visible():
                return loc
        except Exception:
            continue
    return None


def _click_upgrade_item_dom(page: Page) -> bool:
    """Use bank-selected-item-menu.upgradeButton or visible Upgrade Item label (same idea as equip/sell)."""
    return bool(
        page.evaluate(
            """() => {
                const menu = document.querySelector('bank-selected-item-menu');
                if (!menu) return false;
                const b = menu.upgradeButton;
                if (b && !b.disabled) {
                    b.click();
                    return true;
                }
                for (const el of menu.querySelectorAll(
                    'button, a.btn, a[class*="btn"], a.btn-sm, [role="button"]'
                )) {
                    const t = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                    if (!/upgrade\\s*item/i.test(t)) continue;
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }"""
        )
    )


def upgrade(item_name: str, qty: int | None) -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)

        if not is_on_bank_page(page):
            print("Not on the Bank page. Run: python scripts/actions/navigate.py bank")
            return False

        try:
            if not find_and_click_item(page, item_name):
                return False

            try:
                page.locator("bank-selected-item-menu").wait_for(state="attached", timeout=3500)
            except Exception:
                pass
            page.wait_for_timeout(200)

            upgrade_btn = _find_upgrade_item_button(page)
            if upgrade_btn is not None:
                upgrade_btn.click()
            elif not _click_upgrade_item_dom(page):
                print(f"Item '{item_name}' is not upgradeable (no Upgrade Item control found).")
                return False

            qty = 1 if qty is None else max(1, qty)
            page.wait_for_timeout(250)

            if not _select_upgrade_quantity(page, qty):
                print(
                    f"Could not execute upgrade quantity {qty} using available upgrade modal controls."
                )
                return False

            popup_text, is_error = _dismiss_popup(page)
            if is_error:
                close_upgrade_modal(page)
                print(f"Upgrade failed for '{item_name}': {popup_text}")
                return False

            # Close upgrade modal if still open.
            close_upgrade_modal(page)

            # Close bank panel after action.
            close_item_menu(page)

            if popup_text:
                print(f"Upgrade result: {popup_text}")
            else:
                print(f"Upgrade action sent for '{item_name}' x{qty}.")
            return True
        finally:
            clear_bank_search(page)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log_action_call("bank.py", sys.argv[1:])
    if len(sys.argv) < 2:
        log_action_result("bank.py", sys.argv[1:], False, details="Missing required arguments.")
        print(__doc__)
        sys.exit(1)

    cmd  = sys.argv[1].lower()
    name = sys.argv[2] if len(sys.argv) >= 3 else ""
    action_label = f"bank_{cmd}_{name}" if name else f"bank_{cmd}"

    if cmd != "sellmulti" and len(sys.argv) < 3:
        log_action_result("bank.py", sys.argv[1:], False, details=f"{cmd} missing item name.")
        print(__doc__)
        sys.exit(1)

    if cmd == "sell":
        if len(sys.argv) < 3:
            log_action_result("bank.py", sys.argv[1:], False, details="Sell missing item name.")
            print("Error: sell requires item name and quantity. Usage: bank.py sell <item> <qty>")
            sys.exit(1)
        if len(sys.argv) < 4:
            log_action_result("bank.py", sys.argv[1:], False, details="Sell missing quantity.")
            print("Error: sell requires a quantity. Usage: bank.py sell <item> <qty>")
            sys.exit(1)
        try:
            quantity = int(sys.argv[3])
        except ValueError:
            log_action_result("bank.py", sys.argv[1:], False, details="Sell quantity is not an integer.")
            print(f"Error: quantity must be a number, got '{sys.argv[3]}'")
            sys.exit(1)
        before = take_action_screenshot("before", f"{action_label}_{quantity}")
        ok = sell(name, quantity)
        after = take_action_screenshot("after", f"{action_label}_{quantity}")
        log_action_result("bank.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)

    elif cmd == "sellmulti":
        if len(sys.argv) < 4 or (len(sys.argv) - 2) % 2 != 0:
            log_action_result("bank.py", sys.argv[1:], False, details="sellmulti expects repeated <item> <qty> pairs.")
            print('Usage: python scripts/actions/bank.py sellmulti "<item1>" <qty1> ["<item2>" <qty2> ...]')
            sys.exit(1)
        pairs: list[tuple[str, int]] = []
        for i in range(2, len(sys.argv), 2):
            item_i = sys.argv[i]
            qty_raw = sys.argv[i + 1]
            try:
                qty_i = int(qty_raw)
            except ValueError:
                log_action_result("bank.py", sys.argv[1:], False, details=f"sellmulti quantity is not an integer: {qty_raw}")
                print(f"Error: quantity must be a number, got '{qty_raw}' for '{item_i}'")
                sys.exit(1)
            pairs.append((item_i, qty_i))
        batch_label = "batch_" + "_".join(f"{n}_{q}" for n, q in pairs)
        before = take_action_screenshot("before", f"bank_sellmulti_{batch_label}")
        ok = sell_multi(pairs)
        after = take_action_screenshot("after", f"bank_sellmulti_{batch_label}")
        log_action_result("bank.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)

    elif cmd == "equip":
        if len(sys.argv) >= 4:
            log_action_result("bank.py", sys.argv[1:], False, details="equip does not take quantity; use equipfood.")
            print("Error: equip is for weapons/armour only (no quantity). For food use:")
            print('  python scripts/actions/bank.py equipfood "<item>" [qty]')
            sys.exit(1)
        before = take_action_screenshot("before", action_label)
        ok = equip(name)
        after = take_action_screenshot("after", action_label)
        log_action_result("bank.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)

    elif cmd == "equipfood":
        quantity = None
        if len(sys.argv) >= 4:
            try:
                quantity = int(sys.argv[3])
            except ValueError:
                log_action_result("bank.py", sys.argv[1:], False, details="equipfood quantity is not an integer.")
                print(f"Error: quantity must be a number, got '{sys.argv[3]}'")
                sys.exit(1)
        qty_label = "all" if quantity is None else str(quantity)
        before = take_action_screenshot("before", f"{action_label}_{qty_label}")
        ok = equip_food(name, quantity)
        after = take_action_screenshot("after", f"{action_label}_{qty_label}")
        log_action_result("bank.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)

    elif cmd == "upgrade":
        quantity = 1
        if len(sys.argv) >= 4:
            try:
                quantity = int(sys.argv[3])
            except ValueError:
                log_action_result("bank.py", sys.argv[1:], False, details="Upgrade quantity is not an integer.")
                print(f"Error: quantity must be a number, got '{sys.argv[3]}'")
                sys.exit(1)
        before = take_action_screenshot("before", f"{action_label}_{quantity}")
        ok = upgrade(name, quantity)
        after = take_action_screenshot("after", f"{action_label}_{quantity}")
        log_action_result("bank.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)

    elif cmd == "open":
        quantity = 1
        if len(sys.argv) >= 4:
            try:
                quantity = int(sys.argv[3])
            except ValueError:
                log_action_result("bank.py", sys.argv[1:], False, details="Open quantity is not an integer.")
                print(f"Error: quantity must be a number, got '{sys.argv[3]}'")
                sys.exit(1)
        before = take_action_screenshot("before", f"{action_label}_{quantity}")
        ok = open_item(name, quantity)
        after = take_action_screenshot("after", f"{action_label}_{quantity}")
        log_action_result("bank.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)

    elif cmd == "claim":
        quantity = 1
        if len(sys.argv) >= 4:
            try:
                quantity = int(sys.argv[3])
            except ValueError:
                log_action_result("bank.py", sys.argv[1:], False, details="Claim quantity is not an integer.")
                print(f"Error: quantity must be a number, got '{sys.argv[3]}'")
                sys.exit(1)
        before = take_action_screenshot("before", f"{action_label}_{quantity}")
        ok = claim_token(name, quantity)
        after = take_action_screenshot("after", f"{action_label}_{quantity}")
        log_action_result("bank.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)

    else:
        log_action_result("bank.py", sys.argv[1:], False, details=f"Unknown command: {cmd}")
        print(
            f"Unknown command: '{cmd}'. Use 'sell', 'sellmulti', 'equip', 'equipfood', 'upgrade', 'open', or 'claim'."
        )
        sys.exit(1)
