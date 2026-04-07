#!/usr/bin/env python3
"""Action logging helpers for scripts/actions.

Every script should call ``log_action_call`` first in ``__main__``. That call
detects a SweetAlert2 **You Died** modal: if present, it is dismissed (OK),
death is reported to the console and ``error.txt``, an ``action_result`` line
is written with ``success: false``, and the process **exits** with code 1 so the
action body does not run.

``log_action_result`` still checks for death **after** the action (e.g. you died
during the scripted clicks).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _paths():
    root = Path(__file__).resolve().parents[2]
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return root, logs_dir, logs_dir / "actions.log", root / "error.txt"


# Same SweetAlert2 death modal parsing as scripts/observations/_observation_logging.py
_DEATH_MODAL_SUBPROCESS_JS = r"""
import json
from playwright.sync_api import sync_playwright
out = {"died": False, "loss_summary": ""}
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
            '  const low = text.toLowerCase();'
            '  if (low.includes("luck was on your side")) return "You lost nothing.";'
            '  if (low.includes("it looks like you lost your")) {'
            '    const lines = text.split("\\n").map(l => l.trim()).filter(Boolean);'
            '    const items = lines.filter(l => !l.toLowerCase().startsWith("it looks like"));'
            '    return items.length ? "You lost: " + items.join(", ") : "You lost an item.";'
            '  }'
            '  return text || "Unknown outcome.";'
            '})()'
        )
        if result is not None:
            out["died"] = True
            out["loss_summary"] = result
            try:
                confirm = page.locator(".swal2-confirm")
                if confirm.is_visible():
                    confirm.click()
            except Exception:
                pass
print(json.dumps(out))
"""


def detect_death_on_screen() -> tuple[bool, str]:
    """Detect 'You Died' SweetAlert2 modal; dismiss it; return (died, loss_summary)."""
    root, _, _, _ = _paths()
    timeout_s = float(os.environ.get("ACTION_DEATH_CHECK_TIMEOUT_S", "8"))
    try:
        p = subprocess.run(
            [sys.executable, "-c", _DEATH_MODAL_SUBPROCESS_JS],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout_s,
        )
        data = json.loads((p.stdout or "").strip() or "{}")
        return bool(data.get("died")), str(data.get("loss_summary", ""))
    except Exception:
        return False, ""


def format_death_loss_line(loss_summary: str) -> str:
    """One line for terminal / error.txt (modal body is already phrased e.g. 'You lost: …')."""
    s = (loss_summary or "").strip()
    return s if s else "Unknown outcome."


def report_detected_death(
    script_name: str,
    argv: list[str],
    loss_summary: str,
    *,
    when: str,
    ts: str,
    before_screenshot: str | None,
    after_screenshot: str | None,
    command_skipped: bool = False,
) -> None:
    root, _, actions_log, error_file = _paths()
    alert = "!!! CRITICAL ALERT: YOU DIED !!!"
    bar = "!" * len(alert)
    print("\n" + bar)
    print(alert)
    print(bar)
    print()
    print(format_death_loss_line(loss_summary))
    print()
    print(f"Command: {script_name} {' '.join(argv)}")
    if command_skipped:
        print("The requested action was not performed due to death.")
    print()
    log_lines = [
        f"[{ts}] DEATH DETECTED ({when}): {script_name} {' '.join(argv)}",
        format_death_loss_line(loss_summary),
    ]
    if command_skipped:
        log_lines.append("action_not_run: requested action was not performed due to death")
    log_lines.extend(
        [
            f"screenshots.before: {before_screenshot or '(not captured)'}",
            f"screenshots.after: {after_screenshot or '(not captured)'}",
            f"logs.action: {actions_log.relative_to(root)}",
            "",
        ]
    )
    with error_file.open("a", encoding="utf-8") as f:
        f.write("\n".join(log_lines))


def log_action_call(script_name: str, argv: list[str]) -> None:
    _, _, actions_log, _ = _paths()
    ts_call = datetime.now().isoformat(timespec="seconds")
    entry = {
        "ts": ts_call,
        "event": "action_call",
        "script": script_name,
        "argv": argv,
    }
    with actions_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    died, loss_summary = detect_death_on_screen()
    if died:
        ts = datetime.now().isoformat(timespec="seconds")
        report_detected_death(
            script_name,
            argv,
            loss_summary,
            when="before action",
            ts=ts,
            before_screenshot=None,
            after_screenshot=None,
            command_skipped=True,
        )
        result_entry = {
            "ts": ts,
            "event": "action_result",
            "script": script_name,
            "argv": argv,
            "success": False,
            "before_screenshot": None,
            "after_screenshot": None,
            "details": "blocked: You Died modal was open (dismissed); action not run",
        }
        with actions_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result_entry) + "\n")
        sys.exit(1)


def log_action_result(
    script_name: str,
    argv: list[str],
    success: bool,
    before_screenshot: str | None = None,
    after_screenshot: str | None = None,
    details: str = "",
) -> None:
    root, _, actions_log, error_file = _paths()
    ts = datetime.now().isoformat(timespec="seconds")

    died, loss_summary = detect_death_on_screen()
    if died:
        report_detected_death(
            script_name,
            argv,
            loss_summary,
            when="after action",
            ts=ts,
            before_screenshot=before_screenshot,
            after_screenshot=after_screenshot,
        )

    entry = {
        "ts": ts,
        "event": "action_result",
        "script": script_name,
        "argv": argv,
        "success": bool(success),
        "before_screenshot": before_screenshot,
        "after_screenshot": after_screenshot,
        "details": details,
    }
    with actions_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    if not success:
        with error_file.open("a", encoding="utf-8") as f:
            f.write(
                "\n".join(
                    [
                        f"[{ts}] ACTION FAILURE: {script_name} {' '.join(argv)}",
                        f"details: {details or 'Action returned failure.'}",
                        f"screenshots.before: {before_screenshot or '(not captured)'}",
                        f"screenshots.after: {after_screenshot or '(not captured)'}",
                        f"logs.action: {actions_log.relative_to(root)}",
                        "",
                    ]
                )
            )
