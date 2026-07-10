import hashlib
import secrets
import sqlite3

from app.models.db import get_connection


def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex()


class AdminRepository:
    @staticmethod
    def create_admin(username: str, password: str, is_super: int = 1) -> bool:
        salt = secrets.token_bytes(16)
        password_hash = _hash_password(password, salt)
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO admins (username, password_hash, salt, is_super) VALUES (?,?,?,?)",
                    (username, password_hash, salt.hex(), is_super)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def get_admin_by_username(username: str):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, salt, is_super FROM admins WHERE username=?",
                (username,)
            ).fetchone()
        return row

    @staticmethod
    def verify_admin(username: str, password: str) -> bool:
        row = AdminRepository.get_admin_by_username(username)
        if not row:
            return False
        salt = bytes.fromhex(row["salt"])
        return _hash_password(password, salt) == row["password_hash"]