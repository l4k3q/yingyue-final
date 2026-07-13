import sqlite3

from app.models.db import get_connection


class RoleRepository:
    @staticmethod
    def get_roles(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM roles WHERE name LIKE ?",
                    (f"%{keyword}%",)
                )
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    "SELECT id, name, description, is_default, status, created_at FROM roles WHERE name LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (f"%{keyword}%", page_size, offset)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM roles")
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    "SELECT id, name, description, is_default, status, created_at FROM roles ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_role_by_id(role_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, description, is_default, status FROM roles WHERE id=?",
                (role_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_role_by_name(name: str):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, description, is_default, status FROM roles WHERE name=?",
                (name,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create_role(name: str, description: str = "") -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO roles (name, description) VALUES (?,?)",
                    (name, description)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_role(role_id: int, name: str, description: str = "") -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE roles SET name=?, description=? WHERE id=?",
                    (name, description, role_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_role(role_id: int) -> bool:
        with get_connection() as conn:
            conn.execute("DELETE FROM role_functions WHERE role_id=?", (role_id,))
            conn.execute("DELETE FROM roles WHERE id=?", (role_id,))
        return True

    @staticmethod
    def get_role_functions(role_id: int):
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT function_id FROM role_functions WHERE role_id=?",
                (role_id,)
            )
            rows = cursor.fetchall()
        return [row["function_id"] for row in rows]

    @staticmethod
    def update_role_functions(role_id: int, function_ids: list):
        with get_connection() as conn:
            conn.execute("DELETE FROM role_functions WHERE role_id=?", (role_id,))
            for func_id in function_ids:
                conn.execute(
                    "INSERT INTO role_functions (role_id, function_id) VALUES (?,?)",
                    (role_id, func_id)
                )
        return True