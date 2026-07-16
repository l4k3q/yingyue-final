import hashlib
import secrets
import sqlite3

from app.models.db import get_connection


def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex()


class UserRepository:
    @staticmethod
    def get_users(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) FROM users u LEFT JOIN roles r ON u.role_id = r.id 
                    WHERE u.username LIKE ? OR r.name LIKE ?
                    """,
                    (f"%{keyword}%", f"%{keyword}%")
                )
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    """
                    SELECT u.id, u.username, u.role_id, r.name as role_name, u.status, u.created_at 
                    FROM users u LEFT JOIN roles r ON u.role_id = r.id 
                    WHERE u.username LIKE ? OR r.name LIKE ?
                    ORDER BY CASE WHEN u.username='admin' THEN 0 ELSE 1 END, u.created_at DESC LIMIT ? OFFSET ?
                    """,
                    (f"%{keyword}%", f"%{keyword}%", page_size, offset)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM users")
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    """
                    SELECT u.id, u.username, u.role_id, r.name as role_name, u.status, u.created_at 
                    FROM users u LEFT JOIN roles r ON u.role_id = r.id 
                    ORDER BY CASE WHEN u.username='admin' THEN 0 ELSE 1 END, u.created_at DESC LIMIT ? OFFSET ?
                    """,
                    (page_size, offset)
                )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_user_by_id(user_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, role_id, status FROM users WHERE id=?",
                (user_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_user_by_username(username: str):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, salt, role_id, status FROM users WHERE username=?",
                (username,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create_user(username: str, password: str, role_id: int = 1) -> bool:
        salt = secrets.token_bytes(16)
        password_hash = _hash_password(password, salt)
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash, salt, role_id) VALUES (?,?,?,?)",
                    (username, password_hash, salt.hex(), role_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_user(user_id: int, username: str, role_id: int = 1) -> bool:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
                if row and row["username"] == "admin":
                    return False
                conn.execute(
                    "UPDATE users SET username=?, role_id=? WHERE id=?",
                    (username, role_id, user_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_user(user_id: int) -> bool:
        with get_connection() as conn:
            row = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
            if row and row["username"] == "admin":
                return False
            conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        return True

    @staticmethod
    def toggle_user_status(user_id: int, status: int) -> bool:
        with get_connection() as conn:
            row = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
            if row and row["username"] == "admin":
                return False
            conn.execute("UPDATE users SET status=? WHERE id=?", (status, user_id))
        return True

    @staticmethod
    def update_password(user_id: int, password: str) -> bool:
        salt = secrets.token_bytes(16)
        password_hash = _hash_password(password, salt)
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET password_hash=?, salt=? WHERE id=?",
                (password_hash, salt.hex(), user_id)
            )
        return True

    @staticmethod
    def verify_user(username: str, password: str) -> bool:
        row = UserRepository.get_user_by_username(username)
        if not row:
            return False
        if row["status"] != 1:
            return False
        salt = bytes.fromhex(row["salt"])
        return _hash_password(password, salt) == row["password_hash"]

    @staticmethod
    def update_face_embedding(username: str, face_embedding: str) -> bool:
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET face_embedding=? WHERE username=?",
                (face_embedding, username)
            )
        return True
    
    @staticmethod
    def get_users_with_face_embedding():
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, username, face_embedding FROM users WHERE face_embedding IS NOT NULL AND face_embedding != '' AND status=1"
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
