from app.models.db import get_connection


class SystemSettingRepository:
    @staticmethod
    def get_all_settings():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM system_settings ORDER BY group_name, sort_order"
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_settings_by_group(group_name: str):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM system_settings WHERE group_name=? ORDER BY sort_order",
                (group_name,)
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_setting(key: str):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM system_settings WHERE key=?",
                (key,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def update_setting(key: str, value: str) -> bool:
        with get_connection() as conn:
            conn.execute(
                "UPDATE system_settings SET value=?, updated_at=datetime('now','localtime') WHERE key=?",
                (value, key)
            )
        return True

    @staticmethod
    def get_grouped_settings():
        settings = SystemSettingRepository.get_all_settings()
        groups = {}
        for s in settings:
            group = s["group_name"]
            if group not in groups:
                groups[group] = []
            groups[group].append(s)
        return groups
