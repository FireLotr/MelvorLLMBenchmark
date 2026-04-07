#!/usr/bin/env python3
"""Observation logging helpers for scripts/observations."""

from __future__ import annotations

import json
import io
import os
import re
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

# Shared between run_observation and log_observation within one observation call.
# run_observation checks for death (after capturing output) and caches here so
# log_observation can write to error.txt without a second detection round-trip.
_last_death_check: tuple[bool, str] | None = None


def _log_file():
    root = Path(__file__).resolve().parents[2]
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "observations.log"


def _root_and_error():
    root = Path(__file__).resolve().parents[2]
    return root, root / "error.txt"


def _detect_death_on_screen() -> tuple[bool, str]:
    root, _ = _root_and_error()
    timeout_s = float(os.environ.get("OBS_DEATH_CHECK_TIMEOUT_S", "8"))
    code = r"""
import json
from playwright.sync_api import sync_playwright
out = {"died": False, "snippet": ""}
with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://localhost:9222")
    page = None
    for c in b.contexts:
        for p in c.pages:
            if "melvor" in p.url.lower():
                page = p
                break
        if page:
            break
    if page is None and b.contexts and b.contexts[0].pages:
        page = b.contexts[0].pages[0]
    if page:
        result = page.evaluate(
            '(() => {'
            '  const title = document.querySelector("#swal2-title, .swal2-title");'
            '  if (!title || !title.textContent.includes("You Died")) return null;'
            '  const body = document.querySelector("#swal2-html-container, .swal2-html-container");'
            '  const text = body ? body.innerText.trim() : "";'
            '  if (text.toLowerCase().includes("luck was on your side")) return "You lost nothing.";'
            '  if (text.toLowerCase().includes("it looks like you lost your")) {'
            '    const lines = text.split("\\n").map(l => l.trim()).filter(Boolean);'
            '    const items = lines.filter(l => !l.toLowerCase().startsWith("it looks like"));'
            '    return items.length ? "You lost: " + items.join(", ") : "You lost an item.";'
            '  }'
            '  return text || "Unknown outcome.";'
            '})()'
        )
        if result is not None:
            out["died"] = True
            out["snippet"] = result
            # Auto-dismiss the death modal so the game is unblocked.
            try:
                confirm = page.locator(".swal2-confirm")
                if confirm.is_visible():
                    confirm.click()
            except Exception:
                pass
print(json.dumps(out))
"""
    try:
        p = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout_s,
        )
        data = json.loads((p.stdout or "").strip() or "{}")
        return bool(data.get("died")), str(data.get("snippet", ""))
    except Exception:
        return False, ""


def _print_death_alert(snippet: str, script_name: str = "", argv: list[str] | None = None) -> None:
    alert = "!!! CRITICAL ALERT: YOU DIED !!!"
    bar = "!" * len(alert)
    print(bar)
    print(alert)
    print(bar)
    if snippet:
        print(snippet)


def log_observation(script_name: str, argv: list[str], success: bool, details: str = "") -> None:
    global _last_death_check
    log_path = _log_file()
    root, error_file = _root_and_error()
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "script": script_name,
        "argv": argv,
        "success": bool(success),
        "details": details,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    if _last_death_check is not None:
        # run_observation already detected death and printed the alert above the output.
        # Just consume the cache and write to error.txt.
        died, snippet = _last_death_check
        _last_death_check = None
    else:
        # Called outside run_observation (e.g. error path) — detect and print now.
        died, snippet = _detect_death_on_screen()
        if died:
            _print_death_alert(snippet, script_name, argv)
            print()

    if died:
        with error_file.open("a", encoding="utf-8") as f:
            f.write(
                "\n".join(
                    [
                        f"[{entry['ts']}] DEATH DETECTED during observation: {script_name} {' '.join(argv)}",
                        f"screen_snippet: {snippet or '(not captured)'}",
                        f"logs.observation: {log_path.relative_to(root)}",
                        "",
                    ]
                )
            )


def run_observation(fn, *args, **kwargs):
    """
    Run an observation function, capture exactly what it prints,
    echo it back to stdout, and return (success, output_text).

    Death detection runs after the function completes (while output is still
    buffered). If death is detected the alert is printed first, followed by
    a blank line, then the normal observation output — so the alert is always
    visible at the top. The death modal is also auto-dismissed.
    """
    global _last_death_check
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = fn(*args, **kwargs)
    output = buf.getvalue()

    # Check for death while output is still buffered so we can print alert first.
    died, snippet = _detect_death_on_screen()
    _last_death_check = (died, snippet)

    if died:
        _print_death_alert(snippet)
        print()  # blank line separating alert from normal output

    if output:
        print(output, end="")

    success = True if result is None else bool(result)
    return success, _normalize_output(output)


def _normalize_output(output: str) -> str:
    """Keep content, reduce noisy whitespace for log readability."""
    lines = [ln.rstrip() for ln in output.splitlines()]
    # Trim outer empty lines
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    # Collapse consecutive blank lines
    collapsed = []
    prev_blank = False
    for ln in lines:
        # Collapse long in-line spacing from table-aligned output.
        ln = re.sub(r"[ \t]{2,}", " ", ln).strip()
        is_blank = ln == ""
        if is_blank and prev_blank:
            continue
        collapsed.append(ln)
        prev_blank = is_blank
    return "\n".join(collapsed)
