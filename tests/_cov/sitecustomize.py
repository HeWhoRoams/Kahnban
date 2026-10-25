"""Starts coverage in every Python process that inherits PYTHONPATH=tests/_cov.

Used only by ``python tests/run_coverage.py``: child processes (the CLI, the MCP server, the
simulation's workers) report their lines too, which a plain ``coverage run -m pytest`` misses.
"""

try:
    import coverage

    coverage.process_startup()
except ImportError:  # coverage is a dev dependency
    pass
