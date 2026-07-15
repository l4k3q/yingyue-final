import json
import sqlite3
import urllib.parse
import requests

from app.models.db import get_connection


class WatchSourceRepository:
    @staticmethod
    def get_sources(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM watch_sources WHERE name LIKE ? OR description LIKE ?",
                    (f"%{keyword}%", f"%{keyword}%")
                )
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    "SELECT id, name, url, status, description, created_at FROM watch_sources WHERE name LIKE ? OR description LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (f"%{keyword}%", f"%{keyword}%", page_size, offset)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM watch_sources")
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    "SELECT id, name, url, status, description, created_at FROM watch_sources ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_source_by_id(source_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, url, request_headers, params, status, description FROM watch_sources WHERE id=?",
                (source_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_enabled_sources():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, name, url, request_headers, params FROM watch_sources WHERE status=1"
            ).fetchall()
        sources = []
        for row in rows:
            source = dict(row)
            if source["request_headers"]:
                source["request_headers"] = json.loads(source["request_headers"])
            if source["params"]:
                source["params"] = json.loads(source["params"])
            sources.append(source)
        return sources

    @staticmethod
    def create_source(name: str, url: str, request_headers: str, params: str, description: str = "") -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO watch_sources (name, url, request_headers, params, description, updated_at) VALUES (?,?,?,?,?,datetime('now','localtime'))",
                    (name, url, request_headers, params, description)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_source(source_id: int, name: str, url: str, request_headers: str, params: str, description: str = "") -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE watch_sources SET name=?, url=?, request_headers=?, params=?, description=?, updated_at=datetime('now','localtime') WHERE id=?",
                    (name, url, request_headers, params, description, source_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_source(source_id: int) -> bool:
        with get_connection() as conn:
            conn.execute("DELETE FROM watch_sources WHERE id=?", (source_id,))
        return True

    @staticmethod
    def toggle_source_status(source_id: int, status: int) -> bool:
        with get_connection() as conn:
            conn.execute("UPDATE watch_sources SET status=? WHERE id=?", (status, source_id))
        return True


class WatchRecordRepository:
    @staticmethod
    def get_records(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM watch_records r LEFT JOIN watch_sources s ON r.source_id = s.id WHERE r.keyword LIKE ? OR s.name LIKE ?",
                    (f"%{keyword}%", f"%{keyword}%")
                )
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    """
                    SELECT r.id, r.source_id, s.name as source_name, r.keyword, r.page, r.data, r.status, r.created_at 
                    FROM watch_records r LEFT JOIN watch_sources s ON r.source_id = s.id 
                    WHERE r.keyword LIKE ? OR s.name LIKE ?
                    ORDER BY r.created_at DESC LIMIT ? OFFSET ?
                    """,
                    (f"%{keyword}%", f"%{keyword}%", page_size, offset)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM watch_records")
                total = cursor.fetchone()[0]
                cursor = conn.execute(
                    """
                    SELECT r.id, r.source_id, s.name as source_name, r.keyword, r.page, r.data, r.status, r.created_at 
                    FROM watch_records r LEFT JOIN watch_sources s ON r.source_id = s.id 
                    ORDER BY r.created_at DESC LIMIT ? OFFSET ?
                    """,
                    (page_size, offset)
                )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_record_by_id(record_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, source_id, keyword, page, data, status FROM watch_records WHERE id=?",
                (record_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create_record(source_id: int, keyword: str, page: int = 1, data: str = "", status: int = 0):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO watch_records (source_id, keyword, page, data, status) VALUES (?,?,?,?,?)",
                (source_id, keyword, page, data, status)
            )

    @staticmethod
    def update_record(record_id: int, data: str = "", status: int = 0):
        with get_connection() as conn:
            conn.execute(
                "UPDATE watch_records SET data=?, status=? WHERE id=?",
                (data, status, record_id)
            )

    @staticmethod
    def get_stats():
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT COUNT(*) as total,
                   SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as success,
                   SUM(CASE WHEN status=0 THEN 1 ELSE 0 END) as failed
                   FROM watch_records"""
            )
            row = cursor.fetchone()
        return dict(row) if row else {"total": 0, "success": 0, "failed": 0}

    @staticmethod
    def delete_record(record_id: int):
        with get_connection() as conn:
            conn.execute("DELETE FROM watch_records WHERE id=?", (record_id,))


class WatchCollector:
    @staticmethod
    def collect(source_id: int, keyword: str, page: int = 1):
        source = WatchSourceRepository.get_source_by_id(source_id)
        if not source or source["status"] != 1:
            return None

        try:
            headers = json.loads(source["request_headers"]) if source["request_headers"] else {}
            params = json.loads(source["params"]) if source["params"] else {}
            params["word"] = keyword
            params["pn"] = (page - 1) * 10

            url = source["url"] + "?" + urllib.parse.urlencode(params)
            
            headers.pop('Accept-Encoding', None)
            
            response = requests.get(url, headers=headers, timeout=30)
            response.encoding = response.apparent_encoding
            
            return response.text
        except Exception as e:
            return f"采集失败: {str(e)}"

    @staticmethod
    def parse_baidu_news(html_content: str):
        import re
        articles = []
        try:
            title_pattern = re.compile(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>', re.DOTALL)
            link_pattern = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
            
            titles = title_pattern.findall(html_content)
            for title in titles:
                links = link_pattern.findall(title)
                if links:
                    href = links[0][0]
                    text = re.sub(r'<[^>]+>', '', links[0][1]).strip()
                    articles.append({"title": text, "url": href})
                    
            return articles[:12]
        except Exception as e:
            return [{"title": f"解析失败: {str(e)}", "url": ""}]