#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _daemon_cli import run_action_cli

if __name__ == "__main__":
    raise SystemExit(run_action_cli("mastery", sys.argv[1:]))
