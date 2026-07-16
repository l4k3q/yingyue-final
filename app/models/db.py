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
                model_type TEXT NOT NULL DEFAULT 'text',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        try:
            conn.execute("ALTER TABLE ai_models ADD COLUMN model_type TEXT NOT NULL DEFAULT 'text'")
        except sqlite3.OperationalError:
            pass
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS digital_employees(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code_name TEXT NOT NULL UNIQUE,
                type INTEGER NOT NULL DEFAULT 1,
                model_id INTEGER DEFAULT 0,
                prompt TEXT,
                skills TEXT,
                use_crawl4ai INTEGER NOT NULL DEFAULT 0,
                api_url TEXT,
                api_method TEXT DEFAULT 'GET',
                api_headers TEXT,
                api_params TEXT,
                api_body TEXT,
                card_template TEXT,
                description TEXT,
                status INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        try:
            conn.execute("ALTER TABLE digital_employees ADD COLUMN card_template TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE digital_employees ADD COLUMN md_files_path TEXT")
        except sqlite3.OperationalError:
            pass
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deep_collect_tasks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                employee_id INTEGER DEFAULT 0,
                employee_name TEXT,
                status INTEGER NOT NULL DEFAULT 0,
                progress INTEGER NOT NULL DEFAULT 0,
                step TEXT DEFAULT '',
                log TEXT DEFAULT '',
                result TEXT DEFAULT '',
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (record_id) REFERENCES data_warehouse(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT DEFAULT '',
                messages TEXT DEFAULT '',
                status INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        def ensure_role(name, description, is_default=0):
            row = conn.execute("SELECT id FROM roles WHERE name=?", (name,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE roles SET description=?, is_default=?, status=1 WHERE id=?",
                    (description, is_default, row["id"])
                )
                return row["id"]
            cursor = conn.execute(
                "INSERT INTO roles (name, description, is_default, status) VALUES (?,?,?,1)",
                (name, description, is_default)
            )
            return cursor.lastrowid

        def ensure_function(name, icon, url, parent_id=0, sort_order=0):
            row = conn.execute(
                "SELECT id FROM functions WHERE name=? AND parent_id=?",
                (name, parent_id)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE functions SET icon=?, url=?, sort_order=?, status=1 WHERE id=?",
                    (icon, url, sort_order, row["id"])
                )
                return row["id"]
            cursor = conn.execute(
                "INSERT INTO functions (name, icon, url, parent_id, sort_order, status) VALUES (?,?,?,?,?,1)",
                (name, icon, url, parent_id, sort_order)
            )
            return cursor.lastrowid

        def ensure_role_function(role_id, function_id):
            conn.execute(
                "INSERT OR IGNORE INTO role_functions (role_id, function_id) VALUES (?,?)",
                (role_id, function_id)
            )

        user_role_id = ensure_role("普通用户", "只能登录前台-用户侧", 1)
        admin_role_id = ensure_role("系统管理员", "只能登录后台-后台管理系统", 1)
        user_admin_role_id = ensure_role("用户管理员", "负责后台用户列表、用户状态和普通用户资料维护", 0)

        dashboard_id = ensure_function("控制台", "layui-icon-home", "/admin/index", 0, 1)
        user_root_id = ensure_function("用户管理", "layui-icon-user", "/admin/users", 0, 2)
        user_list_id = ensure_function("用户列表", "layui-icon-list", "/admin/users", user_root_id, 1)
        permission_root_id = ensure_function("权限管理", "layui-icon-set", "/admin/functions", 0, 3)
        function_id = ensure_function("功能管理", "layui-icon-app", "/admin/functions", permission_root_id, 1)
        menu_id = ensure_function("菜单管理", "layui-icon-tabs", "/admin/menus", permission_root_id, 2)
        role_id = ensure_function("角色管理", "layui-icon-group", "/admin/roles", permission_root_id, 3)
        data_root_id = ensure_function("数据管理", "layui-icon-chart", "/admin/data", 0, 4)
        watch_id = ensure_function("瞭望采集", "layui-icon-search", "/admin/watch", data_root_id, 1)
        data_id = ensure_function("数据仓库", "layui-icon-table", "/admin/data", data_root_id, 2)
        collection_id = ensure_function("采集管理", "layui-icon-template", "/admin/collection", data_root_id, 3)
        ai_root_id = ensure_function("AI管理", "layui-icon-service", "/admin/model", 0, 5)
        employee_id = ensure_function("数字员工", "layui-icon-username", "/admin/digital_employee", ai_root_id, 1)
        model_id = ensure_function("模型引擎", "layui-icon-engine", "/admin/model", ai_root_id, 2)
        big_screen_id = ensure_function("数智大屏", "layui-icon-chart-screen", "/admin/dashboard", 0, 6)
        sentiment_id = ensure_function("舆情大屏", "layui-icon-dialogue", "/admin/sentiment", 0, 7)

        all_admin_functions = [
            dashboard_id, user_root_id, user_list_id, permission_root_id, function_id, menu_id, role_id,
            data_root_id, watch_id, data_id, collection_id, ai_root_id, employee_id, model_id,
            big_screen_id, sentiment_id
        ]
        for function_id_value in all_admin_functions:
            ensure_role_function(admin_role_id, function_id_value)

        for function_id_value in [dashboard_id, user_root_id, user_list_id]:
            ensure_role_function(user_admin_role_id, function_id_value)

        cursor = conn.execute("SELECT COUNT(*) FROM admins WHERE username='admin'")
        count = cursor.fetchone()[0]
        import hashlib
        import secrets
        salt = secrets.token_bytes(16)
        password_hash = hashlib.pbkdf2_hmac("sha256", "admin888".encode("utf-8"), salt, 100_000).hex()
        if count == 0:
            conn.execute(
                "INSERT INTO admins (username, password_hash, salt, is_super, status) VALUES (?,?,?,?,1)",
                ("admin", password_hash, salt.hex(), 1)
            )

        admin_user = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        if admin_user:
            conn.execute(
                "UPDATE users SET role_id=?, status=1 WHERE username='admin'",
                (admin_role_id,)
            )
        else:
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, role_id, status) VALUES (?,?,?,?,1)",
                ("admin", password_hash, salt.hex(), admin_role_id)
            )
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
        
        cursor = conn.execute("SELECT COUNT(*) FROM ai_models")
        count = cursor.fetchone()[0]
        if count == 0:
            conn.execute(
                """INSERT INTO ai_models (name, model_id, api_key, base_url, temperature, max_tokens, is_default, status, description, provider) 
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                ("DeepSeek Free", "deepseek-chat", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "https://api.deepseek.com/v1", 0.7, 4096, 1, 1, "DeepSeek免费大模型服务", "openai")
            )
        
        cursor = conn.execute("SELECT COUNT(*) FROM digital_employees")
        count = cursor.fetchone()[0]
        if count == 0:
            weather_card = """<div class="weather-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border-radius: 16px; padding: 20px; color: #fff; min-width: 280px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <div style="font-size: 24px; font-weight: 600;">{location}</div>
                        <div style="font-size: 14px; opacity: 0.8; margin-top: 4px;">{date}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 48px; font-weight: 700;">{temp}</div>
                        <div style="font-size: 14px;">{condition}</div>
                    </div>
                </div>
                <div style="margin-top: 16px; display: flex; justify-content: space-around; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 12px;">
                    <div style="text-align: center;">
                        <div style="font-size: 12px; opacity: 0.8;">湿度</div>
                        <div style="font-size: 16px; font-weight: 500;">{humidity}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 12px; opacity: 0.8;">风力</div>
                        <div style="font-size: 16px; font-weight: 500;">{wind}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 12px; opacity: 0.8;">能见度</div>
                        <div style="font-size: 16px; font-weight: 500;">{visibility}</div>
                    </div>
                </div>
            </div>"""
            
            news_card = """<div class="news-card" style="border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; background: #fff;">
                <h4 style="font-size: 16px; font-weight: 600; color: #1f2937; margin-bottom: 12px;">📰 最新新闻</h4>
                <div>{news_list}</div>
            </div>"""
            
            conn.execute(
                """INSERT INTO digital_employees (name, code_name, type, api_url, api_method, api_params, card_template, description) 
                VALUES (?,?,?,?,?,?,?,?)""",
                ("天气", "weather", 2, "https://wttr.in/{city}?format=j1", "GET", '{"city": "Beijing"}', weather_card, "查询指定城市天气信息")
            )
            
            conn.execute(
                """INSERT INTO digital_employees (name, code_name, type, model_id, prompt, description) 
                VALUES (?,?,?,?,?,?)""",
                ("新闻", "news", 1, 1, "你是一个新闻助手，请为用户提供最新的新闻资讯。用户查询: {query}", "获取最新新闻资讯")
            )
            
            conn.execute(
                """INSERT INTO digital_employees (name, code_name, type, model_id, prompt, description) 
                VALUES (?,?,?,?,?,?)""",
                ("川哥", "chuange", 1, 1, "你是川哥，一位幽默风趣的AI助手，擅长聊天和解答各种问题。用户输入: {query}", "与川哥聊天互动")
            )
            
            conn.execute(
                """INSERT INTO digital_employees (name, code_name, type, model_id, prompt, description) 
                VALUES (?,?,?,?,?,?)""",
                ("电影", "movie", 1, 1, "你是一个电影推荐助手，请为用户推荐电影。用户查询: {query}", "电影推荐和查询")
            )
            
            conn.execute(
                """INSERT INTO digital_employees (name, code_name, type, model_id, prompt, description) 
                VALUES (?,?,?,?,?,?)""",
                ("采集专员", "collector", 1, 1, "你是采集专员，负责网页内容深度采集。URL: {url}", "网页内容深度采集")
            )
