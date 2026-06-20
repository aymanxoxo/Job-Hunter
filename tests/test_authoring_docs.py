"""C-038 - authoring documentation coverage."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_authoring_docs_exist_and_are_linked_from_readme():
    readme = _text("README.md")

    for path in ("CONNECTOR_GUIDE.md", "PROVIDER_GUIDE.md", "PROFILE_INPUT_GUIDE.md"):
        assert (ROOT / path).exists()
        assert path in readme


def test_connector_guide_covers_contract_discovery_config_and_tests():
    guide = _text("CONNECTOR_GUIDE.md")

    for expected in (
        "BaseConnector",
        "async def search",
        "connectors/",
        "auth_methods",
        "config.yaml",
        "tests/contracts/connector_contract.py",
        "python -m pytest",
    ):
        assert expected in guide


def test_provider_guide_covers_contract_auth_engine_and_tests():
    guide = _text("PROVIDER_GUIDE.md")

    for expected in (
        "BaseAIProvider",
        "generate_criteria",
        "score_jobs",
        "AIEngine",
        "auth_methods",
        "ai_providers/",
        "tests/contracts/provider_contract.py",
    ):
        assert expected in guide


def test_profile_input_guide_covers_contract_discovery_and_tests():
    guide = _text("PROFILE_INPUT_GUIDE.md")

    for expected in (
        "BaseProfileInput",
        "async def to_text",
        "profile_inputs/",
        "accepts",
        "profile.input",
        "python -m pytest",
    ):
        assert expected in guide
