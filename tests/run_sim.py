"""Launcher: ``python tests/run_sim.py run [S1 ...]``. See docs/simulation-plan.md.

A module run (``python -m tests.sim``) is shadowed by an unrelated ``tests`` package that some
Python installs carry in site-packages, so the simulation is started from this file instead.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sim.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
