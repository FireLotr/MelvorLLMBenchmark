"""Re-export navigate from scripts/actions for observation scripts (import path)."""

import sys
from pathlib import Path

_actions = Path(__file__).resolve().parent.parent / "actions"
if str(_actions) not in sys.path:
    sys.path.insert(0, str(_actions))

from navigate import navigate  # noqa: E402

__all__ = ["navigate"]
