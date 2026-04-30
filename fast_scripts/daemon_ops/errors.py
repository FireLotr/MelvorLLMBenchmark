from __future__ import annotations

from typing import Any


def unsupported(kind: str, name: str, args: list[str]) -> dict[str, Any]:
    return {
        "ok": False,
        "code": "UNSUPPORTED_FAST",
        "error": f"UNSUPPORTED_FAST: {kind} '{name}' not implemented in daemon",
        "name": name,
        "args": args,
    }

