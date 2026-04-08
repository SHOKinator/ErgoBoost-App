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


def _hash_password(password: str, salt: str) -> str:
    """Hash password with salt using SHA-256"""
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()


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

        password_hash = _hash_password(password, user['salt'])
        if password_hash != user['password_hash']:
            raise ValueError("Invalid username or password")

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
