"""Encrypted Playwright storage-state session store (SDD section 8.3)."""
from __future__ import annotations

import base64
import json
import re
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

KEYRING_SERVICE = "jobhunter"
KEYRING_USERNAME = "session_store_key"
SESSION_FILE_SUFFIX = ".enc"
DEFAULT_SESSION_DIR = Path.home() / ".jobhunter" / "sessions"
MACHINE_ID_PATH = Path.home() / ".jobhunter" / "machine-id"
SALT_PATH = Path.home() / ".jobhunter" / "salt"
_SESSION_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_KEY_ITERATIONS = 390_000


class KeyringBackend(Protocol):
    """Subset of the keyring API used by the session store."""

    def get_password(self, service: str, username: str) -> str | None: ...

    def set_password(self, service: str, username: str, password: str) -> None: ...


class SessionStoreError(RuntimeError):
    """Raised when an encrypted session file cannot be decoded into storage state."""


class SessionStore:
    """Save and load encrypted Playwright `storage_state` dictionaries."""

    def __init__(
        self,
        *,
        root_dir: str | Path = DEFAULT_SESSION_DIR,
        keyring_backend: KeyringBackend | None = None,
        machine_id_provider: Callable[[], str] | None = None,
        salt_provider: Callable[[], bytes] | None = None,
    ) -> None:
        self.root_dir = Path(root_dir)
        self._keyring_backend = keyring_backend
        self._machine_id_provider = machine_id_provider or _default_machine_id
        self._salt_provider = salt_provider or _default_salt

    def save(self, name: str, state_dict: dict[str, Any]) -> None:
        """Encrypt and persist a Playwright storage-state dictionary."""
        path = self._path_for(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
        path.write_bytes(self._fernet().encrypt(payload))

    def load(self, name: str) -> dict[str, Any]:
        """Decrypt and return a Playwright storage-state dictionary."""
        path = self._path_for(name)
        encrypted = path.read_bytes()
        try:
            decoded = self._fernet().decrypt(encrypted)
            payload = json.loads(decoded.decode("utf-8"))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SessionStoreError(f"Session file could not be decrypted: {name}") from exc
        if not isinstance(payload, dict):
            raise SessionStoreError("Session file must decrypt to a JSON object.")
        return payload

    def exists(self, name: str) -> bool:
        """Return whether an encrypted session file exists."""
        return self._path_for(name).exists()

    def delete(self, name: str) -> None:
        """Remove an encrypted session file if it exists."""
        path = self._path_for(name)
        if path.exists():
            path.unlink()

    def _get_key(self) -> bytes:
        keyring_backend = self._keyring()
        stored = keyring_backend.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if stored:
            return stored.encode("ascii")
        machine_id = self._machine_id_provider()
        salt = self._salt_provider()
        key = derive_session_key(machine_id, salt)
        keyring_backend.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key.decode("ascii"))
        return key

    def _fernet(self) -> Fernet:
        return Fernet(self._get_key())

    def _path_for(self, name: str) -> Path:
        if not _SESSION_NAME_RE.fullmatch(name):
            raise ValueError(
                "session name must contain only letters, numbers, dots, dashes, or underscores"
            )
        return self.root_dir / f"{name}{SESSION_FILE_SUFFIX}"

    def _keyring(self) -> KeyringBackend:
        if self._keyring_backend is not None:
            return self._keyring_backend
        import keyring

        return keyring


def derive_session_key(machine_id: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a machine identifier using PBKDF2HMAC/SHA-256."""
    if not machine_id:
        raise ValueError("machine_id must not be empty")
    if not salt:
        raise ValueError("salt must not be empty")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KEY_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(machine_id.encode("utf-8")))


def _load_or_create_machine_id(path: Path) -> str:
    """Return a stable hex machine ID, creating one on first call."""
    if path.exists():
        content = path.read_text(encoding="utf-8").strip()
        if content and len(content) == 32:
            try:
                int(content, 16)
                return content
            except ValueError:
                pass
    machine_id = secrets.token_hex(16)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(machine_id, encoding="utf-8")
    # Re-read from disk to return the canonical value (handles races
    # where another process may have written concurrently).
    return path.read_text(encoding="utf-8").strip()


def _load_or_create_salt(path: Path) -> bytes:
    """Return a stable 32-byte salt, creating one on first call."""
    if path.exists():
        content = path.read_text(encoding="utf-8").strip()
        if content and len(content) == 64:
            try:
                salt = bytes.fromhex(content)
                if len(salt) == 32:
                    return salt
            except ValueError:
                pass
    salt = secrets.token_bytes(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(salt.hex(), encoding="utf-8")
    # Re-read from disk to return the canonical value (handles races).
    return bytes.fromhex(path.read_text(encoding="utf-8").strip())


def _default_machine_id() -> str:
    return _load_or_create_machine_id(MACHINE_ID_PATH)


def _default_salt() -> bytes:
    return _load_or_create_salt(SALT_PATH)
