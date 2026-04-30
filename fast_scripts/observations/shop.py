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
    print("  python fast_scripts/observations/shop.py list")
    print("  python fast_scripts/observations/shop.py category <category>")
    print("  python fast_scripts/observations/shop.py currency")


def _print_available_categories(result: dict) -> None:
    categories = result.get("categories") or []
    if not categories:
        print("Available categories: (none)")
        return
    print("Available categories:")
    for c in categories:
        print(f"- {c}")


def _print_currency(result: dict) -> None:
    print(f"GP: {int(result.get('gp') or 0):,}")
    print(f"Slayer Coins: {int(result.get('slayerCoins') or 0):,}")


def _print_list(result: dict) -> None:
    print(f"Current shop buy quantity: {int(result.get('buyQuantity') or 1)}")
    _print_currency(result)
    rows = result.get("rows") or []
    categories = result.get("categories") or []
    for category in categories:
        cat_rows = [r for r in rows if str(r.get("category") or "") == category]
        if not cat_rows:
            continue
        print(f"\n[{category}]")
        print("Name | Price (x1) | Can Buy")
        print("-" * 120)
        for r in cat_rows:
            can_buy = "yes" if r.get("canBuy1x") else "no"
            print(f"{r.get('name', 'Unknown')} | {r.get('price1x', 'Unknown')} | {can_buy}")
            reqs = r.get("requirements") or []
            if reqs:
                print(f"  Requires: {'; '.join(reqs)}")
            desc = str(r.get("description") or "").strip()
            if desc:
                print(f"  {desc}")


def _print_category(result: dict, requested_category: str) -> int:
    categories = result.get("categories") or []
    rows = result.get("rows") or []
    by_norm = {str(c).strip().lower(): c for c in categories}
    hit = by_norm.get(requested_category.strip().lower())
    if not hit:
        print(f"Unknown category: '{requested_category}'")
        print("Available categories:")
        for c in categories:
            print(f"- {c}")
        return 1
    print(f"Category: {hit}")
    print("Name | Price (x1) | Can Buy")
    print("-" * 120)
    for r in rows:
        if str(r.get("category") or "") != hit:
            continue
        reqs = r.get("requirements") or []
        can_buy = "yes" if r.get("canBuy1x") else "no"
        print(f"{r.get('name', 'Unknown')} | {r.get('price1x', 'Unknown')} | {can_buy}")
        if reqs:
            print(f"  Requires: {'; '.join(reqs)}")
        desc = str(r.get("description") or "").strip()
        if desc:
            print(f"  {desc}")
    return 0


def format_output(cmd: str, result: dict, argv: list[str] | None = None) -> tuple[str, int]:
    buf = StringIO()
    rc = 0
    with redirect_stdout(buf):
        if cmd == "currency":
            _print_currency(result)
        elif cmd == "category":
            requested_category = " ".join((argv or [])[1:]).strip()
            rc = _print_category(result, requested_category)
        else:
            _print_list(result)
    return buf.getvalue().rstrip("\n"), rc


def main() -> int:
    if len(sys.argv) < 2:
        _usage()
        return 1
    cmd = sys.argv[1].strip().lower()
    if cmd not in {"list", "category", "currency"}:
        print(f"Unknown command: '{cmd}'")
        _usage()
        return 1
    category_arg = ""
    if cmd == "category":
        if len(sys.argv) < 3:
            print("Missing category name.")
            try:
                resp = daemon_send({"op": "observation.call", "name": "shop", "args": ["category"]})
                if resp.get("ok"):
                    _print_available_categories(resp.get("result") or {})
            except Exception:
                pass
            _usage()
            return 1
        category_arg = " ".join(sys.argv[2:]).strip()
    log_args = [cmd]
    if cmd == "category" and category_arg:
        log_args.extend(category_arg.split())
    try:
        log_observation("shop", log_args)
        resp = daemon_send({"op": "observation.call", "name": "shop", "args": [cmd]})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    result = resp.get("result") or {}
    out, rc = format_output(cmd, result, log_args)
    log_observation_result("shop", log_args, rc == 0, result=result, details=out)
    if out:
        print(out)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
