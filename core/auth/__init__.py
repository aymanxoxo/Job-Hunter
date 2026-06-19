"""JobHunter core.auth package."""

from core.auth.auth_strategy import AuthResult, resolve_auth
from core.auth.session_store import SessionStore, SessionStoreError

__all__ = ["AuthResult", "SessionStore", "SessionStoreError", "resolve_auth"]
