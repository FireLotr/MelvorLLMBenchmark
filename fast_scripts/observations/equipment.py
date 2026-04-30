#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _daemon_client import daemon_send
from _logging import log_observation, log_observation_result


def _usage() -> None:
    print("Usage:")
    print("  python fast_scripts/observations/equipment.py all")
    print("  python fast_scripts/observations/equipment.py equipped")


def _pretty_slot(slot_id: str) -> str:
    if not slot_id:
        return "Unknown"
    name = slot_id.split(":")[-1]
    return name.replace("_", " ")


def _is_empty_item(item_id: str, qty: int) -> bool:
    return (not item_id) or item_id.endswith("Empty_Equipment") or item_id.endswith("Empty_Food") or qty <= 0


def _print_table(rows: list[dict]) -> None:
    print(f"{'Slot':24} {'Item':30} {'Qty':>8}")
    print("-" * 66)
    for r in rows:
        print(f"{r['slot'][:24]:24} {r['item'][:30]:30} {r['qty']:>8,}")


def _print_equipment(result: dict, mode: str) -> None:
    equipment_rows = []
    for row in result.get("equipment", []):
        slot = _pretty_slot(row.get("slotID", ""))
        item_id = row.get("itemID", "")
        qty = int(row.get("qty", 0))
        is_empty = _is_empty_item(item_id, qty)
        if mode == "equipped" and is_empty:
            continue
        equipment_rows.append(
            {"slot": slot, "item": "Empty" if is_empty else row.get("itemName", "Unknown"), "qty": 0 if is_empty else qty}
        )

    food_rows = []
    for row in result.get("food", []):
        slot = _pretty_slot(row.get("slotID", ""))
        item_id = row.get("itemID", "")
        qty = int(row.get("qty", 0))
        is_empty = _is_empty_item(item_id, qty)
        if mode == "equipped" and is_empty:
            continue
        food_rows.append(
            {"slot": slot, "item": "Empty" if is_empty else row.get("itemName", "Unknown"), "qty": 0 if is_empty else qty}
        )

    if not equipment_rows and not food_rows:
        print("No equipped gear or food.")
        return

    if equipment_rows:
        _print_table(equipment_rows)

    if food_rows:
        print("\nFood slots:\n")
        _print_table(food_rows)


def format_output(cmd: str, result: dict, argv: list[str] | None = None) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        _print_equipment(result, cmd)
    return buf.getvalue().rstrip("\n")


def main() -> int:
    if len(sys.argv) < 2:
        _usage()
        return 1
    cmd = sys.argv[1].strip().lower()
    if cmd not in {"all", "equipped"}:
        _usage()
        return 1
    try:
        log_observation("equipment", [cmd])
        resp = daemon_send({"op": "observation.call", "name": "equipment", "args": [cmd]})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    result = resp.get("result") or {}
    out = format_output(cmd, result, [cmd])
    log_observation_result("equipment", [cmd], True, result=result, details=out)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
