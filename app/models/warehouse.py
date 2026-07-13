from app.models.db import get_connection


class DataWarehouseRepository:
    @staticmethod
    def add_record(title, summary="", content="", url="", source="", source_id=0, keyword="", image_url=""):
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO data_warehouse 
                (title, summary, content, url, source, source_id, keyword, image_url)
                VALUES (?,?,?,?,?,?,?,?)""",
                (title, summary, content, url, source, source_id, keyword, image_url)
            )

    @staticmethod
    def add_records(records):
        with get_connection() as conn:
            conn.executemany(
                """INSERT INTO data_warehouse 
                (title, summary, content, url, source, source_id, keyword, image_url)
                VALUES (?,?,?,?,?,?,?,?)""",
                records
            )

    @staticmethod
    def get_records(page=1, page_size=20, keyword="", source=""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            conditions = ["status=1"]
            params = []
            if keyword:
                conditions.append("(title LIKE ? OR summary LIKE ? OR keyword LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
            if source:
                conditions.append("source LIKE ?")
                params.append(f"%{source}%")
            where_clause = " AND ".join(conditions)
            
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM data_warehouse WHERE {where_clause}",
                params
            )
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                f"""SELECT * FROM data_warehouse WHERE {where_clause} 
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                params + [page_size, offset]
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_record_by_id(record_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM data_warehouse WHERE id=?",
                (record_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def update_record(record_id, **kwargs):
        fields = []
        params = []
        for key, value in kwargs.items():
            fields.append(f"{key}=?")
            params.append(value)
        params.append(record_id)
        with get_connection() as conn:
            conn.execute(
                f"UPDATE data_warehouse SET {', '.join(fields)} WHERE id=?",
                params
            )

    @staticmethod
    def delete_record(record_id):
        with get_connection() as conn:
            conn.execute("UPDATE data_warehouse SET status=0 WHERE id=?", (record_id,))

    @staticmethod
    def mark_deep_collected(record_id):
        with get_connection() as conn:
            conn.execute(
                "UPDATE data_warehouse SET is_deep_collected=1, deep_collect_time=datetime('now','localtime') WHERE id=?",
                (record_id,)
            )

    @staticmethod
    def get_stats():
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT COUNT(*) as total, 
                   SUM(CASE WHEN is_deep_collected=1 THEN 1 ELSE 0 END) as deep_collected
                   FROM data_warehouse WHERE status=1"""
            )
            row = cursor.fetchone()
        return dict(row) if row else {"total": 0, "deep_collected": 0}