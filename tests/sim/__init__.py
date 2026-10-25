"""Workflow simulation: scripted agents drive the real engine; invariants and a scorecard judge it.

See docs/simulation-plan.md. Run with ``python tests/run_sim.py run`` from the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parents[1]
for _path in (_TESTS, _TESTS.parent / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
