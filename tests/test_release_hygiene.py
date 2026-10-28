import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
FORBIDDEN_SUFFIXES = {".pem", ".key", ".sqlite", ".db", ".patch", ".log", ".env"}


def test_tree_contains_only_public_material() -> None:
    allowed = {".github", "docs", "src", "tests", "tools", ".gitignore", "LICENSE", "README.md", "SECURITY.md", "PRIVACY.md", "CONTRIBUTING.md", "pyproject.toml", "MANIFEST.in"}
    ignored = {".git", ".tooling", ".venv", "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__"}
    assert {path.name for path in ROOT.iterdir() if path.name not in ignored} <= allowed
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in ignored for part in path.parts):
            continue
        if path == Path(__file__).resolve():
            continue
        assert path.suffix not in FORBIDDEN_SUFFIXES
        content = path.read_text(encoding="utf-8")
        assert "/" + "home/" not in content
        assert "-" * 5 + "BEGIN " not in content
        assert not re.search(r"\b(?:10|192\.168)\.\d+\.\d+\b", content)
