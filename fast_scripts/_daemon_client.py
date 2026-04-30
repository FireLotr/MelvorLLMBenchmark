from __future__ import annotations

import json
import os
import socket
from typing import Any

HOST = os.environ.get("MELVOR_HELPER_HOST", "127.0.0.1")
PORT = int(os.environ.get("MELVOR_HELPER_PORT", "17312"))


def daemon_send(req: dict[str, Any], timeout_s: float = 30.0) -> dict[str, Any]:
    data = (json.dumps(req) + "\n").encode("utf-8")
    with socket.create_connection((HOST, PORT), timeout=timeout_s) as s:
        s.sendall(data)
        line = b""
        while not line.endswith(b"\n"):
            chunk = s.recv(4096)
            if not chunk:
                break
            line += chunk
    if not line:
        return {"ok": False, "error": "empty response from daemon"}
    return json.loads(line.decode("utf-8"))
