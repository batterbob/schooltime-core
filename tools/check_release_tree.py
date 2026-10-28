"""Generic fail-closed tracked-file release hygiene check."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

ALLOWED_TOP = {".github", "docs", "src", "tests", "tools", ".gitignore", "LICENSE", "README.md", "SECURITY.md", "PRIVACY.md", "CONTRIBUTING.md", "pyproject.toml", "MANIFEST.in"}
BAD_SUFFIXES = {".pem", ".key", ".sqlite", ".db", ".patch", ".log", ".env", ".tar", ".zip"}
MARKERS = (b"-----begin ", b"password=", b"secret=", b"/" + b"home/")


def tracked() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], check=True, stdout=subprocess.PIPE)
    return [entry.decode("utf-8") for entry in result.stdout.split(b"\0") if entry]


def reachable_blobs() -> list[str]:
    objects = subprocess.run(["git", "rev-list", "--objects", "--all"], check=True, text=True, stdout=subprocess.PIPE).stdout.splitlines()
    blobs: list[str] = []
    for line in objects:
        object_id = line.split(maxsplit=1)[0]
        kind = subprocess.run(["git", "cat-file", "-t", object_id], check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        if kind == "blob":
            blobs.append(object_id)
    return blobs


def blob_data(object_id: str) -> bytes:
    return subprocess.run(["git", "cat-file", "blob", object_id], check=True, stdout=subprocess.PIPE).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generic", action="store_true")
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()
    if args.private:
        root = subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        if root != str(Path.cwd()) or subprocess.run(["git", "status", "--porcelain"], check=True, text=True, stdout=subprocess.PIPE).stdout:
            print("FAIL repository root or worktree rule")
            return 1
    denylist = os.environ.get("SCHOOLTIME_PRIVATE_DENYLIST")
    denied = []
    if args.private:
        if not denylist or not Path(denylist).is_file():
            print("FAIL private denylist rule")
            return 1
        denied = [
            term.encode("utf-8")
            for line in Path(denylist).read_text(encoding="utf-8").splitlines()
            if (term := line.strip()) and not term.startswith("#")
        ]
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
        if any(term in name.encode() or term in data for term in denied):
            print(f"FAIL {name}: private denylist rule")
            failed = True
    if args.private:
        blobs = reachable_blobs()
        for object_id in blobs:
            data = blob_data(object_id)
            if any(term in data for term in denied):
                print(f"FAIL object {object_id}: private denylist rule")
                failed = True
        print(f"private gate scanned {len(tracked())} tracked files and {len(blobs)} reachable blobs")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
