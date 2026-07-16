import hashlib
import secrets
import sqlite3

from app.models.db import get_connection


def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex()


class AdminRepository:
    @staticmethod
    def get_admins(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM admins WHERE username LIKE ?",
                    (f"%{keyword}%",)
                )
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    "SELECT id, username, is_super, status, created_at FROM admins WHERE username LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (f"%{keyword}%", page_size, offset)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM admins")
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    "SELECT id, username, is_super, status, created_at FROM admins ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_admin_by_id(admin_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, is_super, status FROM admins WHERE id=?",
                (admin_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_admin_by_username(username: str):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, salt, is_super, status FROM admins WHERE username=?",
                (username,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create_admin(username: str, password: str, is_super: int = 0) -> bool:
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
    def update_admin(admin_id: int, username: str, is_super: int = 0) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE admins SET username=?, is_super=? WHERE id=?",
                    (username, is_super, admin_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_admin(admin_id: int) -> bool:
        with get_connection() as conn:
            conn.execute("DELETE FROM admins WHERE id=?", (admin_id,))
        return True

    @staticmethod
    def toggle_admin_status(admin_id: int, status: int) -> bool:
        with get_connection() as conn:
            conn.execute("UPDATE admins SET status=? WHERE id=?", (status, admin_id))
        return True

    @staticmethod
    def verify_admin(username: str, password: str) -> bool:
        from app.models.user import UserRepository
        from app.models.role import RoleRepository
        from app.models.function import FunctionRepository
        
        user = UserRepository.get_user_by_username(username)
        if not user:
            row = AdminRepository.get_admin_by_username(username)
            if not row:
                return False
            if row["status"] != 1:
                return False
            salt = bytes.fromhex(row["salt"])
            return _hash_password(password, salt) == row["password_hash"]
        
        if user["status"] != 1:
            return False
        
        salt = bytes.fromhex(user["salt"])
        if _hash_password(password, salt) != user["password_hash"]:
            return False

        if user["username"] == "admin":
            return True
        
        role = RoleRepository.get_role_by_id(user["role_id"])
        if not role or role["status"] != 1:
            return False
        return FunctionRepository.role_has_admin_access(user["role_id"])
