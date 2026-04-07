#!/usr/bin/env python3
"""
farming.py — Farming actions.

Usage:
  python scripts/actions/farming.py harvest-all [allotment|herb|tree]
  python scripts/actions/farming.py compost-all [allotment|herb|tree]
  python scripts/actions/farming.py weird-gloop-all [allotment|herb|tree]
  python scripts/actions/farming.py plant-all <seed_name> [allotment|herb|tree]
  python scripts/actions/farming.py plant-all-selected [allotment|herb|tree]
  python scripts/actions/farming.py plant <seed_name> [plot] [allotment|herb|tree]
  python scripts/actions/farming.py select-seed <seed_name> [plot] [allotment|herb|tree]
  python scripts/actions/farming.py harvest [plot] [allotment|herb|tree]
  python scripts/actions/farming.py compost [plot] [allotment|herb|tree]
  python scripts/actions/farming.py weird-gloop [plot] [allotment|herb|tree]
  python scripts/actions/farming.py clear [plot] [allotment|herb|tree]
  python scripts/actions/farming.py unlock <plot> [allotment|herb|tree]

Auto-navigates to Farming if needed. Category defaults to allotment. Plot defaults to 1.

- harvest-all / compost-all / weird-gloop-all: bulk category-level actions.
- plant-all <seed>: opens Plant All modal (costs 5k GP), plants all empty plots.
- plant-all-selected: clicks Plant All Selected Crops (costs 5k GP), uses each plot's dropdown pre-selection.
- plant <seed> [plot]: plant one specific plot via the seed modal (needs 3+ seeds in bank).
- select-seed <seed> [plot]: set the dropdown pre-selection on a plot (used by plant-all-selected).
- harvest / compost / weird-gloop / clear: per-plot actions.
- unlock: unlock a locked plot by its number from 'observations/farming.py plots'.
"""

import sys, os, re
os.environ.setdefault("NODE_NO_WARNINGS", "1")
from playwright.sync_api import sync_playwright, Page
from _action_screenshots import take_action_screenshot
from _action_logging import log_action_call, log_action_result
from navigate import navigate

CDP_URL = "http://localhost:9222"

CATEGORY_LABELS = {
    "allotment": "Allotments",
    "allotments": "Allotments",
    "herb": "Herbs",
    "herbs": "Herbs",
    "tree": "Trees",
    "trees": "Trees",
}


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "melvor" in pg.url.lower():
                return pg
    return browser.contexts[0].pages[0]


def _dismiss_modal(page: Page):
    modal = page.locator("#modal-farming-seed.show")
    if modal.count() > 0 and modal.first.is_visible():
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)


def _ensure_farming_page(page: Page) -> bool:
    _dismiss_modal(page)
    if page.locator("farming-category-button").first.is_visible():
        return True
    if not navigate("farming", page=page, quiet=True):
        return False
    page.wait_for_timeout(200)
    return True


def _select_category(page: Page, category_label: str) -> bool:
    cat_btn = page.locator("farming-category-button").filter(has_text=category_label).first
    if not cat_btn.is_visible():
        print(f"Category '{category_label}' not visible.")
        return False
    cat_btn.click()
    page.wait_for_timeout(400)
    return True


def _visible_plot_indices(locator) -> list[int]:
    """Indices of elements that are visible (active farming tab only; other categories stay in the DOM)."""
    out: list[int] = []
    n = locator.count()
    for i in range(n):
        try:
            if locator.nth(i).is_visible():
                out.append(i)
        except Exception:
            continue
    return out


def _get_unlocked_plot(page: Page, plot_index: int):
    unlocked = page.locator("farming-plot:not(.d-none)")
    vis = _visible_plot_indices(unlocked)
    if plot_index < 1 or plot_index > len(vis):
        print(f"Plot {plot_index} not found (only {len(vis)} unlocked plot(s) in this category).")
        return None
    return unlocked.nth(vis[plot_index - 1])


def _parse_args(argv: list[str], cmd: str):
    """Parse optional [plot] [category] from remaining args. Returns (plot, category_label)."""
    rest = argv[2:]
    plot = 1
    category = "Allotments"
    for tok in rest:
        if tok.isdigit():
            plot = int(tok)
        elif tok.lower() in CATEGORY_LABELS:
            category = CATEGORY_LABELS[tok.lower()]
    return plot, category


def _parse_seed_args(argv: list[str]):
    """Parse <seed_name> [plot] [category] from argv[2:]. Returns (seed, plot, category)."""
    rest = argv[2:]
    seed_name = None
    plot = 1
    category = "Allotments"
    for tok in rest:
        if tok.isdigit():
            plot = int(tok)
        elif tok.lower() in CATEGORY_LABELS:
            category = CATEGORY_LABELS[tok.lower()]
        elif seed_name is None:
            seed_name = tok.lower()
    return seed_name, plot, category


def _compost_applied(plot_el) -> bool:
    span = plot_el.locator(".font-w600").first
    text = (span.text_content() or "").strip() if span.count() > 0 else ""
    return "No Compost" not in text and text != ""


def _plot_ready(plot_el) -> bool:
    btn = plot_el.locator(".btn-lg.btn-success.mr-1").first
    return btn.count() > 0 and "d-none" not in (btn.get_attribute("class") or "")


def _plot_empty(plot_el) -> bool:
    btn = plot_el.locator(".block-content .btn-success").filter(has_text="Plant a Seed").first
    return btn.count() > 0 and btn.is_visible()


def _use_seed_modal(page: Page, trigger_click, seed_name: str, context: str) -> bool:
    """
    Generic helper: click trigger_click() to open the seed modal, select seed_name, click Plant.
    trigger_click is a callable that opens the modal.
    Returns True on success.
    """
    trigger_click()
    page.wait_for_timeout(500)

    modal = page.locator("#modal-farming-seed.show")
    if modal.count() == 0 or not modal.first.is_visible():
        print(f"Seed selection modal did not open ({context}).")
        return False

    seed_btns = modal.first.locator(".btn-group-vertical button")
    count = seed_btns.count()
    if count == 0:
        print("No seeds available (need 3+ in bank). Modal is empty.")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        return False

    matched = None
    for i in range(count):
        btn = seed_btns.nth(i)
        if seed_name in (btn.text_content() or "").strip().lower():
            matched = btn
            break

    if matched is None:
        print(f"Seed '{seed_name}' not found. Available:")
        for i in range(count):
            print(f"  {(seed_btns.nth(i).text_content() or '').strip()}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        return False

    seed_label = (matched.text_content() or "").strip()
    matched.click()
    page.wait_for_timeout(300)

    plant_btn = modal.first.locator("button.btn-success").filter(has_text="Plant").first
    if plant_btn.count() == 0 or not plant_btn.is_visible():
        print("Plant confirm button did not appear after seed selection.")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        return False

    plant_btn.click()
    page.wait_for_timeout(400)
    return seed_label


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_harvest_all(page: Page, category_label: str) -> bool:
    if not _select_category(page, category_label):
        return False
    btn = page.locator("#farming-category-options button").filter(has_text="Harvest All").first
    if btn.count() == 0 or not btn.is_visible():
        print("Harvest All button not found.")
        return False

    unlocked = page.locator("farming-plot:not(.d-none)")
    vis = _visible_plot_indices(unlocked)
    ready_before = 0
    for i in vis:
        if _plot_ready(unlocked.nth(i)):
            ready_before += 1
    if ready_before == 0:
        print(f"No plots are ready to harvest in {category_label}.")
        return False

    btn.click()
    page.wait_for_timeout(400)

    ready_after = 0
    for i in vis:
        if _plot_ready(unlocked.nth(i)):
            ready_after += 1
    harvested = max(0, ready_before - ready_after)
    if harvested == 0:
        print(f"Harvest All clicked, but no plots were harvested in {category_label}.")
        return False

    print(f"Harvested {harvested} plot(s) in {category_label}.")
    return True


def _cmd_apply_all(page: Page, category_label: str, btn_class: str, substance: str) -> bool:
    """Shared logic for compost-all and weird-gloop-all."""
    if not _select_category(page, category_label):
        return False
    btn = page.locator(f"#farming-category-options button.{btn_class}").first
    if btn.count() == 0 or not btn.is_visible():
        print(f"Apply {substance} to all Plots button not found.")
        return False

    unlocked = page.locator("farming-plot:not(.d-none)")
    vis = _visible_plot_indices(unlocked)
    before = []
    for i in vis:
        span = unlocked.nth(i).locator(".font-w600").first
        text = (span.text_content() or "").strip() if span.count() > 0 else ""
        before.append("No Compost" not in text and text != "")

    btn.click()
    page.wait_for_timeout(400)

    changed = 0
    for j, i in enumerate(vis):
        span = unlocked.nth(i).locator(".font-w600").first
        text = (span.text_content() or "").strip() if span.count() > 0 else ""
        if ("No Compost" not in text and text != "") and not before[j]:
            changed += 1

    if changed == 0:
        print(f"No plots changed — you likely have no {substance} in your bank.")
        return False
    print(f"Applied {substance} to {changed} plot(s) in {category_label}.")
    return True


def cmd_compost_all(page: Page, category_label: str) -> bool:
    return _cmd_apply_all(page, category_label, "btn-warning", "Compost")


def cmd_weird_gloop_all(page: Page, category_label: str) -> bool:
    return _cmd_apply_all(page, category_label, "btn-info", "Weird Gloop")


def cmd_plant_all(argv: list[str], page: Page) -> bool:
    """Plant all empty plots via the 'Plant All' button (costs 5k GP)."""
    seed_name, _, category = _parse_seed_args(argv)
    if not seed_name:
        print("Usage: farming.py plant-all <seed_name> [allotment|herb|tree]")
        return False
    if not _select_category(page, category):
        return False

    btn = page.locator("#farming-category-options button.btn-success").first
    if btn.count() == 0 or not btn.is_visible():
        print("Plant All button not found.")
        return False

    result = _use_seed_modal(page, btn.click, seed_name, "Plant All")
    if not result:
        return False
    print(f"Planted all empty plots with {result} in {category}.")
    return True


def cmd_plant_all_selected(page: Page, category_label: str) -> bool:
    """Click 'Plant All Selected Crops' — plants each plot with its dropdown pre-selection."""
    if not _select_category(page, category_label):
        return False
    btn = page.locator("#farming-category-options button.btn-alt-success").first
    if btn.count() == 0 or not btn.is_visible():
        print("Plant All Selected Crops button not found.")
        return False

    unlocked = page.locator("farming-plot:not(.d-none)")
    vis = _visible_plot_indices(unlocked)
    empty_before = 0
    for i in vis:
        if _plot_empty(unlocked.nth(i)):
            empty_before += 1
    if empty_before == 0:
        print(f"No empty plots to plant in {category_label}.")
        return False

    btn.click()
    page.wait_for_timeout(400)

    empty_after = 0
    for i in vis:
        if _plot_empty(unlocked.nth(i)):
            empty_after += 1
    planted = max(0, empty_before - empty_after)
    if planted == 0:
        print("Plant All Selected clicked, but nothing was planted (likely missing seeds/GP or requirements).")
        return False

    print(f"Planted selected crops in {planted} plot(s) in {category_label}.")
    return True


def cmd_plant(argv: list[str], page: Page) -> bool:
    """Plant one specific plot."""
    seed_name, plot, category = _parse_seed_args(argv)
    if not seed_name:
        print("Usage: farming.py plant <seed_name> [plot] [allotment|herb|tree]")
        return False
    if not _select_category(page, category):
        return False

    plot_el = _get_unlocked_plot(page, plot)
    if plot_el is None:
        return False

    plant_btn = plot_el.locator(".block-content .btn-success").filter(has_text="Plant a Seed").first
    if plant_btn.count() == 0 or not plant_btn.is_visible():
        print(f"Plot {plot} is not empty — cannot plant.")
        return False

    result = _use_seed_modal(page, plant_btn.click, seed_name, f"plot {plot}")
    if not result:
        return False
    print(f"Planted {result} in plot {plot} ({category}).")
    return True


def cmd_select_seed(argv: list[str], page: Page) -> bool:
    """Set the dropdown pre-selection on a plot (used by plant-all-selected)."""
    seed_name, plot, category = _parse_seed_args(argv)
    if not seed_name:
        print("Usage: farming.py select-seed <seed_name> [plot] [allotment|herb|tree]")
        return False
    if not _select_category(page, category):
        return False

    plot_el = _get_unlocked_plot(page, plot)
    if plot_el is None:
        return False

    toggle = plot_el.locator(".dropdown-toggle").first
    if toggle.count() == 0:
        print(f"Seed dropdown not found on plot {plot}.")
        return False
    toggle.click()
    page.wait_for_timeout(300)

    options = plot_el.locator(".dropdown-menu .dropdown-item")
    matched = None
    for i in range(options.count()):
        opt = options.nth(i)
        if seed_name in (opt.text_content() or "").strip().lower():
            matched = opt
            break

    if matched is None:
        print(f"Seed '{seed_name}' not found in dropdown. Available:")
        for i in range(options.count()):
            print(f"  {(options.nth(i).text_content() or '').strip()}")
        toggle.click()
        return False

    label = (matched.text_content() or "").strip()

    # Read current selection before clicking
    before_src = toggle.locator("img").first.get_attribute("src") or ""

    matched.click()
    page.wait_for_timeout(300)

    # Verify selection changed
    after_src = toggle.locator("img").first.get_attribute("src") or ""
    if after_src == before_src and seed_name not in before_src.lower():
        print(f"Selection not applied — game rejected it (likely insufficient Farming level for this seed).")
        return False

    print(f"Selected {label} for plot {plot} ({category}).")
    return True


def cmd_harvest(page: Page, plot: int, category_label: str) -> bool:
    if not _select_category(page, category_label):
        return False
    plot_el = _get_unlocked_plot(page, plot)
    if plot_el is None:
        return False
    btn = plot_el.locator(".btn-lg.btn-success.mr-1").first
    if btn.count() == 0 or "d-none" in (btn.get_attribute("class") or ""):
        print(f"Plot {plot} is not ready to harvest.")
        return False
    btn.click()
    page.wait_for_timeout(400)
    print(f"Harvested plot {plot} ({category_label}).")
    return True


def _cmd_apply_plot(page: Page, plot: int, category_label: str, btn_filter: str, substance: str) -> bool:
    """Shared logic for compost and weird-gloop per-plot."""
    if not _select_category(page, category_label):
        return False
    plot_el = _get_unlocked_plot(page, plot)
    if plot_el is None:
        return False

    btn = plot_el.locator(f"button.{btn_filter}").filter(has_text=f"Apply {substance}").first
    if btn.count() == 0 or not btn.is_visible():
        if _compost_applied(plot_el):
            print(f"Plot {plot} already has something applied.")
        else:
            timer_el = plot_el.locator(".block-content small").first
            timer_text = (timer_el.text_content() or "").strip() if timer_el.count() > 0 else ""
            if "Growing:" in timer_text:
                print(f"Plot {plot} is growing — {substance} must be applied before planting.")
            else:
                print(f"Apply {substance} button not available on plot {plot}.")
        return False

    was_applied = _compost_applied(plot_el)
    btn.click()
    page.wait_for_timeout(400)

    if not _compost_applied(plot_el) and not was_applied:
        print(f"{substance} not applied — you likely have none in your bank.")
        return False

    print(f"Applied {substance} to plot {plot} ({category_label}).")
    return True


def cmd_compost(page: Page, plot: int, category_label: str) -> bool:
    return _cmd_apply_plot(page, plot, category_label, "btn-warning", "Compost")


def cmd_weird_gloop(page: Page, plot: int, category_label: str) -> bool:
    return _cmd_apply_plot(page, plot, category_label, "btn-info", "Weird Gloop")


def cmd_clear(page: Page, plot: int, category_label: str) -> bool:
    if not _select_category(page, category_label):
        return False
    plot_el = _get_unlocked_plot(page, plot)
    if plot_el is None:
        return False

    timer_el = plot_el.locator(".block-content small").first
    timer_text = (timer_el.text_content() or "").strip() if timer_el.count() > 0 else ""
    if "Growing:" in timer_text:
        print(f"Plot {plot} is still growing — use 'clear' only on dead crops.")
        return False

    btn = plot_el.locator(".btn-lg.btn-danger").first
    if btn.count() == 0 or "d-none" in (btn.get_attribute("class") or ""):
        print(f"Plot {plot} has no dead crop to clear.")
        return False
    btn.click()
    page.wait_for_timeout(400)
    print(f"Cleared dead crop from plot {plot} ({category_label}).")
    return True


def cmd_unlock(page: Page, plot: int, category_label: str) -> bool:
    if not _select_category(page, category_label):
        return False

    unlocked = page.locator("farming-plot:not(.d-none)")
    u_vis = _visible_plot_indices(unlocked)
    unlocked_count = len(u_vis)

    locked_plots = page.locator("locked-farming-plot")
    l_vis = _visible_plot_indices(locked_plots)
    total_locked = len(l_vis)

    locked_index = plot - unlocked_count - 1

    if locked_index < 0 or locked_index >= total_locked:
        if plot <= unlocked_count:
            print(f"Plot {plot} is already unlocked.")
        else:
            print(f"Plot {plot} not found ({unlocked_count} unlocked, {total_locked} locked in {category_label}).")
        return False

    locked_el = locked_plots.nth(l_vis[locked_index])
    level_el = locked_el.locator("span.text-danger").first
    gp_el = locked_el.locator(".badge-pill").first
    req_parts = []
    if level_el.count() > 0 and (t := (level_el.text_content() or "").strip()):
        req_parts.append(f"Farming {t}")
    if gp_el.count() > 0 and (t := (gp_el.text_content() or "").strip()):
        req_parts.append(f"{t} GP")

    unlock_btn = locked_el.locator("button").filter(has_text="Unlock").first
    if unlock_btn.count() == 0:
        print(f"Unlock button not found on plot {plot}.")
        return False
    if unlock_btn.is_disabled():
        print(f"Cannot unlock plot {plot} — requirements not met: {', '.join(req_parts)}.")
        return False

    unlock_btn.click()
    page.wait_for_timeout(500)
    print(f"Unlocked plot {plot} in {category_label} ({', '.join(req_parts)}).")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log_action_call("farming.py", sys.argv[1:])
    if len(sys.argv) < 2:
        log_action_result("farming.py", sys.argv[1:], False, details="Missing command.")
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()
    action_label = f"farming_{cmd}_{'_'.join(sys.argv[2:])}" if len(sys.argv) > 2 else f"farming_{cmd}"

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not _ensure_farming_page(page):
            log_action_result("farming.py", sys.argv[1:], False, details="Navigate to Farming failed.")
            print("Could not navigate to Farming.")
            sys.exit(1)
        before = take_action_screenshot("before", action_label)
        ok = False

        if cmd == "harvest-all":
            _, category = _parse_args(sys.argv, cmd)
            ok = cmd_harvest_all(page, category)

        elif cmd == "compost-all":
            _, category = _parse_args(sys.argv, cmd)
            ok = cmd_compost_all(page, category)

        elif cmd == "weird-gloop-all":
            _, category = _parse_args(sys.argv, cmd)
            ok = cmd_weird_gloop_all(page, category)

        elif cmd == "plant-all":
            ok = cmd_plant_all(sys.argv, page)

        elif cmd == "plant-all-selected":
            _, category = _parse_args(sys.argv, cmd)
            ok = cmd_plant_all_selected(page, category)

        elif cmd == "plant":
            ok = cmd_plant(sys.argv, page)

        elif cmd == "select-seed":
            ok = cmd_select_seed(sys.argv, page)

        elif cmd == "harvest":
            plot, category = _parse_args(sys.argv, cmd)
            ok = cmd_harvest(page, plot, category)

        elif cmd == "compost":
            plot, category = _parse_args(sys.argv, cmd)
            ok = cmd_compost(page, plot, category)

        elif cmd == "weird-gloop":
            plot, category = _parse_args(sys.argv, cmd)
            ok = cmd_weird_gloop(page, plot, category)

        elif cmd == "clear":
            plot, category = _parse_args(sys.argv, cmd)
            ok = cmd_clear(page, plot, category)

        elif cmd == "unlock":
            plot, category = _parse_args(sys.argv, cmd)
            ok = cmd_unlock(page, plot, category)

        else:
            log_action_result("farming.py", sys.argv[1:], False, before, None, f"Unknown command: {cmd}")
            print(f"Unknown command: '{cmd}'")
            print(__doc__)
            sys.exit(1)
        after = take_action_screenshot("after", action_label)
        log_action_result("farming.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)
