# services/auth_service.py
"""
Authentication service. Local SQLite auth with hashed passwords.
No server needed — everything stored in local DB.
"""

import hashlib
import secrets
from typing import Optional, Dict
from data.sqlite_repo import SQLiteRepository
from utils.logger import setup_logger

logger = setup_logger(__name__)

PBKDF2_ITERATIONS = 600_000  # OWASP recommended


def _hash_password(password: str, salt: str) -> str:
    """Hash password with PBKDF2-SHA256 (secure)."""
    dk = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'),
        salt.encode('utf-8'), PBKDF2_ITERATIONS
    )
    return f"pbkdf2${PBKDF2_ITERATIONS}${dk.hex()}"


def _hash_password_legacy(password: str, salt: str) -> str:
    """Legacy SHA-256 hash — for verifying old accounts only."""
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()


def _verify_password(password: str, salt: str, stored_hash: str) -> bool:
    """Verify password against stored hash (supports both old and new format)."""
    if stored_hash.startswith('pbkdf2$'):
        return _hash_password(password, salt) == stored_hash
    else:
        return _hash_password_legacy(password, salt) == stored_hash


class AuthService:
    def __init__(self, db: SQLiteRepository):
        self.db = db
        self.current_user: Optional[Dict] = None

    def sign_up(self, username: str, password: str, display_name: str = "") -> Dict:
        """Register new user. Returns user dict or raises ValueError."""
        username = username.strip().lower()

        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(password) < 4:
            raise ValueError("Password must be at least 4 characters")

        # Check if username exists
        existing = self.db.get_user_by_username(username)
        if existing:
            raise ValueError("Username already taken")

        salt = secrets.token_hex(16)
        password_hash = _hash_password(password, salt)

        user_id = self.db.create_user(
            username=username,
            password_hash=password_hash,
            salt=salt,
            display_name=display_name or username,
        )

        self.current_user = self.db.get_user(user_id)
        logger.info(f"User registered: {username} (id={user_id})")
        return self.current_user

    def sign_in(self, username: str, password: str) -> Dict:
        """Sign in. Returns user dict or raises ValueError."""
        username = username.strip().lower()

        user = self.db.get_user_by_username(username)
        if not user:
            raise ValueError("Invalid username or password")

        if not _verify_password(password, user['salt'], user['password_hash']):
            raise ValueError("Invalid username or password")

        # Auto-migrate legacy SHA-256 hash to PBKDF2
        if not user['password_hash'].startswith('pbkdf2$'):
            new_hash = _hash_password(password, user['salt'])
            self.db.conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, user['id'])
            )
            self.db.conn.commit()
            logger.info(f"Migrated password hash to PBKDF2 for user {username}")

        self.current_user = user
        logger.info(f"User signed in: {username}")
        return self.current_user

    def sign_out(self):
        """Sign out current user."""
        if self.current_user:
            logger.info(f"User signed out: {self.current_user['username']}")
        self.current_user = None

    def get_current_user(self) -> Optional[Dict]:
        return self.current_user

    def get_current_user_id(self) -> Optional[int]:
        return self.current_user['id'] if self.current_user else None
