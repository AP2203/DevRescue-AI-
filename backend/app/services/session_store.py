import os
import time
import json
import sqlite3
import secrets
import hashlib
import hmac
import base64
from typing import Dict, Any, Optional
from app.core.config import settings

class GitHubSessionStore:
    """
    Persistent SQLite-backed session store for authenticated GitHub sessions.
    Stores cryptographically protected tokens and supports server restarts/reloads.
    Never exposes raw tokens or secrets to client-side.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or getattr(settings, "DATABASE_PATH", os.path.join(settings.BASE_DIR, "devrescue_sessions.db"))
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass
        return conn

    def _init_db(self):
        # Ensure parent directory exists if path has directories
        parent = os.path.dirname(self.db_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS github_sessions (
                    session_id TEXT PRIMARY KEY,
                    encrypted_token TEXT NOT NULL,
                    user_login TEXT,
                    user_data TEXT,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );
            """)
            conn.commit()

    def _get_secret_key(self) -> bytes:
        secret = settings.GITHUB_CLIENT_SECRET or "devrescue_secure_session_key_fallback"
        return secret.encode("utf-8")

    def _encrypt_token(self, token: str) -> str:
        if not token:
            return ""
        salt = secrets.token_bytes(16)
        token_bytes = token.encode("utf-8")
        secret = self._get_secret_key()
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(token_bytes):
            keystream.extend(hmac.new(secret + salt, counter.to_bytes(4, "big"), hashlib.sha256).digest())
            counter += 1
        encrypted = bytes(b ^ k for b, k in zip(token_bytes, keystream[:len(token_bytes)]))
        return base64.b64encode(salt + encrypted).decode("utf-8")

    def _decrypt_token(self, cipher_text: str) -> str:
        if not cipher_text:
            return ""
        try:
            raw = base64.b64decode(cipher_text.encode("utf-8"))
            if len(raw) < 16:
                return cipher_text
            salt, encrypted = raw[:16], raw[16:]
            secret = self._get_secret_key()
            keystream = bytearray()
            counter = 0
            while len(keystream) < len(encrypted):
                keystream.extend(hmac.new(secret + salt, counter.to_bytes(4, "big"), hashlib.sha256).digest())
                counter += 1
            decrypted = bytes(b ^ k for b, k in zip(encrypted, keystream[:len(encrypted)]))
            return decrypted.decode("utf-8")
        except Exception:
            return cipher_text

    def create_oauth_state(self) -> str:
        state = secrets.token_urlsafe(32)
        now = time.time()
        expires_at = now + 600  # 10 minutes
        with self._get_connection() as conn:
            conn.execute("DELETE FROM oauth_states WHERE expires_at < ?", (now,))
            conn.execute(
                "INSERT INTO oauth_states (state, created_at, expires_at) VALUES (?, ?, ?)",
                (state, now, expires_at)
            )
            conn.commit()
        return state

    def verify_oauth_state(self, state: str) -> bool:
        if not state:
            return False
        now = time.time()
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT state, expires_at FROM oauth_states WHERE state = ?",
                (state,)
            ).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
            conn.commit()
            return now <= row["expires_at"]

    def create_session(
        self,
        access_token: str,
        user_data: Optional[Dict[str, Any]] = None,
        expires_in: Optional[int] = None
    ) -> str:
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        expires_at = now + (expires_in if expires_in is not None else (86400 * 7))
        user_data = user_data or {}
        user_login = user_data.get("login") or ""
        user_json = json.dumps(user_data)
        encrypted_token = self._encrypt_token(access_token)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO github_sessions (session_id, encrypted_token, user_login, user_data, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, encrypted_token, user_login, user_json, now, expires_at)
            )
            conn.commit()
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not session_id:
            return None
        now = time.time()
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT session_id, encrypted_token, user_login, user_data, created_at, expires_at FROM github_sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            if not row:
                return None

            if now > row["expires_at"]:
                conn.execute("DELETE FROM github_sessions WHERE session_id = ?", (session_id,))
                conn.commit()
                return None

            decrypted_token = self._decrypt_token(row["encrypted_token"])
            user_data = {}
            if row["user_data"]:
                try:
                    user_data = json.loads(row["user_data"])
                except Exception:
                    user_data = {"login": row["user_login"]}
            elif row["user_login"]:
                user_data = {"login": row["user_login"]}

            return {
                "session_id": row["session_id"],
                "access_token": decrypted_token,
                "user": user_data,
                "user_login": row["user_login"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"]
            }

    def get_token(self, session_id: str) -> Optional[str]:
        session = self.get_session(session_id)
        if not session:
            return None
        return session.get("access_token")

    def get_user(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session:
            return None
        return session.get("user")

    def set_user(self, session_id: str, user_data: Dict[str, Any]):
        if not session_id or not user_data:
            return
        user_login = user_data.get("login") or ""
        user_json = json.dumps(user_data)
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE github_sessions SET user_login = ?, user_data = ? WHERE session_id = ?",
                (user_login, user_json, session_id)
            )
            conn.commit()

    def delete_session(self, session_id: str) -> bool:
        if not session_id:
            return False
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM github_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cur.rowcount > 0

    def clean_expired(self):
        now = time.time()
        with self._get_connection() as conn:
            conn.execute("DELETE FROM github_sessions WHERE expires_at < ?", (now,))
            conn.execute("DELETE FROM oauth_states WHERE expires_at < ?", (now,))
            conn.commit()

session_store = GitHubSessionStore()

