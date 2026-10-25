"""Workflow simulation: scripted agents drive the real engine; invariants and a scorecard judge it.

See docs/simulation-plan.md. Run with ``python tests/run_sim.py run`` from the repository root.
KAHNBAN_SIM_SRC points the simulation at another checkout's ``src`` (used by ``compare --against``).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parents[1]
SRC = os.environ.get("KAHNBAN_SIM_SRC") or str(_TESTS.parent / "src")
for _path in (SRC, str(_TESTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
