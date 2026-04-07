#!/usr/bin/env python3
"""Shared screenshot helpers for action scripts."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

CDP_URL = "http://localhost:9222"


def _sanitize(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", value.lower().strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "action"


def _capture_direct(output_path: Path, timeout_s: float) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if "melvor" in pg.url.lower():
                    page = pg
                    break
            if page:
                break
        if page is None and browser.contexts and browser.contexts[0].pages:
            page = browser.contexts[0].pages[0]
        if page is None:
            raise RuntimeError("No browser page available for screenshot.")
        page.screenshot(
            path=str(output_path),
            full_page=False,
            timeout=int(timeout_s * 1000),
            animations="disabled",
        )


def _capture_subprocess_direct(output_path: Path, timeout_s: float) -> None:
    code = f"""
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("{CDP_URL}")
    page = None
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "melvor" in pg.url.lower():
                page = pg
                break
        if page:
            break
    if page is None and browser.contexts and browser.contexts[0].pages:
        page = browser.contexts[0].pages[0]
    if page is None:
        raise RuntimeError("No browser page available for screenshot.")
    page.screenshot(path=r"{str(output_path)}", full_page=False, timeout={int(timeout_s * 1000)})
"""
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def take_action_screenshot(phase: str, action_label: str, page: Page | None = None) -> str | None:
    """
    Best-effort screenshot capture before/after action execution.
    Does not raise; prints warning if capture fails.
    """
    enabled = os.environ.get("ACTION_SCREENSHOTS", "1").strip().lower()
    if enabled in {"0", "false", "off", "no"}:
        return None

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    label = f"{ts}_{_sanitize(action_label)}_{_sanitize(phase)}"
    repo_root = Path(__file__).resolve().parents[2]
    screenshots_dir = repo_root / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    output_path = screenshots_dir / f"{label}.png"
    # Slightly higher default avoids intermittent font-load screenshot timeouts.
    timeout_s = float(os.environ.get("ACTION_SCREENSHOT_TIMEOUT_S", "8"))

    # If caller already has an active Playwright page, use it directly.
    if page is not None:
        try:
            page.screenshot(
                path=str(output_path),
                full_page=False,
                timeout=int(timeout_s * 1000),
                animations="disabled",
            )
            return str(output_path)
        except Exception:
            # Fall through to the regular capture path below.
            pass

    # Fast path: in-process Playwright capture.
    try:
        _capture_direct(output_path, timeout_s)
        return str(output_path)
    except Exception as exc:
        exc_msg = str(exc).lower()
        if "sync api inside the asyncio loop" in exc_msg:
            # Called while another Playwright sync context is active (same process).
            # Try subprocess fallback to still capture.
            try:
                _capture_subprocess_direct(output_path, timeout_s)
                return str(output_path)
            except Exception:
                return None
        # One retry in case of transient CDP/page issues.
        try:
            _capture_direct(output_path, timeout_s)
            return str(output_path)
        except Exception as retry_exc:
            # Fallback for nested sync-playwright contexts: subprocess capture.
            try:
                _capture_subprocess_direct(output_path, timeout_s)
                return str(output_path)
            except Exception:
                msg = f"{exc} {retry_exc}".lower()
                if "sync api inside the asyncio loop" in msg:
                    return None
                print(f"[warn] Screenshot capture failed ({phase}): {msg}")
                return None

