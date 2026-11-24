"""Sign-in: hashed passwords (PBKDF2) in data/accounts.json and signed session cookies.

Each person can only ever load their own record: the session cookie carries the patient ID,
signed with SESSION_SECRET, and every /api/me route reads the ID from the cookie, never from the request.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

ACCOUNTS_FILE = Path(__file__).resolve().parent.parent / "data" / "accounts.json"
SESSION_HOURS = 12
_ITER = 200_000


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2${_ITER}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, it, salt, dk = stored.split("$")
        got = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(got.hex(), dk)
    except Exception:
        return False


def load_accounts() -> dict[str, str]:
    if not ACCOUNTS_FILE.exists():
        return {}
    return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))


def _secret() -> bytes:
    s = os.getenv("SESSION_SECRET")
    if not s:
        # Stable per install: stored next to the accounts so sessions survive restarts.
        f = ACCOUNTS_FILE.parent / ".session_secret"
        if not f.exists():
            f.write_text(secrets.token_hex(32))
        s = f.read_text().strip()
    return s.encode()


def make_token(pid: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"id": pid, "exp": int(time.time()) + SESSION_HOURS * 3600}).encode()).decode()
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
    except Exception:
        return None
    return data["id"] if data.get("exp", 0) > time.time() else None


class LoginLimiter:
    """At most 5 failed sign-ins per ID per 10 minutes."""

    def __init__(self, limit: int = 5, window: int = 600):
        self.limit, self.window, self.fails = limit, window, {}

    def blocked(self, key: str) -> bool:
        now = time.time()
        self.fails[key] = [t for t in self.fails.get(key, []) if now - t < self.window]
        return len(self.fails[key]) >= self.limit

    def fail(self, key: str) -> None:
        self.fails.setdefault(key, []).append(time.time())

    def reset(self, key: str) -> None:
        self.fails.pop(key, None)


def sign(payload: dict, hours: float) -> str:
    """A short signed token (used for a doctor's viewing session)."""
    body = base64.urlsafe_b64encode(json.dumps(payload | {"exp": int(time.time() + hours * 3600)}).encode()).decode()
    return f"{body}.{hmac.new(_secret(), b'view:' + body.encode(), hashlib.sha256).hexdigest()}"


def unsign(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, hmac.new(_secret(), b"view:" + body.encode(), hashlib.sha256).hexdigest()):
        return None
    try:
        d = json.loads(base64.urlsafe_b64decode(body.encode()))
    except Exception:
        return None
    return d if d.get("exp", 0) > time.time() else None


_acc_lock = __import__("threading").Lock()


def add_account(pid: str, password: str) -> None:
    with _acc_lock:
        acc = load_accounts()
        acc[pid] = hash_password(password)
        ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = ACCOUNTS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(acc, indent=1), encoding="utf-8")
        tmp.replace(ACCOUNTS_FILE)
