import json
import sqlite3

from app.models.db import get_connection


class ConversationRepository:
    @staticmethod
    def create_conversation(user_id: int, title: str = "") -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
                (user_id, title)
            )
        return cursor.lastrowid

    @staticmethod
    def get_conversation_by_id(conversation_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id=?",
                (conversation_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_conversations(user_id: int, page: int = 1, page_size: int = 20):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE user_id=?",
                (user_id,)
            )
            total = cursor.fetchone()[0]
            cursor = conn.execute(
                "SELECT id, title, created_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset)
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def update_conversation(conversation_id: int, title: str = None, messages: list = None):
        updates = []
        params = []
        if title is not None:
            updates.append("title=?")
            params.append(title)
        if messages is not None:
            updates.append("messages=?")
            params.append(json.dumps(messages))
        updates.append("updated_at=(datetime('now','localtime'))")
        params.append(conversation_id)
        
        with get_connection() as conn:
            conn.execute(
                f"UPDATE conversations SET {', '.join(updates)} WHERE id=?",
                params
            )
        return True

    @staticmethod
    def delete_conversation(conversation_id: int) -> bool:
        with get_connection() as conn:
            conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
        return True

    @staticmethod
    def add_message(conversation_id: int, role: str, content: str):
        conv = ConversationRepository.get_conversation_by_id(conversation_id)
        if not conv:
            return False
        
        messages = json.loads(conv.get("messages", "[]")) if conv.get("messages") else []
        messages.append({"role": role, "content": content})
        
        with get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET messages=?, updated_at=(datetime('now','localtime')) WHERE id=?",
                (json.dumps(messages), conversation_id)
            )
        return True

    @staticmethod
    def get_messages(conversation_id: int) -> list:
        conv = ConversationRepository.get_conversation_by_id(conversation_id)
        if not conv:
            return []
        return json.loads(conv.get("messages", "[]")) if conv.get("messages") else []