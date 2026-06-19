"""C-019 - encrypted session store."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from core.auth import SessionStore
from core.auth.session_store import (
    KEYRING_SERVICE,
    KEYRING_USERNAME,
    SESSION_FILE_SUFFIX,
    SessionStoreError,
    derive_session_key,
)


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}
        self.set_calls: list[tuple[str, str, str]] = []

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password
        self.set_calls.append((service, username, password))


def _state() -> dict:
    return {
        "cookies": [
            {
                "name": "li_at",
                "value": "secret-cookie",
                "domain": ".linkedin.com",
                "path": "/",
            }
        ],
        "origins": [],
    }


def test_save_encrypts_and_load_decrypts_playwright_storage_state(tmp_path: Path):
    keyring = FakeKeyring()
    store = SessionStore(
        root_dir=tmp_path,
        keyring_backend=keyring,
        machine_id_provider=lambda: "machine-a",
    )

    store.save("linkedin", _state())
    session_file = tmp_path / f"linkedin{SESSION_FILE_SUFFIX}"

    assert session_file.exists()
    assert b"secret-cookie" not in session_file.read_bytes()
    assert store.load("linkedin") == _state()
    assert store.exists("linkedin") is True


def test_get_key_derives_once_and_reuses_keyring_value(tmp_path: Path):
    keyring = FakeKeyring()
    first = SessionStore(
        root_dir=tmp_path,
        keyring_backend=keyring,
        machine_id_provider=lambda: "machine-a",
    )
    second = SessionStore(
        root_dir=tmp_path,
        keyring_backend=keyring,
        machine_id_provider=lambda: "machine-b",
    )

    first.save("linkedin", _state())
    saved_key = keyring.values[(KEYRING_SERVICE, KEYRING_USERNAME)]

    assert saved_key == derive_session_key("machine-a").decode("ascii")
    assert keyring.set_calls == [(KEYRING_SERVICE, KEYRING_USERNAME, saved_key)]
    assert second.load("linkedin") == _state()
    assert len(keyring.set_calls) == 1


def test_delete_removes_session_file_and_is_idempotent(tmp_path: Path):
    store = SessionStore(
        root_dir=tmp_path,
        keyring_backend=FakeKeyring(),
        machine_id_provider=lambda: "machine-a",
    )
    store.save("linkedin", _state())

    store.delete("linkedin")
    store.delete("linkedin")

    assert store.exists("linkedin") is False


def test_load_missing_session_raises_file_not_found(tmp_path: Path):
    store = SessionStore(
        root_dir=tmp_path,
        keyring_backend=FakeKeyring(),
        machine_id_provider=lambda: "machine-a",
    )

    with pytest.raises(FileNotFoundError):
        store.load("linkedin")


@pytest.mark.parametrize("name", ["", "../linkedin", "linked/in", "linked\\in"])
def test_session_names_cannot_escape_store_directory(tmp_path: Path, name: str):
    store = SessionStore(
        root_dir=tmp_path,
        keyring_backend=FakeKeyring(),
        machine_id_provider=lambda: "machine-a",
    )

    with pytest.raises(ValueError, match="session name"):
        store.save(name, _state())


def test_load_rejects_decrypted_non_object_state(tmp_path: Path):
    keyring = FakeKeyring()
    keyring.set_password(
        KEYRING_SERVICE,
        KEYRING_USERNAME,
        base64.urlsafe_b64encode(b"0" * 32).decode("ascii"),
    )
    store = SessionStore(root_dir=tmp_path, keyring_backend=keyring)
    store.save("linkedin", {"cookies": [], "origins": []})
    # Replace the encrypted payload with a valid encrypted JSON array.
    token = store._fernet().encrypt(json.dumps([]).encode("utf-8"))
    (tmp_path / f"linkedin{SESSION_FILE_SUFFIX}").write_bytes(token)

    with pytest.raises(SessionStoreError, match="object"):
        store.load("linkedin")
