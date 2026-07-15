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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sensitive_words(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT '通用',
                severity INTEGER DEFAULT 1,
                status INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS security_alerts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_id INTEGER DEFAULT 0,
                user_id INTEGER DEFAULT 0,
                username TEXT DEFAULT '',
                matched_words TEXT DEFAULT '',
                content_snippet TEXT DEFAULT '',
                risk_level INTEGER DEFAULT 1,
                ai_analysis TEXT DEFAULT '',
                status INTEGER NOT NULL DEFAULT 0,
                handler_id INTEGER DEFAULT 0,
                handled_at TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS content_scan_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,
                target_id INTEGER DEFAULT 0,
                content_hash TEXT DEFAULT '',
                is_safe INTEGER NOT NULL DEFAULT 1,
                matched_count INTEGER DEFAULT 0,
                scan_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        try:
            conn.execute("ALTER TABLE sensitive_words ADD COLUMN patterns TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
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
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('敏感词管理', 'icon-lock', '/admin/sensitive-word', 17, 1)")
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('预警记录', 'icon-warning', '/admin/security-alert', 17, 2)")
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
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 18)")
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, 19)")

        # Ensure new function entries exist (for existing databases)
        cursor = conn.execute("SELECT COUNT(*) FROM functions WHERE url='/admin/sensitive-word'")
        if cursor.fetchone()[0] == 0:
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('敏感词管理', 'icon-lock', '/admin/sensitive-word', 17, 1)")
            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, ?)", (new_id,))
        cursor = conn.execute("SELECT COUNT(*) FROM functions WHERE url='/admin/security-alert'")
        if cursor.fetchone()[0] == 0:
            conn.execute("INSERT INTO functions (name, icon, url, parent_id, sort_order) VALUES ('预警记录', 'icon-warning', '/admin/security-alert', 17, 2)")
            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO role_functions (role_id, function_id) VALUES (2, ?)", (new_id,))
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

        cursor = conn.execute("SELECT COUNT(*) FROM sensitive_words")
        count = cursor.fetchone()[0]
        if count <= 20:
            seed_words = [
                # 政治类 - 高风险
                ("颠覆国家政权", "政治", 3),
                ("危害国家安全", "政治", 3),
                ("泄露国家秘密", "政治", 3),
                ("破坏国家统一", "政治", 3),
                ("煽动颠覆国家政权", "政治", 3),
                ("分裂国家", "政治", 3),
                ("煽动分裂国家", "政治", 3),
                ("武装叛乱", "政治", 3),
                ("暴乱", "政治", 3),
                ("间谍", "政治", 3),
                ("特务", "政治", 3),
                ("叛国", "政治", 3),
                ("推翻政府", "政治", 3),
                ("反动", "政治", 3),
                ("反党", "政治", 3),
                ("反华", "政治", 3),
                ("煽动民族仇恨", "政治", 3),
                ("民族分裂", "政治", 3),
                ("邪教", "政治", 3),
                ("法轮功", "政治", 3),
                ("恐怖组织", "政治", 3),
                ("恐怖分子", "政治", 3),
                ("恐怖袭击", "政治", 3),
                ("伊斯兰国", "政治", 3),
                ("东突", "政治", 3),
                ("藏独", "政治", 3),
                ("台独", "政治", 3),
                ("港独", "政治", 3),
                ("疆独", "政治", 3),

                # 违法类 - 高风险
                ("枪支弹药", "违法", 3, '[{"type":"proximity","words":["买","枪","弹"],"distance":6},{"type":"proximity","words":["卖","枪"],"distance":4},{"type":"proximity","words":["买","枪支"],"distance":4}]'),
                ("枪支", "违法", 3, '[{"type":"proximity","words":["买","枪"],"distance":5},{"type":"proximity","words":["卖","枪"],"distance":5},{"type":"proximity","words":["做","枪"],"distance":4}]'),
                ("弹药", "违法", 3),
                ("炸药", "违法", 3),
                ("雷管", "违法", 3),
                ("炸弹", "违法", 3, '[{"type":"proximity","words":["做","炸弹"],"distance":4},{"type":"proximity","words":["买","炸弹"],"distance":4}]'),
                ("爆炸物", "违法", 3),
                ("枪支制造", "违法", 3),
                ("贩卖枪支", "违法", 3),
                ("贩卖毒品", "违法", 3),
                ("制毒", "违法", 3),
                ("吸毒", "违法", 3),
                ("贩毒", "违法", 3, '[{"type":"proximity","words":["买","毒"],"distance":3},{"type":"proximity","words":["卖","毒"],"distance":3},{"type":"proximity","words":["要","毒"],"distance":3}]'),
                ("毒品", "违法", 3, '[{"type":"proximity","words":["买","毒"],"distance":3},{"type":"proximity","words":["卖","毒"],"distance":3}]'),
                ("海洛因", "违法", 3),
                ("冰毒", "违法", 3),
                ("吗啡", "违法", 3),
                ("大麻", "违法", 3),
                ("摇头丸", "违法", 3),
                ("K粉", "违法", 3),
                ("可卡因", "违法", 3),
                ("鸦片", "违法", 3),
                ("病毒制作", "违法", 3),
                ("木马病毒", "违法", 3),
                ("勒索病毒", "违法", 3),
                ("黑客攻击", "违法", 3),
                ("DDoS攻击", "违法", 3),
                ("网络攻击工具", "违法", 3),
                ("盗取账号", "违法", 3),
                ("钓鱼网站", "违法", 3),
                ("贩卖公民信息", "违法", 3),
                ("个人信息买卖", "违法", 3),
                ("身份证号贩卖", "违法", 3),
                ("开锁工具", "违法", 3),
                ("假钞", "违法", 3),
                ("假币", "违法", 3),
                ("伪造货币", "违法", 3),
                ("洗钱", "违法", 3),
                ("地下钱庄", "违法", 3),
                ("非法集资", "违法", 3),
                ("传销组织", "违法", 3),
                ("庞氏骗局", "违法", 3),
                ("组织领导传销", "违法", 3),

                # 违法类 - 中风险
                ("网络诈骗", "违法", 2),
                ("电信诈骗", "违法", 2),
                ("诈骗团伙", "违法", 2),
                ("杀猪盘", "违法", 2),
                ("刷单诈骗", "违法", 2),
                ("冒充公检法", "违法", 2),
                ("电话诈骗", "违法", 2),
                ("短信诈骗", "违法", 2),
                ("金融诈骗", "违法", 2),
                ("套路贷", "违法", 2),
                ("高利贷", "违法", 2),
                ("裸贷", "违法", 2),
                ("校园贷", "违法", 2),
                ("赌博网站", "违法", 2),
                ("网络赌博", "违法", 2),
                ("境外赌博", "违法", 2),
                ("六合彩", "违法", 2),
                ("赌球", "违法", 2),
                ("赌场", "违法", 2),
                ("赌资", "违法", 2),
                ("制假售假", "违法", 2),
                ("假冒伪劣", "违法", 2),
                ("侵犯知识产权", "违法", 2),
                ("盗版软件", "违法", 2),
                ("盗版影视", "违法", 2),
                ("商业间谍", "违法", 2),
                ("窃取商业机密", "违法", 2),
                ("内幕交易", "违法", 2),
                ("操纵股市", "违法", 2),
                ("偷税漏税", "违法", 2),
                ("虚开发票", "违法", 2),
                ("骗保", "违法", 2),
                ("医保诈骗", "违法", 2),
                ("拐卖人口", "违法", 2),
                ("拐卖妇女", "违法", 2),
                ("拐卖儿童", "违法", 2),
                ("人体器官交易", "违法", 2),
                ("偷渡", "违法", 2),
                ("走私", "违法", 2),
                ("非法越境", "违法", 2),
                ("黑社会", "违法", 2),
                ("黑恶势力", "违法", 2),
                ("保护伞", "违法", 2),
                ("暴力催收", "违法", 2),
                ("非法拘禁", "违法", 2),
                ("绑架", "违法", 2),
                ("勒索", "违法", 2),
                ("敲诈", "违法", 2),

                # 色情类
                ("色情淫秽", "色情", 2),
                ("色情视频", "色情", 2),
                ("色情直播", "色情", 2),
                ("色情网站", "色情", 2),
                ("黄片", "色情", 2),
                ("A片", "色情", 2),
                ("成人电影", "色情", 2),
                ("情色小说", "色情", 2),
                ("淫秽物品", "色情", 2),
                ("裸聊", "色情", 2),
                ("招嫖", "色情", 2),
                ("卖淫", "色情", 2),
                ("嫖娼", "色情", 2),
                ("嫖客", "色情", 2),
                ("小姐上门", "色情", 2),
                ("援交", "色情", 2),
                ("一夜情", "色情", 2),
                ("约炮", "色情", 2),
                ("性服务", "色情", 2),
                ("儿童色情", "色情", 3),

                # 谣言/虚假信息
                ("散布谣言", "违法", 1),
                ("传播谣言", "违法", 1),
                ("虚假新闻", "违法", 1),
                ("造谣", "违法", 1),
                ("传谣", "违法", 1),
                ("假新闻", "违法", 1),
                ("不实信息", "违法", 1),
                ("网络谣言", "违法", 1),
                ("恶意诽谤", "违法", 1),
                ("诋毁他人", "违法", 1),
                ("人身攻击", "违法", 1),
                ("恶意炒作", "违法", 1),
                ("煽动对立", "违法", 1),
                ("制造恐慌", "违法", 1),
                ("疫情谣言", "违法", 1),
                ("疫苗谣言", "违法", 1),

                # 自杀/自残类
                ("自杀方法", "违法", 2),
                ("如何自杀", "违法", 2),
                ("相约自杀", "违法", 2),
                ("自杀群", "违法", 2),
                ("自残教程", "违法", 2),
                ("割腕", "违法", 1),
                ("蓝鲸游戏", "违法", 3),

                # 违禁物品/管制
                ("管制刀具", "违法", 2),
                ("电击器", "违法", 2),
                ("迷药", "违法", 2),
                ("迷魂药", "违法", 2),
                ("安眠药购买", "违法", 2),
                ("听话水", "违法", 2),
                ("GHB", "违法", 2),
                ("窃听器", "违法", 2),
                ("针孔摄像头", "违法", 2),
                ("偷拍设备", "违法", 2),
                ("伪基站", "违法", 2),
                ("信号干扰器", "违法", 2),
                ("翻墙软件", "违法", 1),
                ("VPN翻墙", "违法", 1),
                ("科学上网", "违法", 1),

                # 高危常见变体/短词组合 - 覆盖常见的规避说法
                ("买枪", "违法", 3),
                ("卖枪", "违法", 3),
                ("做枪", "违法", 3),
                ("造枪", "违法", 3),
                ("持枪", "违法", 3),
                ("藏枪", "违法", 3),
                ("贩枪", "违法", 3),
                ("买毒", "违法", 3),
                ("卖毒", "违法", 3),
                ("买到毒", "违法", 3),
                ("买毒品", "违法", 3),
                ("卖毒品", "违法", 3),
                ("种毒", "违法", 3),
                ("运毒", "违法", 3),
                ("藏毒", "违法", 3),
                ("制弹", "违法", 3),
                ("买弹", "违法", 3),
                ("炸学校", "违法", 3),
                ("炸政府", "违法", 3),
                ("买迷药", "违法", 2),
                ("买窃听", "违法", 2),
                ("买监听", "违法", 2),
                ("招嫖信息", "色情", 2),
                ("找小姐", "色情", 2),
                ("上门服务", "色情", 2),
            ]
            for item in seed_words:
                word = item[0]
                category = item[1]
                severity = item[2]
                patterns = item[3] if len(item) > 3 else ""
                conn.execute(
                    "INSERT OR IGNORE INTO sensitive_words (word, category, severity, patterns) VALUES (?,?,?,?)",
                    (word, category, severity, patterns)
                )