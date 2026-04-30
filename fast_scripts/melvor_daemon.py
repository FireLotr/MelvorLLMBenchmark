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
                # Health check for orchestrators: daemon process/socket readiness only.
                # Do not force CDP attach here, because Chrome may still be booting.
                resp = {"ok": True, "daemon": True}
            elif op in {"character.select_first", "character.select"}:
                slot = req.get("slot", 1)
                try:
                    slot = max(1, int(slot))
                except Exception:
                    slot = 1
                page = _ensure_page(require_game=False)
                try:
                    page.wait_for_function(
                        "() => typeof window?.loadLocalSave === 'function'",
                        polling=1000,
                        timeout=30000,
                    )
                except Exception:
                    resp = {"ok": False, "error": "loadLocalSave did not appear within 30s"}
                    self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))
                    return
                data = page.evaluate(
                    """async (slot) => {
                        const openPage = String(game?.openPage?.id ?? "");
                        if (typeof game !== "undefined" && !!game?.bank && openPage) {
                            return { ok: true, alreadyInGame: true, clicked: false };
                        }
                        const directSlot = Math.max(0, (Number(slot) || 1) - 1);
                        try {
                            const maybePromise = window.loadLocalSave(directSlot);
                            if (maybePromise && typeof maybePromise.then === "function") {
                                await maybePromise;
                            }
                            return {
                                ok: true,
                                clicked: true,
                                confirmClicked: false,
                                direct: true,
                                via: "loadLocalSave",
                                slot: directSlot,
                            };
                        } catch (e) {
                            return {
                                ok: false,
                                error: String(e?.message ?? e),
                                via: "loadLocalSave",
                                slot: directSlot,
                            };
                        }
                    }""",
                    slot,
                )
                if isinstance(data, dict) and data.get("clicked"):
                    try:
                        page.wait_for_function(
                            """() => {
                                if (typeof game === "undefined" || !game?.bank) return false;
                                const swalOpen = !!document.querySelector(".swal2-container.swal2-backdrop-show, .swal2-popup.swal2-show");
                                return !swalOpen;
                            }""",
                            polling=1000,
                            timeout=30000,
                        )
                    except Exception:
                        state = page.evaluate(
                            """() => ({
                                openPage: String(game?.openPage?.id ?? ""),
                                swalOpen: !!document.querySelector(".swal2-container.swal2-backdrop-show, .swal2-popup.swal2-show")
                            })"""
                        )
                        resp = {
                            "ok": False,
                            "error": "Character load did not reach stable state (in-game + no swal).",
                            "result": data,
                            "state": state,
                        }
                        self.wfile.write((json.dumps(resp) + "\n").encode("utf-8"))
                        return
                resp = data if isinstance(data, dict) else {"ok": False, "error": "Invalid select response"}
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
