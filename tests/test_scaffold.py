"""C-001 scaffold smoke test — the package tree and tooling exist and import.

This is the executable acceptance for the scaffold chunk: every built-in package
imports, the tooling files are present, and the user drop-zone directories exist.
"""
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BUILTIN_PACKAGES = [
    "core",
    "core.models",
    "core.connectors",
    "core.ai_providers",
    "core.profile_inputs",
    "core.auth",
    "core.ai_engine",
    "ui",
    "ui.cli",
]

TOOLING_FILES = ["pyproject.toml", "requirements.txt"]

DROP_ZONES = ["connectors", "ai_providers", "profile_inputs", "fixtures"]


def test_builtin_packages_import():
    for pkg in BUILTIN_PACKAGES:
        assert importlib.import_module(pkg) is not None


def test_tooling_files_present():
    for name in TOOLING_FILES:
        assert (ROOT / name).is_file(), f"missing tooling file: {name}"


def test_drop_zone_dirs_present():
    for name in DROP_ZONES:
        assert (ROOT / name).is_dir(), f"missing drop-zone dir: {name}"
