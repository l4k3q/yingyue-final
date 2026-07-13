"""
db.py 属于SQLite数据库访问层（model的基础设施部分）
- 使用python3内置的sqlite3连接SQLite数据库（零依赖）
- 统一管理DB文件路径，连接创建，row_factory
- 支持初始化建立表及表结构，实现“开箱即用”
"""
import os
import sqlite3

def project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__),os.pardir,os.pardir))

DB_PATH = os.path.join(project_root(),"database","finderos.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH),exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role_id INTEGER DEFAULT 1,
                status INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                is_super BOOLEAN NOT NULL DEFAULT 1,
                status INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS roles(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_default BOOLEAN NOT NULL DEFAULT 0,
                status INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS functions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                icon TEXT,
                url TEXT,
                parent_id INTEGER DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                status INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS role_functions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                function_id INTEGER NOT NULL,
                UNIQUE(role_id, function_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_sources(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                request_headers TEXT,
                params TEXT,
                status INTEGER NOT NULL DEFAULT 1,
                description TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_records(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                page INTEGER NOT NULL DEFAULT 1,
                data TEXT,
                status INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_models(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                model_id TEXT NOT NULL,
                api_key TEXT NOT NULL,
                base_url TEXT NOT NULL,
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 4096,
                top_p REAL DEFAULT 0.9,
                frequency_penalty REAL DEFAULT 0.0,
                presence_penalty REAL DEFAULT 0.0,
                is_default INTEGER NOT NULL DEFAULT 0,
                status INTEGER NOT NULL DEFAULT 1,
                total_tokens INTEGER DEFAULT 0,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                description TEXT,
                provider TEXT DEFAULT 'openai',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS data_warehouse(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT,
                content TEXT,
                url TEXT,
                source TEXT,
                source_id INTEGER DEFAULT 0,
                keyword TEXT,
                image_url TEXT,
                is_deep_collected INTEGER NOT NULL DEFAULT 0,
                deep_collect_time TEXT,
                status INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        cursor = conn.execute("SELECT COUNT(*) FROM admins WHERE username='admin'")
        count = cursor.fetchone()[0]
        if count == 0:
            import hashlib
            import secrets
            salt = secrets.token_bytes(16)
            password_hash = hashlib.pbkdf2_hmac("sha256", "admin888".encode("utf-8"), salt, 100_000).hex()
            conn.execute(
                "INSERT INTO admins (username, password_hash, salt, is_super) VALUES (?,?,?,?)",
                ("admin", password_hash, salt.hex(), 1)
            )
        cursor = conn.execute("SELECT COUNT(*) FROM roles")
        count = cursor.fetchone()[0]
        if count == 0:
            conn.execute("INSERT INTO roles (name, description, is_default) VALUES ('普通用户', '只能登录前台-用户侧', 1)")
            conn.execute("INSERT INTO roles (name, description, is_default) VALUES ('系统管理员', '只能登录后台-后台管理系统', 1)")
        cursor = conn.execute("SELECT COUNT(*) FROM functions")
        count = cursor.fetchone()[0]
        if count == 0:
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('系统首页', 'icon-home', '/admin/index', 0, 1)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('用户管理', 'icon-user', '/admin/users', 0, 2)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('用户列表', 'icon-list', '/admin/users', 2, 1)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('添加用户', 'icon-add', '/admin/users/add', 2, 2)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('权限管理', 'icon-set', '/admin/functions', 0, 3)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('功能管理', 'icon-app', '/admin/functions', 5, 1)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('菜单管理', 'icon-menu', '/admin/menus', 5, 2)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('角色管理', 'icon-group', '/admin/roles', 5, 3)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('数据管理', 'icon-data', '/admin/data', 0, 4)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('瞭望管理', 'icon-eye', '/admin/watch', 9, 1)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('数据管理', 'icon-database', '/admin/data', 9, 2)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('采集管理', 'icon-collection', '/admin/collection', 9, 3)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('AI管理', 'icon-robot', '/admin/model', 0, 5)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('数字员工', 'icon-face', '/admin/digital_employee', 13, 1)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('模型引擎', 'icon-cpu', '/admin/model', 13, 2)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('数智大屏', 'icon-screen', '/admin/dashboard', 0, 6)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('舆情大屏', 'icon-cloud', '/admin/sentiment', 0, 7)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 1)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 2)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 3)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 4)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 5)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 6)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 7)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 8)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 9)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 10)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 11)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 12)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 13)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 14)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 15)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 16)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 17)")
        cursor = conn.execute("SELECT COUNT(*) FROM watch_sources")
        count = cursor.fetchone()[0]
        if count == 0:
            import json
            baidu_headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Host": "www.baidu.com",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 QQBrowser/21.4.9121.400",
                "sec-ch-ua": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\""
            }
            baidu_params = {
                "rtt": "1",
                "bsst": "1",
                "cl": "2",
                "tn": "news",
                "rsv_dl": "ns_pc"
            }
            conn.execute(
                "INSERT INTO watch_sources (name, url, request_headers, params, status, description) VALUES (?,?,?,?,?,?)",
                ("百度新闻", "https://www.baidu.com/s", json.dumps(baidu_headers), json.dumps(baidu_params), 1, "百度新闻搜索接口，支持关键词搜索和分页")
            )