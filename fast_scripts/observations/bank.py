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
    print("  python fast_scripts/observations/bank.py items")
    print("  python fast_scripts/observations/bank.py space")
    print("  python fast_scripts/observations/bank.py info \"<item>\"")


def _print_items(result: dict) -> None:
    items = result.get("items") or []
    count = int(result.get("count") or len(items))
    print(f"Bank items: {count}\n")
    if not items:
        print("(empty)")
        return
    name_w = max(4, min(32, max(len(str(i.get("name") or "")) for i in items)))
    feature_w = max(
        7,
        max(
            len(", ".join(i.get("otherFeatures") or [])) if (i.get("otherFeatures") or []) else 1
            for i in items
        ),
    )
    print(
        f"{'Item':{name_w}}  {'Qty':>8}  {'Sell(x1)':>8}  {'Can Upgrade':>11}  {'Can Open':>8}  "
        f"{'Can Equip':>9}  {'Can Claim':>9}  {'Extra':{feature_w}}  Description"
    )
    print(
        f"{'-' * name_w}  {'-' * 8}  {'-' * 8}  {'-' * 11}  {'-' * 8}  "
        f"{'-' * 9}  {'-' * 9}  {'-' * feature_w}  {'-' * 40}"
    )
    for item in items:
        name = str(item.get("name") or "Unknown")
        qty = int(item.get("qty") or 0)
        sell_price = int(item.get("sellPrice") or 0)
        upg = "Y" if item.get("canUpgrade") else "-"
        opn = "Y" if item.get("canOpen") else "-"
        eqp = "Y" if item.get("canEquip") else "-"
        clm = "Y" if item.get("canClaim") else "-"
        extra = ", ".join(item.get("otherFeatures") or []) or "-"
        desc = str(item.get("description") or "-").replace("\n", " ")
        print(
            f"{name[:name_w]:{name_w}}  {qty:>8,}  {sell_price:>8,}  {upg:>11}  {opn:>8}  "
            f"{eqp:>9}  {clm:>9}  {extra:{feature_w}}  {desc}"
        )


def _print_space(result: dict) -> None:
    used = int(result.get("used") or 0)
    max_slots = int(result.get("max") or 0)
    if max_slots > 0:
        print(f"Bank space: {used}/{max_slots} ({(used / max_slots) * 100:.1f}% used)")
    else:
        print(f"Bank space: {used}/{max_slots}")


def _print_info(result: dict) -> None:
    item = result.get("item") if isinstance(result.get("item"), dict) else result
    if not isinstance(item, dict):
        print("Item not found.")
        return
    print(f"Item: {item.get('name', 'Unknown')}")
    print(f"Bank Qty: {int(item.get('qty', 0)):,}")
    print(f"Type: {item.get('typeName', 'Item')}")
    slots = item.get("slots", [])
    if slots:
        print(f"Equip Slots: {', '.join(str(s) for s in slots)}")
    reqs = item.get("equipRequirements", [])
    if reqs:
        print(f"Equip Requirements: ({'; '.join(str(r) for r in reqs)})")
    elif slots:
        print("Equip Requirements: (none)")
    desc = str(item.get("description") or "").strip()
    if desc:
        print(f"Description: {desc}")
    else:
        print("Description: (no text from game — item may use icons-only or wiki for details)")
    heal = item.get("foodHealing")
    if isinstance(heal, (int, float)) and float(heal) > 0:
        heal_val = float(heal)
        # Normalize to in-game displayed HP values.
        heal_val *= 10
        heal_txt = int(round(heal_val)) if abs(heal_val - round(heal_val)) < 1e-9 else heal_val
        print(f"Food Heal: {heal_txt}")
    stats = item.get("equipmentStats", [])
    if stats:
        print("Equipment Stats:")
        for s in stats:
            stat = str(s.get("stat", "Unknown"))
            val = s.get("value")
            is_pct = bool(s.get("isPercent", False))
            if isinstance(val, (int, float)):
                if is_pct:
                    val_txt = f"{val:+g}%"
                elif val == int(val) and abs(val) < 1e9:
                    val_txt = f"{int(val):+,}"
                else:
                    val_txt = f"{val:+g}"
            else:
                val_txt = str(val)
            print(f"  {stat}: {val_txt}")
    else:
        print("Equipment Stats: (none)")
    upgrades = item.get("upgrades", [])
    if upgrades:
        print("Upgrades:")
        for u in upgrades:
            target = str(u.get("target", "Unknown"))
            max_qty = u.get("maxQty")
            max_txt = "?" if max_qty is None else f"{int(max_qty):,}"
            print(f"  -> {target} (max now: {max_txt})")
            costs = []
            for c in u.get("itemCosts", []) or []:
                q = int(c.get("quantity", 0))
                n = str(c.get("name", "Unknown Item"))
                costs.append(f"{q:,}x {n}")
            for c in u.get("currencyCosts", []) or []:
                q = int(c.get("quantity", 0))
                n = str(c.get("name", "Currency"))
                costs.append(f"{q:,} {n}")
            if costs:
                print(f"     Requires: {', '.join(costs)}")
            else:
                print("     Requires: (none)")
    else:
        print("Upgrades: (none)")
    tags = []
    if item.get("canEquip"):
        tags.append("Equipable")
    if item.get("canClaim"):
        tags.append("Claimable")
    if item.get("canOpen"):
        tags.append("Openable")
    if tags:
        print(f"Features: {', '.join(tags)}")


def format_output(cmd: str, result: dict, argv: list[str] | None = None) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        if cmd == "items":
            _print_items(result)
        elif cmd == "space":
            _print_space(result)
        elif cmd == "info":
            _print_info(result)
    return buf.getvalue().rstrip("\n")


def main() -> int:
    if len(sys.argv) < 2:
        _usage()
        return 1
    cmd = sys.argv[1].strip().lower()
    args = [cmd]
    if cmd == "info":
        if len(sys.argv) < 3:
            _usage()
            return 1
        args.extend(sys.argv[2:])
    elif cmd not in {"items", "space"}:
        _usage()
        return 1

    log_observation("bank", args)
    try:
        resp = daemon_send({"op": "observation.call", "name": "bank", "args": args})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2

    if not resp.get("ok"):
        if cmd == "info":
            result = resp.get("result") or {}
            err = str(result.get("error") or resp.get("error") or "")
            if err == "not_found":
                query = " ".join(sys.argv[2:]).strip()
                print(f"Item not found in bank: '{query}'")
                return 1
            if err == "ambiguous":
                names = ", ".join(result.get("matches") or [])
                query = " ".join(sys.argv[2:]).strip()
                print(f"Ambiguous item '{query}'. Matches: {names}")
                return 1
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1

    result = resp.get("result") or {}
    out = format_output(cmd, result, args)
    log_observation_result("bank", args, True, result=result, details=out)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
