from __future__ import annotations

from typing import Any

from playwright.sync_api import Page

from js_actions.shop import SHOP_BUY_JS
from js_actions.combat import (
    COMBAT_FOOD_SLOT_JS,
    COMBAT_LIST_JS,
    COMBAT_LOOT_JS,
    COMBAT_STOP_JS,
    COMBAT_STYLE_JS,
    COMBAT_TARGET_JS,
    COMBAT_UNEQUIP_FOOD_JS,
)
from js_actions.bank import (
    BANK_CLAIM_JS,
    BANK_EQUIP_FOOD_JS,
    BANK_EQUIP_JS,
    BANK_OPEN_JS,
    BANK_SELL_JS,
    BANK_UNEQUIP_JS,
    BANK_UPGRADE_JS,
)
from js_actions.cooking import COOKING_IS_ACTIVE_JS, COOKING_LIST_JS, COOKING_START_JS, COOKING_STOP_JS
from js_actions.firemaking import (
    FIREMAKING_BONFIRE_START_JS,
    FIREMAKING_BONFIRE_STOP_JS,
    FIREMAKING_SELECT_JS,
    FIREMAKING_START_JS,
    FIREMAKING_STOP_JS,
)
from js_actions.fishing import FISHING_START_JS, FISHING_STOP_JS
from js_actions.farming import (
    FARMING_COMPOST_ALL_GAME_JS,
    FARMING_COMPOST_PLOT_JS,
    FARMING_CLEAR_PLOT_JS,
    FARMING_HARVEST_PLOT_JS,
    FARMING_HARVEST_ALL_GAME_JS,
    FARMING_PARSE_ARGS_JS,
    FARMING_PLANT_ALL_GAME_JS,
    FARMING_PLANT_ALL_SELECTED_GAME_JS,
    FARMING_SELECT_SEED_JS,
    FARMING_UNLOCK_JS,
)
from js_actions.mastery import MASTERY_SPEND_JS
from js_actions.mining import MINING_START_JS, MINING_STOP_JS
from js_actions.smithing import SMITHING_LIST_JS, SMITHING_START_JS, SMITHING_STOP_JS
from js_actions.woodcutting import WOODCUTTING_START_JS, WOODCUTTING_STATE_JS, WOODCUTTING_STOP_JS
from _session import PAGES, navigate_fast
from daemon_ops.errors import unsupported


SKILL_ALIASES = {
    "fishing": "fishing",
    "mining": "mining",
    "woodcutting": "woodcutting",
    "firemaking": "firemaking",
    "cooking": "cooking",
    "smithing": "smithing",
    "farming": "farming",
}


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _resolve_skill(skill: str) -> str | None:
    return SKILL_ALIASES.get(_norm(skill))


def handle_action_call(page: Page, name: str, args: list[str]) -> dict[str, Any]:
    n = (name or "").strip().lower()
    if n == "navigate":
        if not args:
            return {"ok": False, "error": "navigate needs page key arg"}
        key = args[0].strip().lower()
        if key not in PAGES:
            return {"ok": False, "error": "unknown page key", "known": sorted(PAGES)}
        return {"ok": bool(navigate_fast(page, key, quiet=True)), "result": {"key": key}}

    if n == "mining":
        if not args:
            return {"ok": False, "error": "mining needs subcommand: start|stop"}
        sub = args[0].strip().lower()
        if sub == "stop":
            result = page.evaluate(MINING_STOP_JS)
            return {"ok": bool(result.get("ok")), "result": result}
        if sub == "start":
            if len(args) < 2:
                return {"ok": False, "error": "mining start needs rock name"}
            result = page.evaluate(MINING_START_JS, " ".join(args[1:]).strip())
            return {"ok": bool(result.get("ok")), "result": result}
        return {"ok": False, "error": f"unknown mining subcommand: {sub}"}

    if n in {"fishing", "woodcutting", "cooking", "smithing"}:
        if not args:
            return {"ok": False, "error": f"{n} requires subcommand start|stop"}
        sub = args[0].strip().lower()

        if n == "fishing":
            if sub == "stop":
                data = page.evaluate(FISHING_STOP_JS)
                return {"ok": bool(data.get("ok")), "result": data}
            if sub == "start":
                if not navigate_fast(page, n, quiet=True):
                    return {"ok": False, "error": f"Could not navigate to {n}"}
                if len(args) < 2:
                    return {"ok": False, "error": "fishing start requires fish name"}
                query = _norm(" ".join(args[1:]))
                data = page.evaluate(FISHING_START_JS, query)
                return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
            return {"ok": False, "error": f"Unknown fishing subcommand: {sub}"}

        if n == "woodcutting":
            if sub == "stop":
                data = page.evaluate(WOODCUTTING_STOP_JS)
                return {"ok": bool(data.get("ok")), "result": data}
            if sub == "start":
                if not navigate_fast(page, n, quiet=True):
                    return {"ok": False, "error": f"Could not navigate to {n}"}
                if len(args) < 2:
                    return {"ok": False, "error": "woodcutting start requires tree name(s)"}
                req = [x.strip() for x in " ".join(args[1:]).split(",") if x.strip()]
                state = page.evaluate(WOODCUTTING_STATE_JS)
                if len(req) > int(state.get("limit", 1)):
                    return {"ok": False, "error": "Too many trees requested for current cut limit"}
                tree_names = [t["name"] for t in state["trees"]]
                resolved = []
                for q in req:
                    nq = _norm(q)
                    exact = [x for x in tree_names if _norm(x) == nq]
                    hits = exact if exact else [x for x in tree_names if nq and nq in _norm(x)]
                    if len(hits) != 1:
                        return {"ok": False, "error": f"Unknown or ambiguous tree: {q}"}
                    info = next((t for t in state["trees"] if t["name"] == hits[0]), None)
                    if not info or not info.get("unlocked"):
                        return {"ok": False, "error": f"Tree locked: {hits[0]}"}
                    if hits[0] not in resolved:
                        resolved.append(hits[0])
                data = page.evaluate(WOODCUTTING_START_JS, resolved)
                return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
            return {"ok": False, "error": f"Unknown woodcutting subcommand: {sub}"}

        if n == "cooking":
            if sub == "stop":
                data = page.evaluate(COOKING_STOP_JS)
                return {"ok": bool(data.get("ok")), "result": data}
            if sub == "start":
                if not navigate_fast(page, n, quiet=True):
                    return {"ok": False, "error": f"Could not navigate to {n}"}
                if len(args) < 2:
                    return {"ok": False, "error": "cooking start requires recipe name"}
                q = _norm(" ".join(args[1:]))
                rows = page.evaluate(COOKING_LIST_JS)
                exact = [r for r in rows if _norm(r["name"]) == q]
                picks = exact if exact else [r for r in rows if q and q in _norm(r["name"])]
                if len(picks) != 1:
                    return {"ok": False, "error": "Unknown or ambiguous recipe"}
                t = picks[0]
                if not t.get("unlocked"):
                    return {"ok": False, "error": f"Recipe locked: {t['name']}"}
                selected = page.evaluate(COOKING_START_JS, t["name"])
                if not selected.get("ok"):
                    return {"ok": False, "error": "Could not select recipe"}
                is_active = bool(page.evaluate(COOKING_IS_ACTIVE_JS))
                if not is_active:
                    return {
                        "ok": False,
                        "result": {"recipe": t["name"], "selected": selected},
                        "error": "could not start cooking (likely missing costs/ingredients or blocked by current state)",
                    }
                return {"ok": True, "result": {"recipe": t["name"], "selected": selected}}
            return {"ok": False, "error": f"Unknown cooking subcommand: {sub}"}

        if n == "smithing":
            if sub == "stop":
                data = page.evaluate(SMITHING_STOP_JS)
                return {"ok": bool(data.get("ok")), "result": data}
            if sub == "start":
                if not navigate_fast(page, n, quiet=True):
                    return {"ok": False, "error": f"Could not navigate to {n}"}
                if len(args) < 2:
                    return {"ok": False, "error": "smithing start requires recipe name"}
                q = _norm(" ".join(args[1:]))
                rows = page.evaluate(SMITHING_LIST_JS)
                exact = [r for r in rows if _norm(r["name"]) == q]
                picks = exact if exact else [r for r in rows if q and q in _norm(r["name"])]
                if len(picks) != 1:
                    return {"ok": False, "error": "Unknown or ambiguous recipe"}
                t = picks[0]
                if not t.get("unlocked"):
                    return {"ok": False, "error": f"Recipe locked: {t['name']}"}
                data = page.evaluate(SMITHING_START_JS, t["name"])
                return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
            return {"ok": False, "error": f"Unknown smithing subcommand: {sub}"}

    if n == "firemaking":
        if not args:
            return {"ok": False, "error": "firemaking requires command"}
        cmd = args[0].strip().lower()
        if cmd == "stop":
            data = page.evaluate(FIREMAKING_STOP_JS)
            return {"ok": bool(data.get("ok")), "result": data}
        if not navigate_fast(page, "firemaking", quiet=True):
            return {"ok": False, "error": "Could not navigate to firemaking"}
        if cmd == "select":
            if len(args) < 2:
                return {"ok": False, "error": "select requires log name"}
            log_query = _norm(" ".join(args[1:]))
            data = page.evaluate(FIREMAKING_SELECT_JS, log_query)
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        if cmd == "start":
            if len(args) < 2:
                return {"ok": False, "error": "start requires log name"}
            log_query = _norm(" ".join(args[1:]))
            data = page.evaluate(FIREMAKING_START_JS, log_query)
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        if cmd == "bonfire":
            if len(args) < 2:
                return {"ok": False, "error": "bonfire requires start|stop"}
            sub = args[1].strip().lower()
            if sub == "start":
                log_query = _norm(" ".join(args[2:])) if len(args) > 2 else ""
                data = page.evaluate(FIREMAKING_BONFIRE_START_JS, log_query)
                return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
            if sub == "stop":
                data = page.evaluate(FIREMAKING_BONFIRE_STOP_JS)
                return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
            return {"ok": False, "error": f"Unknown bonfire subcommand: {sub}"}
        return {"ok": False, "error": f"Unknown firemaking command: {cmd}"}

    if n == "farming":
        if not args:
            return {"ok": False, "error": "farming requires command"}
        cmd = args[0].strip().lower()
        parsed = page.evaluate(FARMING_PARSE_ARGS_JS, args[1:])
        category = parsed.get("category", "Allotments") if isinstance(parsed, dict) else "Allotments"
        plot = int(parsed.get("plot", 1)) if isinstance(parsed, dict) else 1
        seed = str(parsed.get("seed") or "") if isinstance(parsed, dict) else ""
        data: dict[str, Any]
        if cmd == "harvest-all-game":
            data = page.evaluate(FARMING_HARVEST_ALL_GAME_JS, {"category": category})
        elif cmd == "compost-all-game":
            comp = str(args[1]) if len(args) > 1 else "compost"
            data = page.evaluate(FARMING_COMPOST_ALL_GAME_JS, {"category": category, "compost": comp})
        elif cmd == "plant-all-game":
            data = page.evaluate(FARMING_PLANT_ALL_GAME_JS, {"category": category, "seed": seed})
        elif cmd == "plant-all-selected-game":
            data = page.evaluate(FARMING_PLANT_ALL_SELECTED_GAME_JS, {"category": category})
        elif cmd == "harvest":
            data = page.evaluate(FARMING_HARVEST_PLOT_JS, {"category": category, "plot": plot})
        elif cmd == "compost":
            data = page.evaluate(FARMING_COMPOST_PLOT_JS, {"category": category, "plot": plot, "compost": "compost"})
        elif cmd == "weird-gloop":
            data = page.evaluate(FARMING_COMPOST_PLOT_JS, {"category": category, "plot": plot, "compost": "weird gloop"})
        elif cmd == "clear":
            data = page.evaluate(FARMING_CLEAR_PLOT_JS, {"category": category, "plot": plot})
        elif cmd == "unlock":
            data = page.evaluate(FARMING_UNLOCK_JS, {"category": category, "plot": plot})
        elif cmd == "select-seed":
            data = page.evaluate(FARMING_SELECT_SEED_JS, {"category": category, "plot": plot, "seed": seed, "doPlant": False})
        elif cmd == "plant":
            data = page.evaluate(FARMING_SELECT_SEED_JS, {"category": category, "plot": plot, "seed": seed, "doPlant": True})
        else:
            return {"ok": False, "error": f"Unknown farming command: {cmd}"}
        return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}

    if n == "mastery":
        if len(args) < 2:
            return {"ok": False, "error": "mastery usage: spend|claim <skill> ..."}
        cmd = _norm(args[0])
        skill_key = _resolve_skill(args[1])
        if not skill_key:
            return {"ok": False, "error": f"Unknown skill: {args[1]}"}
        if not navigate_fast(page, skill_key, quiet=True):
            return {"ok": False, "error": f"Could not navigate to {skill_key}"}
        if cmd == "claim":
            skill_label = skill_key[:1].upper() + skill_key[1:]
            return handle_action_call(page, "bank", ["claim", f"Mastery Token ({skill_label})", "999999"])
        if cmd == "spend":
            if len(args) < 4:
                return {"ok": False, "error": "mastery spend needs <skill> <action> <levels>"}
            action_query = args[2]
            try:
                lv = int(args[3])
            except Exception:
                return {"ok": False, "error": "levels must be integer"}
            data = page.evaluate(MASTERY_SPEND_JS, {"query": action_query, "levels": lv, "skill": skill_key})
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        return {"ok": False, "error": f"Unknown mastery command: {cmd}"}

    if n == "bank":
        if not args:
            return {"ok": False, "error": "bank needs subcommand"}
        sub = args[0].strip().lower()
        if sub == "sell":
            if len(args) < 3:
                return {"ok": False, "error": "bank sell usage: sell <item> <qty>"}
            try:
                qty = int(args[2])
            except Exception:
                return {"ok": False, "error": "bank sell qty must be int"}
            result = page.evaluate(BANK_SELL_JS, {"name": args[1], "qty": qty})
            return {"ok": bool(result.get("ok")), "result": result}
        if sub == "sellmulti":
            if len(args) < 3 or (len(args) - 1) % 2 != 0:
                return {"ok": False, "error": "sellmulti expects repeated <item> <qty> pairs"}
            results = []
            for i in range(1, len(args), 2):
                try:
                    qty = int(args[i + 1])
                except Exception:
                    return {"ok": False, "error": f"Invalid qty for {args[i]}"}
                res = page.evaluate(BANK_SELL_JS, {"name": args[i], "qty": qty})
                if not bool(res.get("ok")):
                    return {"ok": False, "result": {"failed": args[i], "details": res, "done": results}}
                results.append({"name": res.get("name", args[i]), "qty": int(res.get("qty", qty))})
            return {"ok": True, "result": {"sold": results}}
        if sub == "equip":
            if len(args) < 2:
                return {"ok": False, "error": "equip requires item name"}
            data = page.evaluate(BANK_EQUIP_JS, args[1])
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        if sub == "unequip":
            if len(args) < 2:
                return {"ok": False, "error": "unequip requires slot name"}
            data = page.evaluate(BANK_UNEQUIP_JS, args[1])
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        if sub == "equipfood":
            if len(args) < 2:
                return {"ok": False, "error": "equipfood requires item name"}
            qty = None
            if len(args) >= 3:
                try:
                    qty = int(args[2])
                except Exception:
                    return {"ok": False, "error": "equipfood qty must be int"}
            data = page.evaluate(BANK_EQUIP_FOOD_JS, {"name": args[1], "qty": qty})
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        if sub == "upgrade":
            if len(args) < 2:
                return {"ok": False, "error": "upgrade requires item name"}
            qty = 1
            if len(args) >= 3:
                try:
                    qty = int(args[2])
                except Exception:
                    return {"ok": False, "error": "upgrade qty must be int"}
            data = page.evaluate(BANK_UPGRADE_JS, {"name": args[1], "qty": qty})
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        if sub == "open":
            if len(args) < 2:
                return {"ok": False, "error": "open requires item name"}
            qty = 1
            if len(args) >= 3:
                try:
                    qty = int(args[2])
                except Exception:
                    return {"ok": False, "error": "open qty must be int"}
            data = page.evaluate(BANK_OPEN_JS, {"name": args[1], "qty": qty})
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        if sub == "claim":
            if len(args) < 2:
                return {"ok": False, "error": "claim requires item name"}
            qty = 1
            if len(args) >= 3:
                try:
                    qty = int(args[2])
                except Exception:
                    return {"ok": False, "error": "claim qty must be int"}
            data = page.evaluate(BANK_CLAIM_JS, {"name": args[1], "qty": qty})
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        return {"ok": False, "error": f"Unknown bank command: {sub}"}

    if n == "shop":
        if not args:
            return {"ok": False, "error": "shop needs subcommand"}
        if args[0].strip().lower() != "buy":
            return unsupported("action", f"shop.{args[0]}", args)
        if len(args) < 3:
            return {"ok": False, "error": "shop buy usage: buy <name> <qty>"}
        try:
            qty = int(args[2])
        except Exception:
            return {"ok": False, "error": "shop buy qty must be int"}
        result = page.evaluate(SHOP_BUY_JS, {"name": args[1], "qty": qty})
        return {"ok": bool(result.get("ok")), "result": result}

    if n == "combat":
        if not args:
            return {"ok": False, "error": "combat requires target/command"}
        low = " ".join(args).strip().lower()
        if low == "list":
            return {
                "ok": True,
                "result": page.evaluate(COMBAT_LIST_JS),
            }
        if low == "loot":
            data = page.evaluate(COMBAT_LOOT_JS)
            return {"ok": bool(data.get("ok", True)), "result": data}
        if low == "stop":
            data = page.evaluate(COMBAT_STOP_JS)
            return {"ok": bool(data.get("ok", True)), "result": data}
        if low == "style":
            return {"ok": False, "error": "style usage: style <stab|slash|block>"}
        if low.startswith("style "):
            parts = " ".join(args).split()
            if len(parts) < 2:
                return {"ok": False, "error": "style usage: style <stab|slash|block>"}
            style_key = parts[1].strip().lower()
            style_map = {"stab": "Stab", "slash": "Slash", "block": "Block"}
            if style_key not in style_map:
                return {"ok": False, "error": f"Unknown style: {parts[1]}"}
            label = style_map[style_key]
            data = page.evaluate(COMBAT_STYLE_JS, label)
            return {"ok": bool(data.get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        if low.startswith("unequip food"):
            slot = 1
            for tok in reversed(" ".join(args).split()):
                if tok.isdigit():
                    slot = int(tok)
                    break
            if slot < 1 or slot > 3:
                return {"ok": False, "error": "Food slot must be 1, 2, or 3"}
            data = page.evaluate(COMBAT_UNEQUIP_FOOD_JS, slot)
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        if low.startswith("food slot"):
            slot = None
            for tok in reversed(" ".join(args).split()):
                if tok.isdigit():
                    slot = int(tok)
                    break
            if slot is None or slot < 1 or slot > 3:
                return {"ok": False, "error": "food slot usage: food slot <1|2|3>"}
            data = page.evaluate(COMBAT_FOOD_SLOT_JS, slot)
            return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}
        target = " ".join(args)
        if not navigate_fast(page, "combat", quiet=True):
            return {"ok": False, "error": "Could not navigate to combat"}
        data = page.evaluate(COMBAT_TARGET_JS, target)
        return {"ok": bool((data or {}).get("ok")), "result": data, **({"error": data.get("error")} if isinstance(data, dict) and data.get("error") else {})}

    return unsupported("action", n, args)

