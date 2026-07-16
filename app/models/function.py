import sqlite3

from app.models.db import get_connection


class FunctionRepository:
    @staticmethod
    def get_functions(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM functions WHERE name LIKE ?",
                    (f"%{keyword}%",)
                )
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    "SELECT id, name, icon, url, parent_id, sort_order, status, created_at FROM functions WHERE name LIKE ? ORDER BY sort_order, id LIMIT ? OFFSET ?",
                    (f"%{keyword}%", page_size, offset)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM functions")
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    "SELECT id, name, icon, url, parent_id, sort_order, status, created_at FROM functions ORDER BY sort_order, id LIMIT ? OFFSET ?",
                    (page_size, offset)
                )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_function_by_id(func_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, icon, url, parent_id, sort_order, status FROM functions WHERE id=?",
                (func_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_function_by_url(url: str):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, icon, url, parent_id, sort_order, status FROM functions WHERE url=?",
                (url,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_all_functions():
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, icon, url, parent_id, sort_order, status FROM functions ORDER BY sort_order, id"
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_function_tree():
        functions = FunctionRepository.get_all_functions()
        function_map = {f["id"]: f for f in functions}
        tree = []
        for func in functions:
            if func["parent_id"] == 0:
                tree.append(func)
            else:
                parent = function_map.get(func["parent_id"])
                if parent:
                    if "children" not in parent:
                        parent["children"] = []
                    parent["children"].append(func)
        return tree

    @staticmethod
    def create_function(name: str, icon: str = "", url: str = "", parent_id: int = 0, sort_order: int = 0) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES (?,?,?,?,?)",
                    (name, icon, url, parent_id, sort_order)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_function(func_id: int, name: str, icon: str = "", url: str = "", parent_id: int = 0, sort_order: int = 0) -> bool:
        with get_connection() as conn:
            conn.execute(
                "UPDATE functions SET name=?, icon=?, url=?, parent_id=?, sort_order=? WHERE id=?",
                (name, icon, url, parent_id, sort_order, func_id)
            )
        return True

    @staticmethod
    def delete_function(func_id: int) -> bool:
        with get_connection() as conn:
            conn.execute("DELETE FROM role_functions WHERE function_id=?", (func_id,))
            conn.execute("DELETE FROM functions WHERE id=?", (func_id,))
        return True

    @staticmethod
    def toggle_function_status(func_id: int, status: int) -> bool:
        with get_connection() as conn:
            conn.execute("UPDATE functions SET status=? WHERE id=?", (status, func_id))
        return True