#!/usr/bin/env python3
"""
equipment.py — Read-only equipment observations.

Usage:
  python scripts/observations/equipment.py all       # all equipment + food slots
  python scripts/observations/equipment.py equipped  # only non-empty equipment + food slots
"""

import sys
import os

os.environ.setdefault("NODE_NO_WARNINGS", "1")
from playwright.sync_api import sync_playwright
from _observation_logging import log_observation, run_observation

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
        page.wait_for_function("() => typeof game !== 'undefined' && !!game.combat?.player", timeout=10000)
        return True
    except Exception:
        return False


def _pretty_slot(slot_id: str) -> str:
    if not slot_id:
        return "Unknown"
    name = slot_id.split(":")[-1]
    return name.replace("_", " ")


def _is_empty_item(item_id: str, qty: int) -> bool:
    return (not item_id) or item_id.endswith("Empty_Equipment") or item_id.endswith("Empty_Food") or qty <= 0


def read_equipment(mode: str) -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False

        data = page.evaluate(
            """() => {
                const p = game.combat.player;
                const eq = (p.equipment?.equippedArray ?? []).map((e) => ({
                    slotID: e?.slot?.id ?? "",
                    itemID: e?.item?.id ?? "",
                    itemName: e?.item?.name ?? "",
                    qty: Number(e?.quantity ?? 0),
                }));
                const food = (p.food?.slots ?? []).map((f, i) => ({
                    slotID: `Food_${i + 1}`,
                    itemID: f?.item?.id ?? "",
                    itemName: f?.item?.name ?? "",
                    qty: Number(f?.quantity ?? 0),
                }));
                let activeFoodSlot = null;
                const asSlotNum = (v) => {
                    const n = Number(v);
                    if (Number.isFinite(n) && n >= 0 && n < 3) return n + 1;
                    if (Number.isFinite(n) && n >= 1 && n <= 3) return n;
                    return null;
                };
                for (const v of [p.food?.selectedSlot, p.food?.currentSlot, p.food?.activeSlot]) {
                    const s = asSlotNum(v);
                    if (s) { activeFoodSlot = s; break; }
                }
                if (!activeFoodSlot) {
                    const sid = String(p?.selectedFood?.slot?.id ?? p?.selectedFood?.slotID ?? "");
                    const m = sid.match(/(\\d+)/);
                    if (m) {
                        const n = Number(m[1]);
                        if (Number.isFinite(n) && n >= 1 && n <= 3) activeFoodSlot = n;
                    }
                }
                return { ok: true, equipment: eq, food, activeFoodSlot };
            }"""
        )

    if not data.get("ok"):
        print("Failed to read equipment.")
        return False

    equipment_rows = []
    for row in data.get("equipment", []):
        slot = _pretty_slot(row.get("slotID", ""))
        item_id = row.get("itemID", "")
        qty = int(row.get("qty", 0))
        is_empty = _is_empty_item(item_id, qty)
        if mode == "equipped" and is_empty:
            continue
        equipment_rows.append(
            {
                "slot": slot,
                "item": "Empty" if is_empty else row.get("itemName", "Unknown"),
                "qty": 0 if is_empty else qty,
            }
        )

    food_rows = []
    for row in data.get("food", []):
        slot = _pretty_slot(row.get("slotID", ""))
        item_id = row.get("itemID", "")
        qty = int(row.get("qty", 0))
        is_empty = _is_empty_item(item_id, qty)
        if mode == "equipped" and is_empty:
            continue
        food_rows.append(
            {
                "slot": slot,
                "item": "Empty" if is_empty else row.get("itemName", "Unknown"),
                "qty": 0 if is_empty else qty,
            }
        )

    if not equipment_rows and not food_rows:
        print("No equipped gear or food.")
        return True

    if equipment_rows:
        print("Equipment:\n")
        print(f"{'Slot':24} {'Item':30} {'Qty':>8}")
        print("-" * 66)
        for r in equipment_rows:
            print(f"{r['slot'][:24]:24} {r['item'][:30]:30} {r['qty']:>8,}")

    if food_rows:
        print("\nFood slots:\n")
        print(f"{'Slot':24} {'Item':30} {'Qty':>8}")
        print("-" * 66)
        for r in food_rows:
            print(f"{r['slot'][:24]:24} {r['item'][:30]:30} {r['qty']:>8,}")
        active = data.get("activeFoodSlot")
        if isinstance(active, (int, float)) and 1 <= int(active) <= 3:
            print(f"\nActive Food Slot: {int(active)}")
        else:
            print("\nActive Food Slot: unknown")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log_observation("equipment.py", sys.argv[1:], False, "Missing command.")
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower().strip()
    if cmd == "all":
        ok, out = run_observation(read_equipment, "all")
        log_observation("equipment.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    elif cmd == "equipped":
        ok, out = run_observation(read_equipment, "equipped")
        log_observation("equipment.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    else:
        log_observation("equipment.py", sys.argv[1:], False, f"Unknown command: {cmd}")
        print(f"Unknown command: '{cmd}'. Use 'all' or 'equipped'.")
        sys.exit(1)
