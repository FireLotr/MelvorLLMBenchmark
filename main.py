import subprocess
import time
import argparse
import os
import json
import socket
import signal
import urllib.request

RESTART_INTERVAL = 3 * 60 * 60
_SHUTDOWN = False
_ACTIVE_PROCESSES: list[subprocess.Popen] = []

def _daemon_request(daemon_port: int, payload: dict, timeout_s: int = 6) -> dict:
    try:
        with socket.create_connection(("127.0.0.1", daemon_port), timeout=timeout_s) as s:
            s.settimeout(timeout_s)
            s.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            data = b""
            while not data.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        return json.loads(data.decode("utf-8")) if data else {"ok": False, "error": "empty daemon reply"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _wait_for_daemon(daemon_port: int, timeout_s: int = 30) -> bool:
    deadline = time.time() + max(3, timeout_s)
    while time.time() < deadline:
        resp = _daemon_request(daemon_port, {"op": "ping"}, timeout_s=2)
        if resp.get("ok"):
            return True
        time.sleep(1)
    return False


def _wait_for_cdp(cdp_port: int, timeout_s: int = 30) -> bool:
    deadline = time.time() + max(3, timeout_s)
    url = f"http://127.0.0.1:{cdp_port}/json/version"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _select_character_via_daemon(daemon_port: int, slot: int = 1) -> bool:
    deadline = time.time() + 120
    last_error = "unknown error"
    slot = max(1, int(slot))
    while time.time() < deadline and not _SHUTDOWN:
        resp = _daemon_request(
            daemon_port,
            {"op": "character.select", "slot": slot},
            timeout_s=100,
        )
        if resp.get("ok"):
            print(f"Character selection command sent (slot {slot}).")
            return True
        last_error = str(resp.get("error", "unknown error"))
        # Character page/data can be temporarily unavailable during boot.
        retryable = (
            "No existing save slot button found",
            "game is not defined",
            "Target page, context or browser has been closed",
            "Execution context was destroyed",
            "connect ECONNREFUSED",
            "retrieving websocket url",
            "timed out",
            "Character select not ready",
        )
        if not any(msg in last_error for msg in retryable):
            break
        time.sleep(1)
    print(f"Character select via daemon failed: {last_error}")
    return False


def _spawn_daemon(port: int, daemon_port: int) -> subprocess.Popen:
    daemon_cmd = [
        "./venv/bin/python",
        "fast_scripts/melvor_daemon.py",
    ]
    daemon_env = os.environ.copy()
    daemon_env["MELVOR_CDP_URL"] = f"http://localhost:{port}"
    daemon_env["MELVOR_HELPER_PORT"] = str(daemon_port)
    return subprocess.Popen(daemon_cmd, env=daemon_env, start_new_session=True)


def start_processes(port, daemon_port, character_slot: int = 1):
    chromium_cmd = [
        "chromium-browser",
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-plugins",
        "--disable-dev-shm-usage",
        f"--remote-debugging-port={port}",
        f"--user-data-dir=/tmp/melvor-clean-{port}",  # avoid clashes
        "--window-size=1920,1080",
        "--mute-audio",
        "--no-first-run",
        "--no-default-browser-check",
        "https://melvoridle.com"
    ]

    # Run each child in its own process group so we can terminate the whole tree.
    chromium = subprocess.Popen(chromium_cmd, start_new_session=True)
    daemon = _spawn_daemon(port, daemon_port)
    if _wait_for_daemon(daemon_port, timeout_s=35):
        if _wait_for_cdp(port, timeout_s=35):
            _select_character_via_daemon(daemon_port, character_slot)
        else:
            print("CDP did not become ready in time; skipping character select.")
    else:
        print("Daemon did not become ready in time; skipping character select.")

    return chromium, daemon


def stop_processes(processes):
    global _ACTIVE_PROCESSES
    for p in processes:
        if p is None or p.poll() is not None:
            continue
        try:
            # Kill the whole process group that this child leads.
            os.killpg(p.pid, signal.SIGTERM)
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass
    time.sleep(5)
    for p in processes:
        if p is None or p.poll() is not None:
            continue
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    _ACTIVE_PROCESSES = []


def _request_shutdown(signum, _frame):
    global _SHUTDOWN
    _SHUTDOWN = True
    print(f"Received signal {signum}, shutting down children...")
    stop_processes(_ACTIVE_PROCESSES)
    raise SystemExit(0)


def main():
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGHUP, _request_shutdown)

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument("--daemon-port", type=int, default=17312)
    parser.add_argument("--character-slot", type=int, default=1, help="1-based character slot to load")
    parser.add_argument("--sleep-seconds", type=int, default=60, help="Seconds between child-health checks")
    parser.add_argument("--restart-delay-seconds", type=int, default=3, help="Seconds to wait before restart")
    args = parser.parse_args()

    while not _SHUTDOWN:
        print(
            f"Starting with Chrome CDP port {args.port} "
            f"and daemon port {args.daemon_port}..."
        )
        chromium, daemon = start_processes(args.port, args.daemon_port, args.character_slot)
        global _ACTIVE_PROCESSES
        _ACTIVE_PROCESSES = [chromium, daemon]

        start_time = time.time()

        while not _SHUTDOWN and time.time() - start_time < RESTART_INTERVAL:
            chromium_rc = chromium.poll()
            daemon_rc = daemon.poll()

            if chromium_rc is not None:
                print(f"Chrome died (exit {chromium_rc}), restarting full stack...")
                break

            if daemon_rc is not None:
                print(f"Daemon died (exit {daemon_rc}), restarting daemon only...")
                daemon = _spawn_daemon(args.port, args.daemon_port)
                _ACTIVE_PROCESSES = [chromium, daemon]
                if _wait_for_daemon(args.daemon_port, timeout_s=20):
                    print("Daemon reconnected to existing CDP session.")
                else:
                    print("Daemon did not become ready after restart; forcing full restart...")
                    break

            time.sleep(max(1, int(args.sleep_seconds)))

        if _SHUTDOWN:
            break
        print("Restarting...")
        stop_processes([chromium, daemon])
        time.sleep(max(0, int(args.restart_delay_seconds)))


if __name__ == "__main__":
    main()