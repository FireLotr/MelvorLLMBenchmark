#!/usr/bin/env python3
"""
observations/farming.py — Read-only farming state.

Usage:
  python scripts/observations/farming.py plots

Works from any page (navigates to Farming internally if needed).
"""

import sys, os, re
from datetime import datetime, timedelta
os.environ.setdefault("NODE_NO_WARNINGS", "1")
from playwright.sync_api import sync_playwright, Page
from _navigate import navigate
from _observation_logging import log_observation, run_observation

CDP_URL = "http://localhost:9222"

CATEGORIES = ["Allotments", "Herbs", "Trees"]


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "melvor" in pg.url.lower():
                return pg
    return browser.contexts[0].pages[0]


def _parse_finish_time(timer_text: str) -> str:
    """Parse 'About X mins' / 'X mins Y secs' etc into a wall-clock finish time string."""
    total_seconds = 0
    # Hours
    m = re.search(r"(\d+)\s*hour", timer_text, re.I)
    if m:
        total_seconds += int(m.group(1)) * 3600
    # Minutes
    m = re.search(r"(\d+)\s*min", timer_text, re.I)
    if m:
        total_seconds += int(m.group(1)) * 60
    # Seconds
    m = re.search(r"(\d+)\s*sec", timer_text, re.I)
    if m:
        total_seconds += int(m.group(1))

    if total_seconds == 0:
        return ""
    finish = datetime.now() + timedelta(seconds=total_seconds)
    return finish.strftime("%H:%M")


def _seed_name_from_src(src: str) -> str:
    """Extract crop name from an image src, e.g. '...seeds_potato.png' -> 'Potato'."""
    if not src:
        return "?"
    filename = src.split("/")[-1]
    name = re.sub(r"^seeds_", "", filename)
    name = re.sub(r"\.\w+$", "", name)
    name = name.replace("_", " ").title()
    return name or "?"


def _dismiss_modal(page: Page):
    modal = page.locator("#modal-farming-seed.show")
    if modal.count() > 0 and modal.first.is_visible():
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)


def _visible_plot_indices(locator) -> list[int]:
    """Indices of elements that are actually visible (only the active farming category tab)."""
    out: list[int] = []
    n = locator.count()
    for i in range(n):
        try:
            if locator.nth(i).is_visible():
                out.append(i)
        except Exception:
            continue
    return out


def _ensure_farming_page(page: Page) -> bool:
    _dismiss_modal(page)
    if page.locator("farming-category-button").first.is_visible():
        return True
    if not navigate("farming", page=page, quiet=True):
        return False
    page.wait_for_timeout(200)
    return True


def _read_plots_for_category(page: Page, category: str) -> list:
    # Build action metadata by product and action name for XP/interval enrichment.
    action_meta = page.evaluate(
        """() => {
            const f = game?.farming;
            const rows = (f?.actions?.allObjects ?? []).map(a => ({
                actionName: a?.name ?? null,
                productName: a?.product?.name ?? null,
                category: a?.category?.name ?? a?.category?.id ?? null,
                xp: Number(a?.baseExperience ?? 0),
                intervalMs: Number(a?.baseInterval ?? 0),
            }));
            const byProduct = {};
            const byAction = {};
            for (const r of rows) {
                if (r.productName) byProduct[r.productName] = r;
                if (r.actionName) byAction[r.actionName] = r;
            }
            return { byProduct, byAction };
        }"""
    )

    def _norm(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (name or "").lower())

    def _find_meta(name: str):
        if not name:
            return None
        by_product = action_meta.get("byProduct", {})
        by_action = action_meta.get("byAction", {})
        # Exact first
        if name in by_product:
            return by_product[name]
        if name in by_action:
            return by_action[name]

        key = _norm(name)
        candidates = []
        for src in (by_product, by_action):
            for k, v in src.items():
                nk = _norm(k)
                if not nk:
                    continue
                if nk == key:
                    return v
                if nk.startswith(key) or key.startswith(nk) or key in nk or nk in key:
                    candidates.append(v)
        if candidates:
            return candidates[0]
        # simple singular/plural fallback
        if key.endswith("s"):
            key2 = key[:-1]
        else:
            key2 = key + "s"
        for src in (by_product, by_action):
            for k, v in src.items():
                if _norm(k) == key2:
                    return v
        return None

    cat_btn = page.locator("farming-category-button").filter(has_text=category).first
    if not cat_btn.is_visible():
        return []
    cat_btn.click()
    page.wait_for_timeout(400)

    plots = []

    # Unlocked plots in the *active* category only (other tabs stay in the DOM).
    unlocked = page.locator("farming-plot:not(.d-none)")
    for plot_i, dom_i in enumerate(_visible_plot_indices(unlocked), start=1):
        p = unlocked.nth(dom_i)

        seed_img = p.locator(".dropdown-toggle img").first
        seed = _seed_name_from_src(seed_img.get_attribute("src") or "") if seed_img.count() > 0 else "?"

        crop_img = p.locator("img.skill-icon-sm").first
        timer_el = p.locator(".block-content small").first
        plant_btn = p.locator(".block-content .btn-success").first
        harvest_btn = p.locator(".btn-lg.btn-success.mr-1").first

        has_crop = crop_img.count() > 0 and "d-none" not in (crop_img.get_attribute("class") or "")
        timer_text = (timer_el.text_content() or "").strip() if timer_el.count() > 0 else ""
        harvest_visible = harvest_btn.count() > 0 and "d-none" not in (harvest_btn.get_attribute("class") or "")
        plant_visible = plant_btn.count() > 0 and "d-none" not in (plant_btn.get_attribute("class") or "")

        # Empty before timer: Melvor may leave stale "Growing:" text on `small` after a clear/harvest
        # while the crop icon is hidden and Plant is shown.
        if harvest_visible:
            state = "ready"
        elif not has_crop and plant_visible:
            state = "empty"
        elif has_crop and "Growing:" in timer_text:
            time_left = timer_text.split("Time Left:")[-1].strip() if "Time Left:" in timer_text else timer_text
            finish = _parse_finish_time(time_left)
            state = f"growing ({time_left}, ready ~{finish})" if finish else f"growing ({time_left})"
        else:
            state = "dead"

        compost_span = p.locator(".font-w600").first
        compost_text = (compost_span.text_content() or "").strip() if compost_span.count() > 0 else "?"
        compost = "none" if "No Compost" in compost_text else (compost_text or "none")

        planted = "—"
        if has_crop:
            planted_src = crop_img.get_attribute("src") or ""
            planted = _seed_name_from_src(planted_src) if planted_src else seed

        plots.append({
            "index": plot_i,
            "locked": False,
            "state": state,
            "selected_seed": seed,
            "planted": planted,
            "compost": compost,
            "xp": 0,
            "intervalMs": 0,
        })

        # Attach XP/interval metadata where possible.
        key = planted if planted and planted != "—" else seed
        meta = _find_meta(key)
        if meta:
            plots[-1]["xp"] = int(meta.get("xp", 0))
            plots[-1]["intervalMs"] = int(meta.get("intervalMs", 0))

    # Locked plots visible for this category only
    locked_els = page.locator("locked-farming-plot")
    for dom_i in _visible_plot_indices(locked_els):
        l = locked_els.nth(dom_i)

        level_el = l.locator("span.text-danger").first
        level_req = (level_el.text_content() or "").strip() if level_el.count() > 0 else ""

        gp_el = l.locator(".badge-pill").first
        gp_req = (gp_el.text_content() or "").strip() if gp_el.count() > 0 else ""

        unlock_btn = l.locator("button").first
        can_unlock = unlock_btn.count() > 0 and not unlock_btn.is_disabled()

        req_parts = []
        if level_req:
            req_parts.append(f"Farming {level_req}")
        if gp_req:
            req_parts.append(f"{gp_req} GP")

        plots.append({
            "index": len(plots) + 1,
            "locked": True,
            "state": "locked",
            "requirements": ", ".join(req_parts) if req_parts else "?",
            "can_unlock": can_unlock,
        })

    return plots


def cmd_plots():
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not _ensure_farming_page(page):
            print("Could not navigate to Farming.")
            return False

        for category in CATEGORIES:
            plots = _read_plots_for_category(page, category)
            if not plots:
                print(f"\n{category}: (not available)")
                continue

            print(f"\n{category} ({len(plots)} plots):")
            for p in plots:
                if p["locked"]:
                    unlock_str = " [can unlock]" if p.get("can_unlock") else ""
                    print(f"  Plot {p['index']}: LOCKED — requires {p['requirements']}{unlock_str}")
                else:
                    compost_str = f"compost: {p['compost']}"
                    interval_str = f"{(int(p.get('intervalMs', 0)) / 3600000):.1f}h" if p.get("intervalMs", 0) else "?"
                    xp_str = f"{int(p.get('xp', 0))} XP" if p.get("xp", 0) else "? XP"
                    s = p["state"]
                    if s == "empty":
                        print(
                            f"  Plot {p['index']}: empty            | {compost_str} | "
                            f"selected seed: {p['selected_seed']} | {xp_str} | {interval_str}"
                        )
                    elif s.startswith("growing"):
                        print(
                            f"  Plot {p['index']}: {s:<24} | {compost_str} | "
                            f"{p['planted']} | {xp_str} | {interval_str}"
                        )
                    elif s == "ready":
                        print(f"  Plot {p['index']}: READY TO HARVEST  | {p['planted']} | {xp_str} | {interval_str}")
                    elif s == "dead":
                        print(f"  Plot {p['index']}: DEAD (clear it)   | {p['planted']} | {xp_str} | {interval_str}")
                    else:
                        print(f"  Plot {p['index']}: {s}")
        print()
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "plots":
        log_observation("farming.py", sys.argv[1:], False, "Unknown/missing command.")
        print(__doc__)
        sys.exit(1)
    ok, out = run_observation(cmd_plots)
    log_observation("farming.py", sys.argv[1:], ok, out)
