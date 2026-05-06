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


def _allowed_demo_dungeons() -> set[str] | None:
    cfg_path = Path(__file__).resolve().parents[2] / "lists.json"
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        dungeons = data.get("dungeons")
        if not isinstance(dungeons, list):
            return None
        return {str(d).strip().lower() for d in dungeons if str(d).strip()}
    except Exception:
        return None


def _usage() -> None:
    print("Usage:")
    print("  python fast_scripts/observations/combat.py style")
    print("  python fast_scripts/observations/combat.py hp")
    print("  python fast_scripts/observations/combat.py autoeat")
    print("  python fast_scripts/observations/combat.py food_slot")
    print("  python fast_scripts/observations/combat.py stats")
    print("  python fast_scripts/observations/combat.py enemy")
    print("  python fast_scripts/observations/combat.py current_loot")
    print("  python fast_scripts/observations/combat.py full_status")
    print("  python fast_scripts/observations/combat.py dungeon_completion")
    print("  python fast_scripts/observations/combat.py drops all")
    print("  python fast_scripts/observations/combat.py drops monster \"<name>\"")
    print("  python fast_scripts/observations/combat.py drops dungeon \"<name>\"")


def _fmt_qty(min_qty, max_qty) -> str:
    if min_qty is None and max_qty is None:
        return "?"
    if min_qty == max_qty:
        return str(min_qty)
    return f"{min_qty}-{max_qty}"


def _print_style(result: dict) -> None:
    print(f"Style: {result.get('style') or 'Unknown'}")
    at = result.get("attackType")
    if at:
        print(f"Attack Type: {at}")


def _print_hp(result: dict) -> None:
    print(f"HP: {int(result.get('hp') or 0)}/{int(result.get('maxHp') or 0)}")


def _print_autoeat(result: dict) -> None:
    print(f"Auto Eat Trigger: {int(result.get('autoEatThreshold') or 0)}")
    print(f"Auto Eat Target: {int(result.get('autoEatHPLimit') or 0)}")


def _print_food_slot(result: dict) -> None:
    if not result.get("ok", True):
        print(result.get("error") or "Could not read active food slot.")
        return
    slot = result.get("activeFoodSlot")
    qty = result.get("activeFoodQty")
    if isinstance(slot, (int, float)):
        print(f"Active Food Slot: {int(slot)}")
        if isinstance(qty, (int, float)):
            print(f"Active Food Qty: {int(qty)}")
        else:
            print("Active Food Qty: unavailable")
    else:
        print("Active Food Slot: unavailable")


def _print_stats(result: dict) -> None:
    if not result.get("ok", True):
        err = result.get("error") or "unknown_error"
        print(f"Error: {err}")
        return
    print(f"Min Hit: {int(result.get('minHit') or 0)}")
    print(f"Max Hit: {int(result.get('maxHit') or 0)}")
    print(f"Accuracy: {int(result.get('accuracy') or 0)}")
    hit_chance = result.get("hitChance")
    target = result.get("hitChanceTarget")
    in_combat = bool(result.get("hitChanceInCombat"))
    if isinstance(hit_chance, (int, float)):
        suffix = f" ({target})" if isinstance(target, str) and target.strip() else ""
        if not in_combat and suffix:
            suffix = f"{suffix} [last target]"
        print(f"Hit Chance: {float(hit_chance):.2f}%{suffix}")
    else:
        if not in_combat:
            print("Hit Chance: unavailable (no target)")
        elif isinstance(target, str) and target.strip():
            print(f"Hit Chance: unavailable ({target})")
        else:
            print("Hit Chance: unavailable (no target)")
    print(
        "Evasion (M/R/M): "
        f"{int(result.get('evasionMelee') or 0)} / "
        f"{int(result.get('evasionRanged') or 0)} / "
        f"{int(result.get('evasionMagic') or 0)}"
    )
    dr = result.get("damageReduction")
    if isinstance(dr, (int, float)):
        print(f"Damage Reduction: {float(dr):.2f}%")
    else:
        print("Error: damage_reduction_unavailable")
def _print_enemy(result: dict) -> None:
    if not result.get("ok", True):
        print(result.get("error") or "Not currently in combat.")
        return
    print(f"Enemy: {result.get('name') or 'Unknown'}")
    print(f"HP: {int(result.get('hp') or 0)}/{int(result.get('maxHp') or 0)}")
    at = result.get("attackType")
    if at:
        print(f"Attack Type: {at}")
    sas = result.get("specialAttacks")
    if isinstance(sas, list):
        if sas:
            print("Special Attacks:")
            for sa in sas:
                if not isinstance(sa, dict):
                    continue
                sid = sa.get("id")
                nm = str(sa.get("name") or ("Unknown" if not sid else f"Unknown ({sid})"))
                ch = sa.get("chance")
                if isinstance(ch, (int, float)):
                    print(f"- {nm} ({float(ch):.2f}% chance)")
                else:
                    print(f"- {nm}")
                desc = sa.get("description")
                if isinstance(desc, str) and desc.strip():
                    d = desc.strip().replace("\n", " ")
                    if len(d) > 160:
                        d = d[:157] + "..."
                    print(f"  {d}")
        else:
            print("Special Attacks: (none)")
    print(f"Enemy Min/Max Hit: {int(result.get('minHit') or 0)} / {int(result.get('maxHit') or 0)}")
    print(f"Enemy Accuracy: {int(result.get('accuracy') or 0)}")
    print(f"Enemy Defence: {int(result.get('defenceLevel') or 0)}")
    print(
        "Enemy Evasion (M/R/M): "
        f"{int(result.get('evasionMelee') or 0)} / "
        f"{int(result.get('evasionRanged') or 0)} / "
        f"{int(result.get('evasionMagic') or 0)}"
    )
    edr = result.get("damageReduction")
    if isinstance(edr, (int, float)):
        print(f"Enemy Damage Reduction: {float(edr):.2f}%")
    enemy_hit = result.get("enemyHitChance")
    if isinstance(enemy_hit, (int, float)):
        print(f"Enemy Hit Chance vs You: {float(enemy_hit):.2f}%")
    hit = result.get("playerHitChance")
    if isinstance(hit, (int, float)):
        print(f"Your Hit Chance vs Enemy: {float(hit):.2f}%")


def _print_dungeon_completion(result: dict) -> None:
    rows = result.get("rows") or []
    allowed = _allowed_demo_dungeons()
    if allowed:
        rows = [r for r in rows if str(r.get("name") or "").strip().lower() in allowed]
    if not rows:
        print("Dungeon completion: (none)")
        return
    print("Dungeon completion counts:")
    for r in rows:
        print(f"- {r.get('name', 'Unknown')}: {int(r.get('completions') or 0)}")


def _print_drops(result: dict) -> None:
    mode = (result.get("mode") or "").lower()
    if mode == "all":
        monsters = result.get("monsters") or []
        dungeons = result.get("dungeons") or []
        print("=== Monster Drops ===")
        for mon in sorted(monsters, key=lambda m: str(m.get("name") or "")):
            print(f"Monster: {mon.get('name', 'Unknown')}")
            drops = mon.get("drops") or []
            if not drops:
                print("Possible Drops: none\n")
                continue
            print("Possible Drops:")
            for d in drops:
                qty = _fmt_qty(d.get("min"), d.get("max"))
                src = d.get("source", "drop")
                print(f"- {d.get('name', 'Unknown')} x{qty} [{src}]")
            print()

        print("=== Dungeon Drops ===")
        for dun in sorted(dungeons, key=lambda d: str(d.get("name") or "")):
            print(f"Dungeon: {dun.get('name', 'Unknown')}")
            drops = dun.get("drops") or []
            if not drops:
                print("Possible Drops: none\n")
                continue
            print("Possible Drops:")
            for d in drops:
                qty = _fmt_qty(d.get("min"), d.get("max"))
                src = d.get("source", "reward")
                print(f"- {d.get('name', 'Unknown')} x{qty} [{src}]")
            print()
        return
    matches = result.get("matches") or []
    if not matches:
        print("No matches.")
        return
    row = matches[0]
    label = "Monster" if mode == "monster" else "Dungeon"
    print(f"{label}: {row.get('name', 'Unknown')}")
    drops = row.get("drops") or []
    if not drops:
        print("Possible Drops: none")
        return
    print("Possible Drops:")
    for d in drops:
        qty = _fmt_qty(d.get("min"), d.get("max"))
        src = d.get("source", "drop")
        print(f"- {d.get('name', 'Unknown')} x{qty} [{src}]")


def _print_current_loot(result: dict) -> None:
    if not result.get("ok", True):
        print(result.get("error") or "Could not read current loot.")
        return
    occupied = result.get("occupied_slots")
    free = result.get("free_slots")
    max_slots = result.get("max_slots")
    if isinstance(occupied, (int, float)):
        if isinstance(free, (int, float)) and isinstance(max_slots, (int, float)):
            print(f"Loot slots: {int(occupied)} occupied, {int(free)} free (max {int(max_slots)})")
        elif isinstance(free, (int, float)):
            print(f"Loot slots: {int(occupied)} occupied, {int(free)} free")
        else:
            print(f"Loot slots occupied: {int(occupied)}")
            if result.get("max_slots_unknown"):
                print("Loot capacity: max/free unknown (native loot object has no usable max slot field)")
    loot = result.get("current_loot") or []
    if not loot:
        print("Current Loot: (empty)")
        return
    print("Current Loot:")
    for entry in loot:
        name = str((entry or {}).get("name") or "Unknown")
        qty = (entry or {}).get("qty")
        if isinstance(qty, (int, float)):
            print(f"- {name} x{int(qty)}")
        else:
            print(f"- {name}")


def _print_full_status(result: dict) -> None:
    _print_style(result.get("style") or {})
    _print_hp(result.get("hp") or {})
    _print_autoeat(result.get("autoeat") or {})
    _print_food_slot(result.get("food_slot") or {})
    _print_stats(result.get("stats") or {})
    _print_enemy(result.get("enemy") or {})
    _print_current_loot(result.get("current_loot") or {})


def format_output(cmd: str, result: dict, argv: list[str] | None = None) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        if cmd == "style":
            _print_style(result)
        elif cmd == "hp":
            _print_hp(result)
        elif cmd == "autoeat":
            _print_autoeat(result)
        elif cmd == "food_slot":
            _print_food_slot(result)
        elif cmd == "stats":
            _print_stats(result)
        elif cmd == "enemy":
            _print_enemy(result)
        elif cmd == "current_loot":
            _print_current_loot(result)
        elif cmd == "full_status":
            _print_full_status(result)
        elif cmd == "dungeon_completion":
            _print_dungeon_completion(result)
        elif cmd == "drops":
            _print_drops(result)
    return buf.getvalue().rstrip("\n")


def main() -> int:
    if len(sys.argv) < 2:
        _usage()
        return 1
    cmd = sys.argv[1].strip().lower()
    args = [cmd]
    if cmd == "drops":
        if len(sys.argv) < 3:
            _usage()
            return 1
        args.append(sys.argv[2].strip().lower())
        if args[1] in {"monster", "dungeon"}:
            if len(sys.argv) < 4:
                _usage()
                return 1
            args.extend(sys.argv[3:])
        elif args[1] != "all":
            _usage()
            return 1
    elif cmd not in {"style", "hp", "autoeat", "food_slot", "stats", "enemy", "current_loot", "full_status", "dungeon_completion"}:
        _usage()
        return 1

    try:
        log_observation("combat", args)
        resp = daemon_send({"op": "observation.call", "name": "combat", "args": args})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2

    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1

    result = resp.get("result") or {}
    out = format_output(cmd, result, args)
    log_observation_result("combat", args, True, result=result, details=out)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
