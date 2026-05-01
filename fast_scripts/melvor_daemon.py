#!/usr/bin/env python3
"""
Long-lived Melvor helper: one Playwright CDP connection, JSON-over-TCP on localhost.
"""

from __future__ import annotations

import json
import os
import socketserver
import sys
from pathlib import Path

os.environ.setdefault("NODE_NO_WARNINGS", "1")

from playwright.sync_api import Playwright, sync_playwright

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from _session import CDP_URL, connect_page  # noqa: E402
from daemon_ops.router import dispatch  # noqa: E402

HOST = os.environ.get("MELVOR_HELPER_HOST", "127.0.0.1")
PORT = int(os.environ.get("MELVOR_HELPER_PORT", "17312"))

_pw: Playwright | None = None
_page = None
_server: socketserver.TCPServer | None = None

_SELECT_READY_MS = int(os.environ.get("MELVOR_CHARACTER_SELECT_READY_MS", "90000"))


def _ensure_page(require_game: bool = True):
    global _pw, _page
    if _page is not None:
        try:
            if not _page.is_closed():
                return _page
        except Exception:
            pass
        _page = None
    if _pw is not None:
        try:
            _pw.stop()
        except Exception:
            pass
        _pw = None
    _pw = sync_playwright().start()
    _page = connect_page(_pw)
    if require_game and not _page.evaluate("() => typeof game !== 'undefined'"):
        raise RuntimeError("Melvor tab connected but `game` is missing.")
    return _page


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline()
        if not line:
            return
        try:
            req = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as e:
            self.wfile.write((json.dumps({"ok": False, "error": f"json: {e}"}) + "\n").encode("utf-8"))
            return
        try:
            op = str(req.get("op") or "")
            if op == "ping":
                resp = {"ok": True, "daemon": True}
            elif op in {"character.select_first", "character.select"}:
                slot = req.get("slot", 1)
                try:
                    slot = max(1, int(slot))
                except Exception:
                    slot = 1
                direct_slot = max(0, int(slot) - 1)
                page = _ensure_page(require_game=False)
                try:
                    page.wait_for_function(
                        """(ds) => {
                            if (typeof loadLocalSave !== "function") return false;
                            return !!document.getElementById("save-slot-display-" + ds);
                        }""",
                        arg=direct_slot,
                        polling=500,
                        timeout=_SELECT_READY_MS,
                    )
                except Exception as e:
                    resp = {
                        "ok": False,
                        "error": f"Character select not ready within {_SELECT_READY_MS}ms: {e}",
                    }
                    self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))
                    return
                data = page.evaluate(
                    """(directSlot) => {
                        if (typeof loadLocalSave !== "function") {
                            return { ok: false, error: "loadLocalSave is not defined" };
                        }
                        try {
                            const p = loadLocalSave(directSlot);
                            if (p && typeof p.then === "function" && typeof p.catch === "function") {
                                p.catch(() => {});
                            }
                            return { ok: true, slot: directSlot, via: "loadLocalSave" };
                        } catch (e) {
                            return { ok: false, error: String(e?.message ?? e), slot: directSlot };
                        }
                    }""",
                    direct_slot,
                )
                resp = data if isinstance(data, dict) else {"ok": False, "error": "invalid select response"}
            else:
                resp = dispatch(_ROOT, req, _ensure_page())
        except Exception as e:
            resp = {"ok": False, "error": str(e)}
        self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))


def main() -> None:
    global _server
    socketserver.TCPServer.allow_reuse_address = True
    _server = socketserver.TCPServer((HOST, PORT), _Handler)
    print(
        f"melvor_daemon listening on {HOST}:{PORT} (CDP {CDP_URL}). "
        "Send one JSON line per request; Ctrl+C to quit.",
        flush=True,
    )
    try:
        _server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...", flush=True)
    finally:
        _server.server_close()
        global _pw, _page
        if _pw is not None:
            try:
                _pw.stop()
            except Exception:
                pass
        _pw = None
        _page = None


if __name__ == "__main__":
    main()
