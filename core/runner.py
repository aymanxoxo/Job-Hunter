"""Plugin discovery helpers (SDD §5.1).

C-009 intentionally implements only discovery. Pipeline orchestration, config selection, auth
resolution, parallel search, and result merging land in later runner chunks.
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
from pathlib import Path
from typing import TypeVar

T = TypeVar("T", bound=type)


def discover_plugins(directory: str | Path, base_class: T) -> list[T]:
    """Load concrete subclasses of ``base_class`` from direct ``*.py`` files in ``directory``."""
    plugin_dir = Path(directory)
    if not plugin_dir.exists():
        return []

    plugins: list[T] = []
    for py_file in sorted(plugin_dir.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name.startswith("base_"):
            continue
        module = _load_module(py_file)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is base_class or inspect.isabstract(obj):
                continue
            if issubclass(obj, base_class):
                plugins.append(obj)
    return plugins


def _load_module(path: Path):
    module_name = _module_name_for_path(path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import plugin module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_name_for_path(path: Path) -> str:
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    return f"jobhunter_plugin_{path.stem}_{digest}"
