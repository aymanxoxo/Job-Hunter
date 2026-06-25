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
    _load_or_create_machine_id,
    _load_or_create_salt,
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
        salt_provider=lambda: b"salt-a" * 4,
    )

    store.save("linkedin", _state())
    session_file = tmp_path / f"linkedin{SESSION_FILE_SUFFIX}"

    assert session_file.exists()
    assert b"secret-cookie" not in session_file.read_bytes()
    assert store.load("linkedin") == _state()
    assert store.exists("linkedin") is True


def test_get_key_derives_once_and_reuses_keyring_value(tmp_path: Path):
    keyring = FakeKeyring()
    salt = b"test-salt" * 4  # 32 bytes
    first = SessionStore(
        root_dir=tmp_path,
        keyring_backend=keyring,
        machine_id_provider=lambda: "machine-a",
        salt_provider=lambda: salt,
    )
    second = SessionStore(
        root_dir=tmp_path,
        keyring_backend=keyring,
        machine_id_provider=lambda: "machine-b",
        salt_provider=lambda: salt,
    )

    first.save("linkedin", _state())
    saved_key = keyring.values[(KEYRING_SERVICE, KEYRING_USERNAME)]

    assert saved_key == derive_session_key("machine-a", salt).decode("ascii")
    assert keyring.set_calls == [(KEYRING_SERVICE, KEYRING_USERNAME, saved_key)]
    assert second.load("linkedin") == _state()
    assert len(keyring.set_calls) == 1


def test_delete_removes_session_file_and_is_idempotent(tmp_path: Path):
    store = SessionStore(
        root_dir=tmp_path,
        keyring_backend=FakeKeyring(),
        machine_id_provider=lambda: "machine-a",
        salt_provider=lambda: b"salt-a" * 4,
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
        salt_provider=lambda: b"salt-a" * 4,
    )

    with pytest.raises(FileNotFoundError):
        store.load("linkedin")


@pytest.mark.parametrize("name", ["", "../linkedin", "linked/in", "linked\\in"])
def test_session_names_cannot_escape_store_directory(tmp_path: Path, name: str):
    store = SessionStore(
        root_dir=tmp_path,
        keyring_backend=FakeKeyring(),
        machine_id_provider=lambda: "machine-a",
        salt_provider=lambda: b"salt-a" * 4,
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
    store = SessionStore(
        root_dir=tmp_path,
        keyring_backend=keyring,
        salt_provider=lambda: b"salt-a" * 4,
    )
    store.save("linkedin", {"cookies": [], "origins": []})
    # Replace the encrypted payload with a valid encrypted JSON array.
    token = store._fernet().encrypt(json.dumps([]).encode("utf-8"))
    (tmp_path / f"linkedin{SESSION_FILE_SUFFIX}").write_bytes(token)

    with pytest.raises(SessionStoreError, match="object"):
        store.load("linkedin")


# --- C-067 new tests below ---


def test_machine_id_created_on_first_call(tmp_path: Path):
    machine_id_path = tmp_path / "machine-id"
    assert not machine_id_path.exists()
    result = _load_or_create_machine_id(machine_id_path)
    assert machine_id_path.exists()
    assert result
    assert isinstance(result, str)
    # Should be hex (32 chars for 16 bytes)
    assert len(result) == 32
    try:
        int(result, 16)
    except ValueError:
        pytest.fail("machine_id is not valid hex")


def test_machine_id_stable_across_calls(tmp_path: Path):
    machine_id_path = tmp_path / "machine-id"
    first = _load_or_create_machine_id(machine_id_path)
    second = _load_or_create_machine_id(machine_id_path)
    assert first == second


def test_machine_id_not_uuid_getnode(tmp_path: Path):
    machine_id_path = tmp_path / "machine-id"
    result = _load_or_create_machine_id(machine_id_path)
    import uuid
    assert result != str(uuid.getnode())


def test_salt_created_on_first_call(tmp_path: Path):
    salt_path = tmp_path / "salt"
    assert not salt_path.exists()
    result = _load_or_create_salt(salt_path)
    assert salt_path.exists()
    assert isinstance(result, bytes)
    assert len(result) == 32


def test_salt_stable_across_calls(tmp_path: Path):
    salt_path = tmp_path / "salt"
    first = _load_or_create_salt(salt_path)
    second = _load_or_create_salt(salt_path)
    assert first == second


def test_derive_session_key_rejects_empty_salt():
    with pytest.raises(ValueError, match="salt must not be empty"):
        derive_session_key("machine-a", b"")


def test_machine_id_regenerates_on_empty_file(tmp_path: Path):
    machine_id_path = tmp_path / "machine-id"
    machine_id_path.write_text("   \n", encoding="utf-8")
    result = _load_or_create_machine_id(machine_id_path)
    assert result
    assert len(result) == 32
    assert machine_id_path.read_text(encoding="utf-8").strip() == result


def test_machine_id_regenerates_on_invalid_hex(tmp_path: Path):
    machine_id_path = tmp_path / "machine-id"
    machine_id_path.write_text("not-a-hex-string-at-all!!", encoding="utf-8")
    result = _load_or_create_machine_id(machine_id_path)
    assert result
    assert len(result) == 32
    assert machine_id_path.read_text(encoding="utf-8").strip() == result


def test_salt_regenerates_on_empty_file(tmp_path: Path):
    salt_path = tmp_path / "salt"
    salt_path.write_text("   \n", encoding="utf-8")
    result = _load_or_create_salt(salt_path)
    assert isinstance(result, bytes)
    assert len(result) == 32
    assert bytes.fromhex(salt_path.read_text(encoding="utf-8").strip()) == result


def test_salt_regenerates_on_invalid_hex(tmp_path: Path):
    salt_path = tmp_path / "salt"
    salt_path.write_text("not-hex!", encoding="utf-8")
    result = _load_or_create_salt(salt_path)
    assert isinstance(result, bytes)
    assert len(result) == 32
    assert bytes.fromhex(salt_path.read_text(encoding="utf-8").strip()) == result


def test_salt_regenerates_on_short_hex(tmp_path: Path):
    salt_path = tmp_path / "salt"
    salt_path.write_text("aabbccdd", encoding="utf-8")
    result = _load_or_create_salt(salt_path)
    assert isinstance(result, bytes)
    assert len(result) == 32
    assert bytes.fromhex(salt_path.read_text(encoding="utf-8").strip()) == result


def test_derive_session_key_accepts_salt_param():
    machine_id = "machine-a"
    salt_a = b"salt-a" * 4  # 32 bytes
    salt_b = b"salt-b" * 4
    key_a = derive_session_key(machine_id, salt_a)
    key_b = derive_session_key(machine_id, salt_b)
    # valid Fernet key: base64url, 44 chars ending with '='
    assert isinstance(key_a, bytes)
    assert len(key_a) == 44
    assert key_a.endswith(b"=")
    assert key_a != key_b


def test_session_store_save_load_round_trip_with_injected_providers(tmp_path: Path):
    keyring = FakeKeyring()
    store = SessionStore(
        root_dir=tmp_path,
        keyring_backend=keyring,
        machine_id_provider=lambda: "machine-a",
        salt_provider=lambda: b"salt-a" * 4,
    )
    store.save("linkedin", _state())
    loaded = store.load("linkedin")
    assert loaded == _state()


def test_session_store_key_stable_when_providers_stable(tmp_path: Path):
    keyring = FakeKeyring()
    first = SessionStore(
        root_dir=tmp_path,
        keyring_backend=keyring,
        machine_id_provider=lambda: "machine-a",
        salt_provider=lambda: b"salt-a" * 4,
    )
    second = SessionStore(
        root_dir=tmp_path,
        keyring_backend=keyring,
        machine_id_provider=lambda: "machine-a",
        salt_provider=lambda: b"salt-a" * 4,
    )
    first.save("linkedin", _state())
    assert second.load("linkedin") == _state()
