"""Generic fail-closed tracked-file release hygiene check."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath

ALLOWED_TOP = {".github", "docs", "src", "tests", "tools", ".gitignore", "LICENSE", "README.md", "SECURITY.md", "PRIVACY.md", "CONTRIBUTING.md", "pyproject.toml", "MANIFEST.in"}
BAD_SUFFIXES = {".pem", ".key", ".sqlite", ".db", ".patch", ".log", ".env", ".tar", ".zip"}
MARKERS = (b"-----begin ", b"password=", b"secret=", b"/" + b"home/")


def tracked() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], check=True, stdout=subprocess.PIPE)
    return [entry.decode("utf-8") for entry in result.stdout.split(b"\0") if entry]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generic", action="store_true")
    parser.parse_args()
    failed = False
    for name in tracked():
        path = PurePosixPath(name)
        if path.is_absolute() or path.parts[0] not in ALLOWED_TOP or path.suffix in BAD_SUFFIXES:
            print(f"FAIL {name}: path rule")
            failed = True
            continue
        data = Path(path).read_bytes()
        if name != "tools/check_release_tree.py" and any(marker in data.lower() for marker in MARKERS):
            print(f"FAIL {name}: content rule")
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
