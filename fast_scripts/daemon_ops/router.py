from __future__ import annotations

import os
import time
from typing import Any

from playwright.sync_api import Page

from js_actions.bank import BANK_SELL_JS
from js_actions.shop import SHOP_BUY_JS
from _session import PAGES, navigate_fast
from daemon_ops.actions import handle_action_call
from daemon_ops.observations import handle_observation_call, handle_read


def dispatch(root, req: dict[str, Any], page: Page) -> dict[str, Any]:
    op = req.get("op")

    if op == "ping":
        t0 = time.perf_counter()
        page.evaluate("() => 1")
        return {"ok": True, "eval_ms": round((time.perf_counter() - t0) * 1000, 3)}

    if op == "navigate":
        key = (req.get("key") or req.get("page") or "").strip().lower()
        if not key or key not in PAGES:
            return {"ok": False, "error": "navigate requires key in: " + ", ".join(sorted(PAGES))}
        return {"ok": bool(navigate_fast(page, key, quiet=True)), "key": key}

    if op == "read":
        try:
            return handle_read(page, req)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "action.call":
        name = str(req.get("name") or "").strip().lower()
        args = req.get("args") or []
        if not isinstance(args, list):
            args = [str(args)]
        try:
            return handle_action_call(page, name, [str(a) for a in args])
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "observation.call":
        name = str(req.get("name") or "").strip().lower()
        args = req.get("args") or []
        if not isinstance(args, list):
            args = [str(args)]
        str_args = [str(a) for a in args]
        try:
            return handle_observation_call(root, page, name, str_args)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "mining.start":
        rock = req.get("rock") or req.get("args")
        args = ["start"] + ([rock] if isinstance(rock, str) else [*rock] if isinstance(rock, list) else [])
        return handle_action_call(page, "mining", [str(a) for a in args if str(a).strip()])

    if op == "mining.stop":
        return handle_action_call(page, "mining", ["stop"])

    if op == "bank.sell":
        name = req.get("name")
        qty = req.get("qty", 1)
        if not isinstance(name, str) or not name.strip():
            return {"ok": False, "error": "bank.sell requires item name"}
        try:
            result = page.evaluate(BANK_SELL_JS, {"name": name, "qty": int(qty)})
            return {"ok": bool(result.get("ok")), "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "shop.buy":
        name = req.get("name")
        qty = req.get("qty", 1)
        if not isinstance(name, str) or not name.strip():
            return {"ok": False, "error": "shop.buy requires purchase name"}
        try:
            result = page.evaluate(SHOP_BUY_JS, {"name": name, "qty": int(qty)})
            return {"ok": bool(result.get("ok")), "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if op == "eval" and os.environ.get("MELVOR_DAEMON_EVAL") == "1":
        code = req.get("code")
        if not isinstance(code, str) or not code.strip():
            return {"ok": False, "error": "eval needs code (string)"}
        try:
            return {"ok": True, "result": page.evaluate(code)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {
        "ok": False,
        "error": f"unknown op: {op!r}",
        "known": [
            "ping",
            "navigate",
            "read",
            "eval",
            "action.call",
            "observation.call",
            "mining.start",
            "mining.stop",
            "bank.sell",
            "shop.buy",
        ],
    }

