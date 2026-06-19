"""C-009 - plugin discovery via importlib."""
from __future__ import annotations

from pathlib import Path

from core.ai_providers import BaseAIProvider
from core.connectors import BaseConnector
from core.models.job import Job
from core.models.search_criteria import SearchCriteria
from core.profile_inputs import BaseProfileInput
from core.runner import discover_plugins


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_discovers_valid_connector_class(tmp_path):
    _write(
        tmp_path / "mock_connector.py",
        """
from core.connectors import BaseConnector
from core.models.job import Job

class MockConnector(BaseConnector):
    name = "mock"

    async def search(self, criteria):
        return [Job(id="1", title="Dev", company="Acme", url="https://x", source=self.name)]
""",
    )

    plugins = discover_plugins(tmp_path, BaseConnector)

    assert [plugin.__name__ for plugin in plugins] == ["MockConnector"]
    connector = plugins[0]()
    assert isinstance(connector, BaseConnector)
    assert connector.name == "mock"


def test_discovers_valid_provider_class(tmp_path):
    _write(
        tmp_path / "mock_provider.py",
        """
from core.ai_providers import BaseAIProvider
from core.models.search_criteria import SearchCriteria

class MockProvider(BaseAIProvider):
    name = "mock-ai"

    async def generate_criteria(self, profile):
        return SearchCriteria(raw_profile=profile)

    async def score_jobs(self, jobs, criteria):
        return jobs
""",
    )

    plugins = discover_plugins(tmp_path, BaseAIProvider)

    assert [plugin.__name__ for plugin in plugins] == ["MockProvider"]
    assert isinstance(plugins[0](), BaseAIProvider)


def test_discovers_valid_profile_input_class(tmp_path):
    _write(
        tmp_path / "mock_profile.py",
        """
from core.profile_inputs import BaseProfileInput

class MockProfileInput(BaseProfileInput):
    name = "mock-profile"

    async def to_text(self, source):
        return str(source)
""",
    )

    plugins = discover_plugins(tmp_path, BaseProfileInput)

    assert [plugin.__name__ for plugin in plugins] == ["MockProfileInput"]
    profile_input = plugins[0]()
    assert isinstance(profile_input, BaseProfileInput)
    assert profile_input.name == "mock-profile"


def test_skips_private_base_and_unrelated_classes(tmp_path):
    _write(
        tmp_path / "_private.py",
        """
from core.connectors import BaseConnector
class PrivateConnector(BaseConnector):
    async def search(self, criteria):
        return []
""",
    )
    _write(
        tmp_path / "base_fake.py",
        """
from core.connectors import BaseConnector
class BaseFakeConnector(BaseConnector):
    async def search(self, criteria):
        return []
""",
    )
    _write(
        tmp_path / "unrelated.py",
        """
class NotAConnector:
    pass
""",
    )

    assert discover_plugins(tmp_path, BaseConnector) == []


def test_excludes_imported_base_class_itself(tmp_path):
    _write(
        tmp_path / "imports_base.py",
        """
from core.connectors import BaseConnector
""",
    )

    assert discover_plugins(tmp_path, BaseConnector) == []


def test_excludes_abstract_subclasses(tmp_path):
    _write(
        tmp_path / "abstract_connector.py",
        """
from core.connectors import BaseConnector

class AbstractConnector(BaseConnector):
    pass
""",
    )

    assert discover_plugins(tmp_path, BaseConnector) == []


def test_missing_directory_returns_empty(tmp_path):
    assert discover_plugins(tmp_path / "missing", BaseConnector) == []


def test_same_stem_modules_do_not_collide(tmp_path):
    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir()
    two.mkdir()
    plugin_text = """
from core.profile_inputs import BaseProfileInput

class {name}(BaseProfileInput):
    name = "{plugin_name}"

    async def to_text(self, source):
        return str(source)
"""
    _write(one / "plugin.py", plugin_text.format(name="OneInput", plugin_name="one"))
    _write(two / "plugin.py", plugin_text.format(name="TwoInput", plugin_name="two"))

    first = discover_plugins(one, BaseProfileInput)
    second = discover_plugins(two, BaseProfileInput)

    assert first[0].__name__ == "OneInput"
    assert second[0].__name__ == "TwoInput"
    assert first[0]().name == "one"
    assert second[0]().name == "two"


async def test_returned_connector_class_is_usable(tmp_path):
    _write(
        tmp_path / "usable_connector.py",
        """
from core.connectors import BaseConnector
from core.models.job import Job

class UsableConnector(BaseConnector):
    name = "usable"

    async def search(self, criteria):
        return [Job(id="1", title="Dev", company="Acme", url="https://x", source=self.name)]
""",
    )

    connector = discover_plugins(tmp_path, BaseConnector)[0]()
    jobs = await connector.search(SearchCriteria())

    assert isinstance(jobs[0], Job)
    assert jobs[0].source == "usable"


def test_skips_plugin_file_that_fails_to_import(tmp_path):
    # C-049: a single broken drop-in plugin must not abort discovery of the others.
    _write(
        tmp_path / "broken_connector.py",
        "import a_module_that_does_not_exist_xyz\n",
    )
    _write(
        tmp_path / "good_connector.py",
        """
from core.connectors import BaseConnector

class GoodConnector(BaseConnector):
    name = "good"

    async def search(self, criteria):
        return []
""",
    )

    plugins = discover_plugins(tmp_path, BaseConnector)

    assert [plugin.__name__ for plugin in plugins] == ["GoodConnector"]
