import hashlib
import secrets
import sqlite3

from app.models.db import get_connection

def _hash_password(password: str, salt: bytes) -> str:
    # 将明文相同+salt 计算为稳定的hash
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex()

class UserRepository:
    # 用户数据访问类（面向Controller提供方法）
    # @staticmethod 修饰可以保持方法的简洁，目的是不引入依赖注入，不维护链接池
    @staticmethod
    def create_user(username: str, password: str) -> bool:
        salt = secrets.token_bytes(16)
        password_hash = _hash_password(password, salt)
        try:
            with get_connection() as conn:
                conn.execute(
                    "insert into users (username, password_hash, salt) values (?,?,?)",
                    (username, password_hash, salt.hex())
                )
                # 问号的作用是参数占位符，用来代替语句中动态填入的值，避免出现注入问题
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def get_user_by_username(username: str):
        with get_connection() as conn:
            row = conn.execute(
                "select id, username, password_hash, salt from users where username=?",
                (username,)
            ).fetchone()
        return row

    @staticmethod
    def verify_user(username: str, password: str) -> bool:
        row = UserRepository.get_user_by_username(username)
        # 先看用户名是否存在，如果用户名不存在，则后面验证没有必要
        if not row:
            return False
        salt = bytes.fromhex(row["salt"])
        return _hash_password(password, salt) == row["password_hash"]
