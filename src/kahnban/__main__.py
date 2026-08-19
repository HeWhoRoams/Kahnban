"""Allow `py -3 -m kahnban <command>`."""

from kahnban.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
