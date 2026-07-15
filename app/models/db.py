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

            music_card = """<div class="music-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; padding: 20px; color: #fff; min-width: 300px;">
                <div style="display: flex; gap: 16px; align-items: center;">
                    <div style="flex-shrink: 0; width: 100px; height: 100px; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.3);">
                        <img src="{artwork_url}" alt="专辑封面" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><rect fill=%22%23444%22 width=%22100%22 height=%22100%22/><text x=%2250%22 y=%2255%22 text-anchor=%22middle%22 fill=%22%23999%22 font-size=%2214%22>🎵</text></svg>';">
                    </div>
                    <div style="flex: 1; min-width: 0;">
                        <div style="font-size: 18px; font-weight: 700; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">🎵 {track_name}</div>
                        <div style="font-size: 14px; opacity: 0.9; margin-bottom: 4px;">👤 {artist_name}</div>
                        <div style="font-size: 13px; opacity: 0.75;">💿 {collection_name}</div>
                    </div>
                </div>
                <div style="margin-top: 14px; display: flex; justify-content: space-around; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 12px; font-size: 13px;">
                    <div style="text-align: center;">
                        <div style="font-size: 11px; opacity: 0.7;">风格</div>
                        <div style="font-weight: 500;">{genre}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 11px; opacity: 0.7;">时长</div>
                        <div style="font-weight: 500;">{duration}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 11px; opacity: 0.7;">价格</div>
                        <div style="font-weight: 500;">{price}</div>
                    </div>
                </div>
                <div style="margin-top: 10px; text-align: center;">
                    <a href="{track_url}" target="_blank" style="color: #fff; text-decoration: none; font-size: 12px; opacity: 0.8; border: 1px solid rgba(255,255,255,0.3); border-radius: 20px; padding: 4px 16px; display: inline-block;">🎧 在 iTunes 中打开</a>
                </div>
            </div>"""

            conn.execute(
                """INSERT INTO digital_employees (name, code_name, type, api_url, api_method, api_params, card_template, description)
                VALUES (?,?,?,?,?,?,?,?)""",
                ("随机音乐", "music", 2, "https://itunes.apple.com/search", "GET", '{"limit": "10", "entity": "song"}', music_card, "随机推荐一首歌曲，支持指定风格或关键词")
            )

            conn.execute(
                """INSERT INTO digital_employees (name, code_name, type, model_id, prompt, description)
                VALUES (?,?,?,?,?,?)""",
                ("文案写作助手", "copywriter", 1, 1, "你是一位资深的文案写作专家，擅长各类商业文案创作。你可以帮助用户撰写：\n- 广告文案（品牌slogan、产品描述、营销文案）\n- 社交媒体内容（微信公众号、微博、小红书文案）\n- 商业文档（商业计划书、融资BP、公司介绍）\n- 创意文案（品牌故事、软文、新闻稿）\n- 视频脚本（短视频、宣传片、口播文案）\n\n请根据用户需求，提供专业、高质量、可直接使用的文案内容。注意：\n1. 文案需符合目标平台的风格和规范\n2. 注意版权合规，避免抄袭\n3. 输出结构清晰，标题醒目\n4. 可使用emoji增强可读性（社交媒体文案）\n5. 字数根据用户要求灵活调整\n\n用户需求：{query}", "专业的商业文案写作助手")
            )