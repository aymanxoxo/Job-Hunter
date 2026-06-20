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

from core.logging import get_logger

T = TypeVar("T", bound=type)


def discover_plugins(directory: str | Path, base_class: T) -> list[T]:
    """Load concrete subclasses of ``base_class`` from direct ``*.py`` files in ``directory``."""
    plugin_dir = Path(directory)
    if not plugin_dir.exists():
        return []

    log = get_logger("core.runner.discovery")
    plugins: list[T] = []
    for py_file in sorted(plugin_dir.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name.startswith("base_"):
            continue
        try:
            module = _load_module(py_file)
        except Exception as exc:
            log.warning(
                "plugin import failed; skipped",
                plugin_file=py_file.name,
                error=str(exc),
            )
            continue
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


# --- C-025: pipeline orchestrator (SDD §5.1) ---

import asyncio  # noqa: E402
import uuid  # noqa: E402
from collections.abc import Callable, Sequence  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime  # noqa: E402

from core.ai_providers import BaseAIProvider  # noqa: E402
from core.connectors import BaseConnector  # noqa: E402
from core.models.job import Job  # noqa: E402
from core.models.search_criteria import SearchCriteria  # noqa: E402
from core.output import export_results  # noqa: E402
from core.pipeline import (  # noqa: E402
    dedup_by_url,
    filter_below_threshold,
    merge_results,
    sort_by_score,
)
from core.profile_inputs import BaseProfileInput  # noqa: E402
from core.profile_inputs.text_input import TextProfileInput  # noqa: E402
from core.progress import ProgressEmitter  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class RunResult:
    """The outcome of one pipeline run."""

    run_id: str
    criteria: SearchCriteria
    jobs: tuple[Job, ...]
    exported: tuple[Path, ...]


class Runner:
    """Orchestrates profile -> criteria -> search -> score -> filter -> export (SDD §5.1).

    Collaborators are injected so the full pipeline is testable without network, real plugins,
    or wall-clock time. Search is parallel and fail-graceful: one connector raising is logged
    and skipped, the rest still contribute.
    """

    def __init__(
        self,
        *,
        provider: BaseAIProvider,
        connectors: Sequence[BaseConnector],
        profile_input: BaseProfileInput | None = None,
        output_dir: str | Path = "output/",
        output_format: str = "both",
        emitter: ProgressEmitter | None = None,
        clock: Callable[[], datetime] | None = None,
        logger=None,
        run_id: str | None = None,
    ) -> None:
        self.provider = provider
        self.connectors = tuple(connectors)
        self.profile_input = profile_input or TextProfileInput()
        self.output_dir = output_dir
        self.output_format = output_format
        self.emitter = emitter or ProgressEmitter()
        self.clock = clock or datetime.now
        self.log = logger or get_logger("core.runner")
        self.run_id = run_id or uuid.uuid4().hex

    async def run(self, profile_source) -> RunResult:
        rid = self.run_id

        def emit(stage, state, **fields):
            self.emitter.emit(run_id=rid, stage=stage, state=state, **fields)

        emit("profile", "active")
        profile_text = await self.profile_input.to_text(profile_source)
        emit("profile", "done")

        emit("criteria", "active")
        criteria = await self.provider.generate_criteria(profile_text)
        emit("criteria", "done")

        emit("search", "active", total=len(self.connectors))
        raw = await self._search_all(criteria)
        merged = dedup_by_url(merge_results(raw))
        emit("search", "done", current=len(merged))

        emit("score", "active", total=len(merged))
        scored = await self.provider.score_jobs(list(merged), criteria) if merged else []
        ranked = filter_below_threshold(
            sort_by_score(scored), min_score_threshold=criteria.min_score_threshold
        )
        emit("score", "done", current=len(ranked))

        emit("export", "active")
        exported = export_results(
            ranked, directory=self.output_dir, fmt=self.output_format, moment=self.clock()
        )
        emit("export", "done", current=len(exported))

        return RunResult(
            run_id=rid, criteria=criteria, jobs=tuple(ranked), exported=tuple(exported)
        )

    async def _search_all(self, criteria: SearchCriteria) -> list[list[Job]]:
        enabled = [c for c in self.connectors if getattr(c, "enabled", True)]
        if not enabled:
            return []
        return list(await asyncio.gather(*(self._search_one(c, criteria) for c in enabled)))

    async def _search_one(self, connector: BaseConnector, criteria: SearchCriteria) -> list[Job]:
        name = getattr(connector, "name", "connector")
        try:
            if not await connector.authenticate():
                self.log.warning("connector auth failed; skipped", connector=name)
                return []
            return list(await connector.search(criteria))
        except Exception as exc:
            self.log.warning("connector failed; skipped", connector=name, error=str(exc))
            return []


def _discover_unique(discover, base_class, *dirs: Path) -> list[type]:
    found: list[type] = []
    for directory in dirs:
        for plugin in discover(directory, base_class):
            if plugin not in found:
                found.append(plugin)
    return found


def _select_named(plugins: list[type], name: str) -> type:
    for plugin in plugins:
        if getattr(plugin, "name", None) == name:
            return plugin
    available = ", ".join(sorted(getattr(p, "name", "?") for p in plugins)) or "none"
    raise ValueError(f"No plugin named {name!r} discovered (available: {available})")


def build_runner(
    config,
    *,
    root: Path = _ROOT,
    plugin_root: str | Path | None = None,
    discover=discover_plugins,
    **overrides,
) -> Runner:
    """Wire a Runner from config + plugin discovery (built-in dirs + user drop-zones).

    Built-in plugins ship under ``root/core/...``. User drop-zones (``ai_providers/`` and
    ``connectors/``) are resolved relative to ``plugin_root`` - the current working directory by
    default - so an installed CLI discovers plugins from the project it is run in rather than from
    the package install location. Running from the repo root keeps the old behaviour (cwd == root).
    """
    drop = Path.cwd() if plugin_root is None else Path(plugin_root)
    providers = _discover_unique(
        discover, BaseAIProvider, root / "core" / "ai_providers", drop / "ai_providers"
    )
    connectors = _discover_unique(
        discover, BaseConnector, root / "core" / "connectors", drop / "connectors"
    )
    provider = _select_named(providers, config.ai.provider)()
    return Runner(
        provider=provider,
        connectors=[connector() for connector in connectors],
        output_dir=config.output.directory,
        output_format=config.output.format,
        **overrides,
    )
