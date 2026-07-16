import sqlite3

from app.models.db import get_connection


class FunctionRepository:
    ICON_MAP = {
        "icon-home": "layui-icon-home",
        "icon-user": "layui-icon-user",
        "icon-list": "layui-icon-list",
        "icon-add": "layui-icon-add-circle",
        "icon-set": "layui-icon-set",
        "icon-app": "layui-icon-app",
        "icon-menu": "layui-icon-tabs",
        "icon-group": "layui-icon-group",
        "icon-data": "layui-icon-chart",
        "icon-eye": "layui-icon-search",
        "icon-database": "layui-icon-table",
        "icon-collection": "layui-icon-template",
        "icon-robot": "layui-icon-service",
        "icon-face": "layui-icon-username",
        "icon-cpu": "layui-icon-engine",
        "icon-screen": "layui-icon-chart-screen",
        "icon-cloud": "layui-icon-dialogue",
    }

    @staticmethod
    def _normalize_function(row):
        func = dict(row)
        icon = func.get("icon") or ""
        func["icon_class"] = FunctionRepository.ICON_MAP.get(icon, icon)
        if func["icon_class"] and not func["icon_class"].startswith("layui-icon-"):
            func["icon_class"] = FunctionRepository.ICON_MAP.get(func["icon_class"], "layui-icon-app")
        if not func["icon_class"]:
            func["icon_class"] = "layui-icon-app"
        func["title"] = func.get("name", "")
        func["field"] = str(func.get("id", ""))
        return func

    @staticmethod
    def _build_tree(functions):
        function_map = {f["id"]: f for f in functions}
        tree = []
        for func in functions:
            func.setdefault("children", [])
        for func in functions:
            parent_id = func.get("parent_id", 0)
            if parent_id == 0:
                tree.append(func)
            else:
                parent = function_map.get(parent_id)
                if parent:
                    parent.setdefault("children", []).append(func)
                else:
                    tree.append(func)
        return tree

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
        return [FunctionRepository._normalize_function(row) for row in rows], total

    @staticmethod
    def get_function_by_id(func_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, icon, url, parent_id, sort_order, status FROM functions WHERE id=?",
                (func_id,)
            ).fetchone()
        return FunctionRepository._normalize_function(row) if row else None

    @staticmethod
    def get_all_functions():
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, icon, url, parent_id, sort_order, status FROM functions ORDER BY sort_order, id"
            )
            rows = cursor.fetchall()
        return [FunctionRepository._normalize_function(row) for row in rows]

    @staticmethod
    def get_function_tree(only_enabled: bool = False):
        functions = FunctionRepository.get_all_functions()
        if only_enabled:
            functions = [f for f in functions if f.get("status") == 1]
        return FunctionRepository._build_tree(functions)

    @staticmethod
    def get_functions_for_role(role_id: int, include_parents: bool = True):
        with get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT f.id, f.name, f.icon, f.url, f.parent_id, f.sort_order, f.status
                FROM functions f
                INNER JOIN role_functions rf ON rf.function_id = f.id
                WHERE rf.role_id=? AND f.status=1
                ORDER BY f.sort_order, f.id
                """,
                (role_id,)
            )
            rows = [FunctionRepository._normalize_function(row) for row in cursor.fetchall()]

            if include_parents and rows:
                ids = {row["id"] for row in rows}
                parent_ids = {row["parent_id"] for row in rows if row.get("parent_id", 0) and row["parent_id"] not in ids}
                while parent_ids:
                    placeholders = ",".join(["?"] * len(parent_ids))
                    parent_rows = conn.execute(
                        f"""
                        SELECT id, name, icon, url, parent_id, sort_order, status
                        FROM functions
                        WHERE id IN ({placeholders}) AND status=1
                        """,
                        tuple(parent_ids)
                    ).fetchall()
                    new_parents = []
                    for row in parent_rows:
                        func = FunctionRepository._normalize_function(row)
                        if func["id"] not in ids:
                            rows.append(func)
                            ids.add(func["id"])
                            if func.get("parent_id", 0) and func["parent_id"] not in ids:
                                new_parents.append(func["parent_id"])
                    parent_ids = set(new_parents)

        return sorted(rows, key=lambda item: (item.get("sort_order", 0), item.get("id", 0)))

    @staticmethod
    def get_menu_tree_for_user(username: str, role_id: int = 0):
        if username == "admin":
            functions = [f for f in FunctionRepository.get_all_functions() if f.get("status") == 1]
        else:
            functions = FunctionRepository.get_functions_for_role(role_id, include_parents=True)
        return FunctionRepository._build_tree(functions)

    @staticmethod
    def role_has_admin_access(role_id: int) -> bool:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM role_functions rf
                INNER JOIN functions f ON f.id = rf.function_id
                INNER JOIN roles r ON r.id = rf.role_id
                WHERE rf.role_id=? AND r.status=1 AND f.status=1 AND f.url LIKE '/admin/%'
                LIMIT 1
                """,
                (role_id,)
            ).fetchone()
        return row is not None

    @staticmethod
    def role_can_access_path(role_id: int, path: str) -> bool:
        if path in ("/admin/index", "/admin/logout"):
            return FunctionRepository.role_has_admin_access(role_id)

        functions = FunctionRepository.get_functions_for_role(role_id, include_parents=False)
        for func in functions:
            url = (func.get("url") or "").rstrip("/")
            if not url or not url.startswith("/admin"):
                continue
            if path == url or path.startswith(url + "/"):
                return True
        return False

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
