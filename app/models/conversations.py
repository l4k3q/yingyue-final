import json
import sqlite3

from app.models.db import get_connection


class ConversationRepository:
    @staticmethod
    def create_conversation(user_id: int, title: str = "", business_type: int = 0, employee_id: int = 0) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO conversations (user_id, title, business_type, employee_id) VALUES (?, ?, ?, ?)",
                (user_id, title, business_type, employee_id)
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
                "SELECT id, title, business_type, employee_id, archive_status, status, created_at, updated_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
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
            conn.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
        return True

    @staticmethod
    def add_message(conversation_id: int, role: str, content: str, msg_type: str = 'text'):
        conv = ConversationRepository.get_conversation_by_id(conversation_id)
        if not conv:
            return False
        
        user_id = conv.get("user_id", 0)
        
        # 获取当前消息序号
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT MAX(msg_index) FROM messages WHERE conversation_id=?",
                (conversation_id,)
            )
            max_idx = cursor.fetchone()[0] or 0
            new_idx = max_idx + 1
            
            # 插入到独立的 messages 表
            conn.execute(
                "INSERT INTO messages (conversation_id, user_id, role, content, msg_type, msg_index) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, user_id, role, content, msg_type, new_idx)
            )
            
            # 同时更新 conversations.messages 字段（兼容旧逻辑）
            messages = json.loads(conv.get("messages", "[]")) if conv.get("messages") else []
            messages.append({"role": role, "content": content, "type": msg_type, "index": new_idx})
            conn.execute(
                "UPDATE conversations SET messages=?, updated_at=(datetime('now','localtime')) WHERE id=?",
                (json.dumps(messages), conversation_id)
            )
        return True

    @staticmethod
    def get_messages(conversation_id: int) -> list:
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, role, content, msg_type, msg_index, created_at FROM messages WHERE conversation_id=? ORDER BY msg_index ASC",
                (conversation_id,)
            )
            rows = cursor.fetchall()
        if rows:
            return [dict(row) for row in rows]
        # 兼容旧数据：从 conversations.messages 字段读取
        conv = ConversationRepository.get_conversation_by_id(conversation_id)
        if not conv:
            return []
        return json.loads(conv.get("messages", "[]")) if conv.get("messages") else []

    # ========== 管理员专用方法 ==========
    
    @staticmethod
    def get_all_conversations_admin(page: int = 1, page_size: int = 20, 
                                     user_id: int = None, business_type: int = None,
                                     archive_status: int = None, status: int = None,
                                     start_date: str = None, end_date: str = None,
                                     keyword: str = None):
        """管理员获取所有会话列表，支持多条件筛选"""
        conditions = []
        params = []
        
        if user_id:
            conditions.append("c.user_id=?")
            params.append(user_id)
        if business_type is not None:
            conditions.append("c.business_type=?")
            params.append(business_type)
        if archive_status is not None:
            conditions.append("c.archive_status=?")
            params.append(archive_status)
        if status is not None:
            conditions.append("c.status=?")
            params.append(status)
        if start_date:
            conditions.append("c.created_at>=?")
            params.append(start_date)
        if end_date:
            conditions.append("c.created_at<=?")
            params.append(end_date)
        if keyword:
            conditions.append("(c.title LIKE ? OR c.id=?)")
            params.extend([f"%{keyword}%", keyword])
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        offset = (page - 1) * page_size
        with get_connection() as conn:
            # 总数
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM conversations c WHERE {where_clause}",
                params
            )
            total = cursor.fetchone()[0]
            
            # 列表数据（关联用户名）
            cursor = conn.execute(
                f"""SELECT c.id, c.user_id, c.title, c.business_type, c.employee_id, 
                           c.archive_status, c.status, c.created_at, c.updated_at,
                           u.username,
                           (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) as msg_count
                    FROM conversations c
                    LEFT JOIN users u ON c.user_id=u.id
                    WHERE {where_clause}
                    ORDER BY c.updated_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset]
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_conversation_stats():
        """获取会话统计看板数据"""
        today = __import__('datetime').datetime.now().strftime("%Y-%m-%d")
        with get_connection() as conn:
            # 今日新增会话
            cursor = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE created_at LIKE ?",
                (f"{today}%",)
            )
            today_count = cursor.fetchone()[0]
            
            # 总会话量
            cursor = conn.execute("SELECT COUNT(*) FROM conversations")
            total_count = cursor.fetchone()[0]
            
            # 按业务类型统计
            cursor = conn.execute(
                "SELECT business_type, COUNT(*) as cnt FROM conversations GROUP BY business_type"
            )
            business_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 按状态统计
            cursor = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM conversations GROUP BY status"
            )
            status_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 总消息数
            cursor = conn.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
        
        return {
            "today_count": today_count,
            "total_count": total_count,
            "total_messages": total_messages,
            "business_stats": business_stats,
            "status_stats": status_stats
        }

    @staticmethod
    def batch_archive_conversations(conversation_ids: list) -> bool:
        """批量归档会话"""
        if not conversation_ids:
            return False
        placeholders = ",".join(["?"] * len(conversation_ids))
        with get_connection() as conn:
            conn.execute(
                f"UPDATE conversations SET archive_status=1, updated_at=(datetime('now','localtime')) WHERE id IN ({placeholders})",
                conversation_ids
            )
        return True

    @staticmethod
    def batch_delete_conversations(conversation_ids: list) -> bool:
        """批量删除会话及其消息"""
        if not conversation_ids:
            return False
        placeholders = ",".join(["?"] * len(conversation_ids))
        with get_connection() as conn:
            conn.execute(
                f"DELETE FROM messages WHERE conversation_id IN ({placeholders})",
                conversation_ids
            )
            conn.execute(
                f"DELETE FROM conversations WHERE id IN ({placeholders})",
                conversation_ids
            )
        return True

    @staticmethod
    def archive_conversation(conversation_id: int) -> bool:
        """归档单个会话"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET archive_status=1, updated_at=(datetime('now','localtime')) WHERE id=?",
                (conversation_id,)
            )
        return True

    @staticmethod
    def unarchive_conversation(conversation_id: int) -> bool:
        """取消归档会话"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET archive_status=0, updated_at=(datetime('now','localtime')) WHERE id=?",
                (conversation_id,)
            )
        return True


class MessageRepository:
    """独立的消息管理仓库"""
    
    @staticmethod
    def get_messages_by_conversation(conversation_id: int, page: int = 1, page_size: int = 50):
        """获取指定会话的消息列表"""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id=?",
                (conversation_id,)
            )
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                """SELECT m.id, m.conversation_id, m.user_id, m.role, m.content, 
                          m.msg_type, m.msg_index, m.created_at, u.username
                   FROM messages m
                   LEFT JOIN users u ON m.user_id=u.id
                   WHERE m.conversation_id=?
                   ORDER BY m.msg_index ASC
                   LIMIT ? OFFSET ?""",
                (conversation_id, page_size, offset)
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_all_messages_admin(page: int = 1, page_size: int = 50,
                                conversation_id: int = None, user_id: int = None,
                                start_date: str = None, end_date: str = None,
                                keyword: str = None):
        """管理员获取所有消息列表，支持筛选"""
        conditions = []
        params = []
        
        if conversation_id:
            conditions.append("m.conversation_id=?")
            params.append(conversation_id)
        if user_id:
            conditions.append("m.user_id=?")
            params.append(user_id)
        if start_date:
            conditions.append("m.created_at>=?")
            params.append(start_date)
        if end_date:
            conditions.append("m.created_at<=?")
            params.append(end_date)
        if keyword:
            conditions.append("m.content LIKE ?")
            params.append(f"%{keyword}%")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        offset = (page - 1) * page_size
        with get_connection() as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM messages m WHERE {where_clause}",
                params
            )
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                f"""SELECT m.id, m.conversation_id, m.user_id, m.role, m.content,
                           m.msg_type, m.msg_index, m.created_at, u.username, c.title as conversation_title
                    FROM messages m
                    LEFT JOIN users u ON m.user_id=u.id
                    LEFT JOIN conversations c ON m.conversation_id=c.id
                    WHERE {where_clause}
                    ORDER BY m.created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset]
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def delete_message(message_id: int) -> bool:
        """删除单条消息"""
        with get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE id=?", (message_id,))
        return True

    @staticmethod
    def batch_delete_messages(message_ids: list) -> bool:
        """批量删除消息"""
        if not message_ids:
            return False
        placeholders = ",".join(["?"] * len(message_ids))
        with get_connection() as conn:
            conn.execute(
                f"DELETE FROM messages WHERE id IN ({placeholders})",
                message_ids
            )
        return True

    @staticmethod
    def clear_conversation_messages(conversation_id: int) -> bool:
        """清空指定会话的所有消息"""
        with get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
            conn.execute("UPDATE conversations SET messages='[]', updated_at=(datetime('now','localtime')) WHERE id=?", (conversation_id,))
        return True

    @staticmethod
    def export_messages_to_excel(conversation_id: int = None, user_id: int = None,
                                  start_date: str = None, end_date: str = None) -> list:
        """导出消息数据为Excel格式（返回列表供后续处理）"""
        conditions = []
        params = []
        
        if conversation_id:
            conditions.append("m.conversation_id=?")
            params.append(conversation_id)
        if user_id:
            conditions.append("m.user_id=?")
            params.append(user_id)
        if start_date:
            conditions.append("m.created_at>=?")
            params.append(start_date)
        if end_date:
            conditions.append("m.created_at<=?")
            params.append(end_date)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        with get_connection() as conn:
            cursor = conn.execute(
                f"""SELECT m.id, m.conversation_id, m.user_id, m.role, m.content,
                           m.msg_type, m.msg_index, m.created_at, u.username, c.title as conversation_title
                    FROM messages m
                    LEFT JOIN users u ON m.user_id=u.id
                    LEFT JOIN conversations c ON m.conversation_id=c.id
                    WHERE {where_clause}
                    ORDER BY m.conversation_id, m.msg_index ASC""",
                params
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]