"""Locate the shared toolkit; keep the Skill free of duplicated Telnet implementation."""

import os
from pathlib import Path
import subprocess
import sys

def launch():
    root = Path(os.environ.get("MA2_TOOLKIT_ROOT", Path(__file__).resolve().parents[4]))
    if (root / "pyproject.toml").is_file() and (root / "src/grandma2_toolkit").is_dir():
        # Use the repository's locked environment without assuming the caller's cwd.
        return subprocess.call(["uv", "run", "--locked", "--directory", str(root), "grandma2", *sys.argv[1:]])
    from grandma2_toolkit.cli import main
    return main()


if __name__ == "__main__":
    raise SystemExit(launch())
