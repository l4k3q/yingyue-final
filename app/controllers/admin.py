import json
import os
import shutil
import io
import csv
from types import SimpleNamespace
import tornado.web

from app.models.admin import AdminRepository
from app.models.user import UserRepository
from app.models.role import RoleRepository
from app.models.function import FunctionRepository
from app.models.watch import WatchSourceRepository, WatchRecordRepository, WatchCollector
from app.models.model import AIModelRepository, AIModelService, mask_api_key
from app.models.warehouse import DataWarehouseRepository, DeepCollectTaskRepository, DeepCollectService
from app.models.digital_employee import DigitalEmployeeRepository, DigitalEmployeeService
from app.models.sensitive_word import SensitiveWordRepository
from app.models.security_alert import SecurityAlertRepository, SecurityAlertService
from app.models.digital_employee import DigitalEmployeeRepository, DigitalEmployeeService, APIInterfaceRepository
from app.models.setting import SystemSettingRepository
from app.models.conversations import ConversationRepository, MessageRepository
from app.models.skills import SkillRepository


def _to_obj(d: dict) -> SimpleNamespace:
    """Convert dict to object for Tornado template dot-access"""
    return SimpleNamespace(**d) if d else None


def _to_obj_list(items: list) -> list:
    """Convert list of dicts to list of SimpleNamespace objects"""
    return [SimpleNamespace(**d) for d in items] if items else []


class AdminBaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        admin = self.get_secure_cookie("admin")
        if not admin:
            return None
        return admin.decode("utf-8")

    def get_current_role_id(self):
        role_cookie = self.get_secure_cookie("admin_role")
        if role_cookie:
            try:
                return int(role_cookie.decode("utf-8"))
            except ValueError:
                return 0
        current_user = self.get_current_user()
        user = UserRepository.get_user_by_username(current_user) if current_user else None
        return int(user.get("role_id", 0)) if user else 0

    def get_template_namespace(self):
        namespace = super().get_template_namespace()
        current_user = self.get_current_user()
        role_id = self.get_current_role_id()
        try:
            settings_list = SystemSettingRepository.get_all_settings()
            site = {setting["key"]: setting["value"] for setting in settings_list}
        except Exception:
            site = {"site_name": "智能瞭望与问数系统", "site_subtitle": "DataFinderAgentOS"}
        namespace.update({
            "current_admin": current_user or "",
            "current_path": self.request.path,
            "admin_menu": FunctionRepository.get_menu_tree_for_user(current_user or "", role_id),
            "is_menu_active": self.is_menu_active,
            "site": site,
        })
        return namespace

    def is_menu_active(self, menu):
        path = self.request.path.rstrip("/") or self.request.path
        url = (menu.get("url") or "").rstrip("/")
        if url and (path == url or path.startswith(url + "/")):
            return True
        for child in menu.get("children", []):
            child_url = (child.get("url") or "").rstrip("/")
            if child_url and (path == child_url or path.startswith(child_url + "/")):
                return True
        return False

    def write_json(self, payload, status=200):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.set_status(status)
        self.write(json.dumps(payload, ensure_ascii=False))

    def prepare(self):
        current_user = self.get_current_user()
        if not current_user:
            self.redirect("/admin/login")
            return
        if current_user == "admin":
            return
        role_id = self.get_current_role_id()
        if not FunctionRepository.role_can_access_path(role_id, self.request.path):
            if self.request.method in ("POST", "PUT", "DELETE") or self.request.headers.get("X-Requested-With"):
                self.write_json({"status": "error", "message": "无权限访问该后台功能"}, status=403)
            else:
                self.set_status(403)
                self.write("<h2>403 无权限</h2><p>当前角色未被授权访问该后台功能。</p>")
            self.finish()

    def has_function_permission(self, url: str) -> bool:
        """校验当前管理员角色是否拥有指定 URL 对应的功能权限。admin/系统管理员默认放行。"""
        username = self.get_current_user()
        role_id = self.get_current_role_id()
        # admin 账号与系统管理员角色默认拥有所有权限
        if username == "admin" or role_id == 2:
            return True

        # 兼容旧数据库：数智大屏功能 URL 可能为 /admin/dashboard 或 /admin/screen
        check_urls = [url]
        if url == "/admin/screen":
            check_urls.append("/admin/dashboard")
        elif url == "/admin/dashboard":
            check_urls.append("/admin/screen")

        allowed_ids = RoleRepository.get_role_functions(role_id)
        for check_url in check_urls:
            func = FunctionRepository.get_function_by_url(check_url)
            if func and func["id"] in allowed_ids:
                return True
        return False

    def require_function_permission(self, url: str):
        """无权限时跳转至无权限提示页。"""
        if not self.has_function_permission(url):
            self.redirect("/admin/no_permission")
            return False
        return True

    def render(self, template_name, **kwargs):
        """向所有后台模板注入当前用户拥有的功能权限列表，便于菜单按需展示。"""
        if "user_functions" not in kwargs:
            role_id = self.get_current_role_id()
            if role_id and (self.get_current_user() == "admin" or role_id == 2):
                kwargs["user_functions"] = [f["url"] for f in FunctionRepository.get_all_functions() if f.get("url")]
            elif role_id:
                allowed_ids = RoleRepository.get_role_functions(role_id)
                kwargs["user_functions"] = [
                    f["url"] for f in FunctionRepository.get_all_functions()
                    if f.get("id") in allowed_ids and f.get("url")
                ]
            else:
                kwargs["user_functions"] = []
        super().render(template_name, **kwargs)

class AdminLoginHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("admin/login.html", title="管理员登录", error=None)

    def post(self):
        username = self.get_body_argument("username", "")
        password = self.get_body_argument("password", "")

        if AdminRepository.verify_admin(username, password):
            user = UserRepository.get_user_by_username(username)
            if user:
                self.set_secure_cookie("admin", username)
                self.set_secure_cookie("admin_id", str(user["id"]))
                self.set_secure_cookie("admin_role", str(user["role_id"]))
            else:
                self.set_secure_cookie("admin", username)
            self.redirect("/admin/index")
        else:
            self.set_status(401)
            self.render("admin/login.html", title="管理员登录", error="用户名或密码不正确")


class AdminLogoutHandler(AdminBaseHandler):
    def post(self):
        self.clear_cookie("admin")
        self.clear_cookie("admin_id")
        self.clear_cookie("admin_role")
        self.redirect("/admin/login")


class AdminIndexHandler(AdminBaseHandler):
    def get(self):
        users, _ = UserRepository.get_users(page=1, page_size=5)
        admins, _ = AdminRepository.get_admins(page=1, page_size=5)
        roles, _ = RoleRepository.get_roles(page=1, page_size=5)
        functions, _ = FunctionRepository.get_functions(page=1, page_size=5)
        _, user_total = UserRepository.get_users(page=1, page_size=1)
        _, role_total = RoleRepository.get_roles(page=1, page_size=1)
        _, function_total = FunctionRepository.get_functions(page=1, page_size=1)
        _, model_total = AIModelRepository.get_models(page=1, page_size=1)
        token_stats = AIModelRepository.get_token_stats()
        default_model = AIModelRepository.get_default_model()
        watch_stats = WatchRecordRepository.get_stats()
        warehouse_stats = DataWarehouseRepository.get_stats()
        dashboard_stats = {
            "user_total": user_total,
            "role_total": role_total,
            "function_total": function_total,
            "model_total": model_total,
            "token_total": token_stats.get("total") or 0,
            "watch_total": watch_stats.get("total") or 0,
            "watch_success": watch_stats.get("success") or 0,
            "warehouse_total": warehouse_stats.get("total") or 0,
            "deep_collected": warehouse_stats.get("deep_collected") or 0,
            "default_model": default_model,
        }
        self.render(
            "admin/index.html",
            title="控制台",
            users=users,
            admins=admins,
            roles=roles,
            functions=functions,
            stats=dashboard_stats,
        )


class AdminUserHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        users, total = UserRepository.get_users(page=page, page_size=20, keyword=keyword)
        roles, _ = RoleRepository.get_roles(page=1, page_size=100)
        current_user = self.get_current_user()
        can_manage_users = current_user == "admin" or FunctionRepository.role_can_access_path(self.get_current_role_id(), "/admin/users")
        self.render("admin/users.html", title="用户管理", users=users, total=total, page=page, keyword=keyword, roles=roles, is_admin=current_user == "admin", can_manage_users=can_manage_users)

    def post(self):
        action = self.get_body_argument("action", "")
        current_user = self.get_current_user()
        can_manage_users = current_user == "admin" or FunctionRepository.role_can_access_path(self.get_current_role_id(), "/admin/users")
        
        if action == "add":
            if not can_manage_users:
                self.write_json({"status": "error", "message": "当前角色无新增用户权限"})
                return
            username = self.get_body_argument("username", "")
            password = self.get_body_argument("password", "")
            role_id = int(self.get_body_argument("role_id", 1))
            if UserRepository.create_user(username, password, role_id):
                self.write_json({"status": "success", "message": "用户添加成功"})
            else:
                self.write_json({"status": "error", "message": "用户名已存在"})
        elif action == "edit":
            if not can_manage_users:
                self.write_json({"status": "error", "message": "当前角色无编辑用户权限"})
                return
            user_id = int(self.get_body_argument("id", 0))
            user = UserRepository.get_user_by_id(user_id)
            if user and user["username"] == "admin":
                self.write_json({"status": "error", "message": "超级管理员不允许修改用户名和权限"})
                return
            username = self.get_body_argument("username", "")
            role_id = int(self.get_body_argument("role_id", 1))
            if UserRepository.update_user(user_id, username, role_id):
                self.write_json({"status": "success", "message": "用户修改成功"})
            else:
                self.write_json({"status": "error", "message": "用户名已存在"})
        elif action == "change_pwd":
            user_id = int(self.get_body_argument("id", 0))
            user = UserRepository.get_user_by_id(user_id)
            if user and user["username"] != current_user:
                self.write_json({"status": "error", "message": "只允许修改自己的密码"})
                return
            password = self.get_body_argument("password", "")
            if UserRepository.update_password(user_id, password):
                self.write_json({"status": "success", "message": "密码修改成功"})
            else:
                self.write_json({"status": "error", "message": "密码修改失败"})
        elif action == "delete":
            if not can_manage_users:
                self.write_json({"status": "error", "message": "当前角色无删除用户权限"})
                return
            user_id = int(self.get_body_argument("id", 0))
            user = UserRepository.get_user_by_id(user_id)
            if user and user["username"] == "admin":
                self.write_json({"status": "error", "message": "超级管理员不允许删除"})
                return
            UserRepository.delete_user(user_id)
            self.write_json({"status": "success"})
        elif action == "toggle":
            if not can_manage_users:
                self.write_json({"status": "error", "message": "当前角色无禁用用户权限"})
                return
            user_id = int(self.get_body_argument("id", 0))
            user = UserRepository.get_user_by_id(user_id)
            if user and user["username"] == "admin":
                self.write_json({"status": "error", "message": "超级管理员不允许禁用"})
                return
            status = int(self.get_body_argument("status", 0))
            UserRepository.toggle_user_status(user_id, status)
            self.write_json({"status": "success"})


class AdminRoleHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        roles, total = RoleRepository.get_roles(page=page, page_size=20, keyword=keyword)
        self.render("admin/roles.html", title="角色管理", roles=roles, total=total, page=page, keyword=keyword)

    def post(self):
        action = self.get_body_argument("action", "")
        if action == "add":
            name = self.get_body_argument("name", "")
            description = self.get_body_argument("description", "")
            if RoleRepository.create_role(name, description):
                self.redirect("/admin/roles")
            else:
                self.write(json.dumps({"status": "error", "message": "角色名称已存在"}))
        elif action == "edit":
            role_id = int(self.get_body_argument("id", 0))
            name = self.get_body_argument("name", "")
            description = self.get_body_argument("description", "")
            role = RoleRepository.get_role_by_id(role_id)
            if role and role["is_default"]:
                self.write(json.dumps({"status": "error", "message": "默认角色不允许修改"}))
                return
            if RoleRepository.update_role(role_id, name, description):
                self.redirect("/admin/roles")
            else:
                self.write(json.dumps({"status": "error", "message": "角色名称已存在"}))
        elif action == "delete":
            role_id = int(self.get_body_argument("id", 0))
            role = RoleRepository.get_role_by_id(role_id)
            if role and role["is_default"]:
                self.write(json.dumps({"status": "error", "message": "默认角色不允许删除"}))
                return
            RoleRepository.delete_role(role_id)
            self.write(json.dumps({"status": "success"}))


class AdminRoleFunctionsHandler(AdminBaseHandler):
    def get(self):
        role_id = int(self.get_query_argument("role_id", 0))
        role = RoleRepository.get_role_by_id(role_id)
        function_tree = FunctionRepository.get_function_tree(only_enabled=True)
        selected_ids = RoleRepository.get_role_functions(role_id)
        self.render(
            "admin/role_functions.html",
            title="角色权限配置",
            role=role,
            function_nodes=function_tree,
            selected_ids=selected_ids,
        )

    def post(self):
        role_id = int(self.get_body_argument("role_id", 0))
        role = RoleRepository.get_role_by_id(role_id)
        if role and role["is_default"]:
            self.write_json({"status": "error", "message": "默认角色权限不允许修改"})
            return
        function_ids = self.get_body_argument("function_ids", "")
        if function_ids:
            function_ids = [int(f) for f in function_ids.split(",") if f.strip()]
        else:
            function_ids = [int(f) for f in self.get_body_arguments("function_check") if f.strip()]
        RoleRepository.update_role_functions(role_id, function_ids)
        self.redirect("/admin/roles")


class AdminFunctionHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        functions, total = FunctionRepository.get_functions(page=page, page_size=20, keyword=keyword)
        all_functions = FunctionRepository.get_all_functions()
        parent_options = [f for f in all_functions if f["parent_id"] == 0]
        self.render("admin/functions.html", title="功能管理", functions=functions, total=total, page=page, keyword=keyword, parent_options=parent_options)

    def post(self):
        action = self.get_body_argument("action", "")
        if action == "add":
            name = self.get_body_argument("name", "")
            icon = self.get_body_argument("icon", "")
            url = self.get_body_argument("url", "")
            parent_id = int(self.get_body_argument("parent_id", 0))
            sort_order = int(self.get_body_argument("sort_order", 0))
            FunctionRepository.create_function(name, icon, url, parent_id, sort_order)
            self.redirect("/admin/functions")
        elif action == "edit":
            func_id = int(self.get_body_argument("id", 0))
            name = self.get_body_argument("name", "")
            icon = self.get_body_argument("icon", "")
            url = self.get_body_argument("url", "")
            parent_id = int(self.get_body_argument("parent_id", 0))
            sort_order = int(self.get_body_argument("sort_order", 0))
            FunctionRepository.update_function(func_id, name, icon, url, parent_id, sort_order)
            self.redirect("/admin/functions")
        elif action == "delete":
            func_id = int(self.get_body_argument("id", 0))
            FunctionRepository.delete_function(func_id)
            self.write(json.dumps({"status": "success"}))
        elif action == "toggle":
            func_id = int(self.get_body_argument("id", 0))
            status = int(self.get_body_argument("status", 0))
            FunctionRepository.toggle_function_status(func_id, status)
            self.write(json.dumps({"status": "success"}))


class AdminMenuHandler(AdminBaseHandler):
    def get(self):
        function_tree = FunctionRepository.get_function_tree()
        self.render("admin/menus.html", title="菜单管理", functions=function_tree, function_tree_json=json.dumps(function_tree))


class AdminWatchHandler(AdminBaseHandler):
    def get(self):
        sources = WatchSourceRepository.get_enabled_sources()
        records, total = WatchRecordRepository.get_records(page=1, page_size=36)
        processed_records = self._process_records(records)
        self.render("admin/watch.html", title="瞭望采集", sources=sources, records=processed_records)

    def post(self):
        action = self.get_body_argument("action", "")
        if action == "collect":
            keyword = self.get_body_argument("keyword", "")
            source_ids = self.get_body_argument("source_ids", "")
            source_ids = [int(s) for s in source_ids.split(",") if s.strip()]

            for source_id in source_ids:
                source = WatchSourceRepository.get_source_by_id(source_id)
                html_content = WatchCollector.collect(source_id, keyword, page=1)
                if html_content and "采集失败" not in html_content:
                    # 根据源的配置选择解析器
                    parser_name = WatchCollector.get_parser(source)
                    if parser_name == "sina_news":
                        articles = WatchCollector.parse_sina_news(html_content)
                    elif parser_name == "sogou_news":
                        articles = WatchCollector.parse_sogou_news(html_content)
                    elif parser_name == "360_news":
                        articles = WatchCollector.parse_360_news(html_content)
                    else:
                        articles = WatchCollector.parse_baidu_news(html_content)
                    WatchRecordRepository.create_record(source_id, keyword, page=1, data=json.dumps(articles), status=1)
                    scan_text = keyword + " " + " ".join([
                        a.get("title", "") + " " + a.get("description", "")
                        for a in (articles if isinstance(articles, list) else [])
                    ])
                    is_safe, matched = SensitiveWordRepository.scan(scan_text)
                    SensitiveWordRepository.create_scan_log("watch_record", 0, scan_text, is_safe, len(matched))
                    if not is_safe:
                        risk = SensitiveWordRepository.highest_risk_level(matched)
                        SecurityAlertRepository.create_alert(
                            "watch_record", 0, 0, "",
                            matched, scan_text[:300], risk,
                        )
                else:
                    WatchRecordRepository.create_record(source_id, keyword, page=1, data=html_content or "", status=0)

            sources = WatchSourceRepository.get_enabled_sources()
            records, total = WatchRecordRepository.get_records(page=1, page_size=36)
            processed_records = self._process_records(records)
            self.render("admin/watch.html", title="瞭望采集", sources=sources, records=processed_records)
    
    def _process_records(self, records):
        from app.models.skills_enhancement import SkillsEnhancementEngine

        processed = []
        for record in records:
            articles = []
            if record.get("data"):
                try:
                    articles = json.loads(record["data"])
                except:
                    articles = []
            if isinstance(articles, list):
                # 应用瞭望采集类技能增强（数据清洗）
                if articles:
                    enhancement_result = SkillsEnhancementEngine.run_enhancements_by_category(
                        category=1,  # 瞭望采集类
                        data=articles
                    )
                    articles = enhancement_result.get("enhanced", articles)
                record["articles"] = articles
            else:
                record["articles"] = []
            processed.append(record)
        return processed


class AdminWatchSourceHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        sources, total = WatchSourceRepository.get_sources(page=page, page_size=20, keyword=keyword)
        self.render("admin/watch_source.html", title="瞭源管理", sources=sources, total=total, page=page, keyword=keyword)

    def post(self):
        action = self.get_body_argument("action", "")
        if action == "add":
            name = self.get_body_argument("name", "")
            url = self.get_body_argument("url", "")
            request_headers = self.get_body_argument("request_headers", "")
            params = self.get_body_argument("params", "")
            description = self.get_body_argument("description", "")
            collect_config = self.get_body_argument("collect_config", "")
            WatchSourceRepository.create_source(name, url, request_headers, params, description, collect_config)
            self.redirect("/admin/watch/source")
        elif action == "edit":
            source_id = int(self.get_body_argument("id", 0))
            name = self.get_body_argument("name", "")
            url = self.get_body_argument("url", "")
            request_headers = self.get_body_argument("request_headers", "")
            params = self.get_body_argument("params", "")
            description = self.get_body_argument("description", "")
            collect_config = self.get_body_argument("collect_config", "")
            WatchSourceRepository.update_source(source_id, name, url, request_headers, params, description, collect_config)
            self.redirect("/admin/watch/source")
        elif action == "delete":
            source_id = int(self.get_body_argument("id", 0))
            WatchSourceRepository.delete_source(source_id)
            self.write(json.dumps({"status": "success"}))
        elif action == "toggle":
            source_id = int(self.get_body_argument("id", 0))
            status = int(self.get_body_argument("status", 0))
            WatchSourceRepository.toggle_source_status(source_id, status)
            self.write(json.dumps({"status": "success"}))
        elif action == "test":
            source_id = int(self.get_body_argument("id", 0))
            keyword = self.get_body_argument("keyword", "测试")
            source = WatchSourceRepository.get_source_by_id(source_id)
            html_content = WatchCollector.collect(source_id, keyword, page=1)
            if html_content and "采集失败" not in html_content:
                # 根据源的配置选择解析器
                parser_name = WatchCollector.get_parser(source)
                if parser_name == "sina_news":
                    articles = WatchCollector.parse_sina_news(html_content)
                elif parser_name == "sogou_news":
                    articles = WatchCollector.parse_sogou_news(html_content)
                elif parser_name == "360_news":
                    articles = WatchCollector.parse_360_news(html_content)
                else:
                    articles = WatchCollector.parse_baidu_news(html_content)
                self.write(json.dumps({"status": "success", "data": articles}))
            else:
                self.write(json.dumps({"status": "error", "message": html_content}))


class AdminDataHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        source = self.get_query_argument("source", "")
        records, total = DataWarehouseRepository.get_records(page=page, page_size=20, keyword=keyword, source=source)
        stats = DataWarehouseRepository.get_stats()
        self.render("admin/data.html", title="数据仓库", records=records, total=total, page=page, keyword=keyword, source=source, stats=stats)

    def post(self):
        import json
        action = self.get_body_argument("action", "")
        if action == "view":
            record_id = int(self.get_body_argument("id", 0))
            record = DataWarehouseRepository.get_record_by_id(record_id)
            if record:
                self.write(json.dumps(record))
            else:
                self.write(json.dumps({"status": "error", "message": "记录不存在"}))
        elif action == "delete":
            record_id = int(self.get_body_argument("id", 0))
            DataWarehouseRepository.delete_record(record_id)
            self.write(json.dumps({"status": "success", "message": "删除成功"}))
        elif action == "deep_collect":
            record_id = int(self.get_body_argument("id", 0))
            result = DeepCollectService.execute_deep_collect(record_id)
            if result.get("success", False):
                self.write(json.dumps({"status": "success", "message": result.get("message", "深度采集完成"), "task_id": result.get("task_id")}))
            else:
                self.write(json.dumps({"status": "error", "message": result.get("error", "采集失败")}))
        elif action == "batch_deep_collect":
            record_ids_json = self.get_body_argument("ids", "")
            try:
                record_ids = json.loads(record_ids_json)
                results = DeepCollectService.batch_deep_collect(record_ids)
                success_count = sum(1 for r in results if r.get("success", False))
                self.write(json.dumps({"status": "success", "message": f"批量采集完成，成功 {success_count}/{len(record_ids)}", "results": results}))
            except Exception as e:
                self.write(json.dumps({"status": "error", "message": str(e)}))
        elif action == "deep_collect_detail":
            record_id = int(self.get_body_argument("id", 0))
            detail = DeepCollectService.get_deep_collect_detail(record_id)
            self.write(json.dumps(detail))
        elif action == "deep_collect_tasks":
            record_id = int(self.get_body_argument("record_id", 0))
            status = int(self.get_body_argument("status", -1))
            tasks, total = DeepCollectTaskRepository.get_tasks(record_id=record_id if record_id > 0 else 0, status=status)
            self.write(json.dumps({"status": "success", "data": tasks, "total": total}))
        elif action == "save_to_warehouse":
            articles_json = self.get_body_argument("articles", "")
            source_name = self.get_body_argument("source_name", "")
            keyword = self.get_body_argument("keyword", "")
            try:
                articles = json.loads(articles_json)
                records = []
                for article in articles:
                    title = article.get("title", "")
                    summary = article.get("summary", article.get("description", ""))
                    scan_text = f"{title} {summary} {keyword}"
                    is_safe, matched = SensitiveWordRepository.scan(scan_text)
                    SensitiveWordRepository.create_scan_log("data_warehouse", 0, scan_text, is_safe, len(matched))
                    if not is_safe:
                        risk = SensitiveWordRepository.highest_risk_level(matched)
                        SecurityAlertRepository.create_alert(
                            "data_warehouse", 0, 0, "",
                            matched, scan_text[:300], risk,
                        )
                    records.append((
                        title, summary, "",
                        article.get("url", ""),
                        source_name, 0, keyword,
                        article.get("image_url", article.get("image", ""))
                    ))
                DataWarehouseRepository.add_records(records)
                self.write(json.dumps({"status": "success", "message": f"成功保存 {len(records)} 条数据到仓库"}))
            except Exception as e:
                self.write(json.dumps({"status": "error", "message": str(e)}))


class AdminCollectionHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        source = self.get_query_argument("source", "")
        
        records, total = WatchRecordRepository.get_records(page=page, page_size=20, keyword=keyword)
        
        processed_records = []
        for record in records:
            articles = []
            if record.get("data"):
                try:
                    articles = json.loads(record["data"])
                except:
                    articles = []
            if isinstance(articles, list):
                record["article_count"] = len(articles)
            else:
                record["article_count"] = 0
            processed_records.append(record)
        
        stats = WatchRecordRepository.get_stats()
        
        self.render("admin/collection.html", title="采集管理", records=processed_records, total=total, page=page, keyword=keyword, source=source, stats=stats)


class AdminDigitalEmployeeHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        employee_type = int(self.get_query_argument("type", 0))
        
        employees, total = DigitalEmployeeRepository.get_employees(page=page, page_size=20, keyword=keyword, type=employee_type)
        stats = DigitalEmployeeRepository.get_stats()
        
        models, _ = AIModelRepository.get_models(page=1, page_size=100)
        interfaces = APIInterfaceRepository.get_all_active_interfaces()
        
        self.render("admin/digital_employee.html", title="数字员工", 
                    employees=employees, total=total, page=page, 
                    keyword=keyword, type=employee_type, stats=stats, models=models, interfaces=interfaces)

    def post(self):
        action = self.get_body_argument("action", "")
        
        if action == "get":
            employee_id = int(self.get_body_argument("id", 0))
            employee = DigitalEmployeeRepository.get_employee_by_id(employee_id)
            if employee:
                self.write(json.dumps(employee))
            else:
                self.write(json.dumps({"status": "error", "message": "数字员工不存在"}))
        elif action == "add":
            name = self.get_body_argument("name", "")
            code_name = self.get_body_argument("code_name", "")
            employee_type = int(self.get_body_argument("type", 1))
            model_id = int(self.get_body_argument("model_id", 0))
            prompt = self.get_body_argument("prompt", "")
            skills = self.get_body_argument("skills", "")
            use_crawl4ai = int(self.get_body_argument("use_crawl4ai", 0))
            api_url = self.get_body_argument("api_url", "")
            api_method = self.get_body_argument("api_method", "GET")
            api_headers = self.get_body_argument("api_headers", "")
            api_params = self.get_body_argument("api_params", "")
            api_body = self.get_body_argument("api_body", "")
            api_interface_id = int(self.get_body_argument("api_interface_id", 0))
            card_template = self.get_body_argument("card_template", "")
            description = self.get_body_argument("description", "")
            
            md_files_path = ""
            
            uploaded_files = self.request.files.get("md_files", [])
            if uploaded_files:
                md_files_path = self._save_md_files(code_name, uploaded_files)
            
            if DigitalEmployeeRepository.create_employee(
                name, code_name, employee_type, model_id, prompt, skills,
                use_crawl4ai, api_url, api_method, api_headers, api_params, api_body, description,
                md_files_path=md_files_path, api_interface_id=api_interface_id, card_template=card_template
            ):
                self.write(json.dumps({"status": "success", "message": "数字员工添加成功"}))
            else:
                if md_files_path and os.path.exists(md_files_path):
                    shutil.rmtree(md_files_path)
                self.write(json.dumps({"status": "error", "message": "名称或代号已存在"}))
        
        elif action == "edit":
            employee_id = int(self.get_body_argument("id", 0))
            name = self.get_body_argument("name", "")
            code_name = self.get_body_argument("code_name", "")
            employee_type = int(self.get_body_argument("type", 1))
            model_id = int(self.get_body_argument("model_id", 0))
            prompt = self.get_body_argument("prompt", "")
            skills = self.get_body_argument("skills", "")
            use_crawl4ai = int(self.get_body_argument("use_crawl4ai", 0))
            api_url = self.get_body_argument("api_url", "")
            api_method = self.get_body_argument("api_method", "GET")
            api_headers = self.get_body_argument("api_headers", "")
            api_params = self.get_body_argument("api_params", "")
            api_body = self.get_body_argument("api_body", "")
            api_interface_id = int(self.get_body_argument("api_interface_id", 0))
            card_template = self.get_body_argument("card_template", "")
            description = self.get_body_argument("description", "")
            status = int(self.get_body_argument("status", 1))
            
            employee = DigitalEmployeeRepository.get_employee_by_id(employee_id)
            md_files_path = employee.get("md_files_path", "") if employee else ""
            
            uploaded_files = self.request.files.get("md_files", [])
            if uploaded_files:
                md_files_path = self._save_md_files(code_name, uploaded_files)
            
            if DigitalEmployeeRepository.update_employee(
                employee_id, name, code_name, employee_type, model_id, prompt, skills,
                use_crawl4ai, api_url, api_method, api_headers, api_params, api_body, description, status,
                md_files_path=md_files_path, api_interface_id=api_interface_id, card_template=card_template
            ):
                self.write(json.dumps({"status": "success", "message": "数字员工更新成功"}))
            else:
                self.write(json.dumps({"status": "error", "message": "名称或代号已存在"}))
        
        elif action == "delete":
            employee_id = int(self.get_body_argument("id", 0))
            employee = DigitalEmployeeRepository.get_employee_by_id(employee_id)
            if employee:
                md_files_path = employee.get("md_files_path", "")
                if md_files_path and os.path.exists(md_files_path):
                    shutil.rmtree(md_files_path)
            DigitalEmployeeRepository.delete_employee(employee_id)
            self.write(json.dumps({"status": "success", "message": "删除成功"}))
        
        elif action == "toggle":
            employee_id = int(self.get_body_argument("id", 0))
            status = int(self.get_body_argument("status", 0))
            DigitalEmployeeRepository.toggle_employee_status(employee_id, status)
            self.write(json.dumps({"status": "success", "message": "状态更新成功"}))
        
        elif action == "test":
            employee_id = int(self.get_body_argument("id", 0))
            test_params_json = self.get_body_argument("test_params", "")
            test_params = json.loads(test_params_json) if test_params_json else None
            result = DigitalEmployeeService.test_employee(employee_id, test_params)
            self.write(json.dumps(result))

    def _save_md_files(self, code_name, files):
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "employee_docs")
        employee_dir = os.path.join(base_dir, code_name)
        
        if os.path.exists(employee_dir):
            shutil.rmtree(employee_dir)
        
        os.makedirs(employee_dir, exist_ok=True)
        
        for file in files:
            filename = file["filename"]
            if filename.endswith(".md"):
                file_path = os.path.join(employee_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(file["body"])
        
        return employee_dir


class AdminModelHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        models, total = AIModelRepository.get_models(page=page, page_size=12, keyword=keyword)
        for model in models:
            model["api_key"] = mask_api_key(model["api_key"])
        token_stats = AIModelRepository.get_token_stats()
        self.render("admin/model.html", title="模型引擎", models=models, total=total, page=page, keyword=keyword, token_stats=token_stats)

    def post(self):
        action = self.get_body_argument("action", "")
        if action == "get":
            model_id = int(self.get_body_argument("id", 0))
            model = AIModelRepository.get_model_by_id(model_id)
            if model:
                model["api_key"] = mask_api_key(model["api_key"])
                self.write(json.dumps(model))
            else:
                self.write(json.dumps({"error": "模型不存在"}))
            return
        elif action == "add":
            name = self.get_body_argument("name", "")
            model_id = self.get_body_argument("model_id", "")
            api_key = self.get_body_argument("api_key", "")
            base_url = self.get_body_argument("base_url", "")
            model_type = self.get_body_argument("model_type", "text")
            temperature = float(self.get_body_argument("temperature", 0.7))
            max_tokens = int(self.get_body_argument("max_tokens", 4096))
            top_p = float(self.get_body_argument("top_p", 0.9))
            frequency_penalty = float(self.get_body_argument("frequency_penalty", 0.0))
            presence_penalty = float(self.get_body_argument("presence_penalty", 0.0))
            description = self.get_body_argument("description", "")
            provider = self.get_body_argument("provider", "openai")
            
            if AIModelRepository.create_model(name, model_id, api_key, base_url, temperature, max_tokens, top_p, frequency_penalty, presence_penalty, description, provider, model_type):
                self.write(json.dumps({"status": "success", "message": "模型添加成功"}))
            else:
                self.write(json.dumps({"status": "error", "message": "模型名称已存在"}))
        elif action == "edit":
            model_id = int(self.get_body_argument("id", 0))
            name = self.get_body_argument("name", "")
            model_id_str = self.get_body_argument("model_id", "")
            api_key = self.get_body_argument("api_key", "")
            if "******" in api_key:
                original_model = AIModelRepository.get_model_by_id(model_id)
                if original_model:
                    api_key = original_model["api_key"]
            base_url = self.get_body_argument("base_url", "")
            model_type = self.get_body_argument("model_type", "text")
            temperature = float(self.get_body_argument("temperature", 0.7))
            max_tokens = int(self.get_body_argument("max_tokens", 4096))
            top_p = float(self.get_body_argument("top_p", 0.9))
            frequency_penalty = float(self.get_body_argument("frequency_penalty", 0.0))
            presence_penalty = float(self.get_body_argument("presence_penalty", 0.0))
            description = self.get_body_argument("description", "")
            provider = self.get_body_argument("provider", "openai")
            
            if AIModelRepository.update_model(model_id, name, model_id_str, api_key, base_url, temperature, max_tokens, top_p, frequency_penalty, presence_penalty, description, provider, model_type):
                self.write(json.dumps({"status": "success", "message": "模型更新成功"}))
            else:
                self.write(json.dumps({"status": "error", "message": "模型名称已存在"}))
        elif action == "delete":
            model_id = int(self.get_body_argument("id", 0))
            AIModelRepository.delete_model(model_id)
            self.write(json.dumps({"status": "success", "message": "模型删除成功"}))
        elif action == "set_default":
            model_id = int(self.get_body_argument("id", 0))
            AIModelRepository.set_default_model(model_id)
            self.write(json.dumps({"status": "success", "message": "默认模型设置成功"}))
        elif action == "toggle":
            model_id = int(self.get_body_argument("id", 0))
            status = int(self.get_body_argument("status", 0))
            AIModelRepository.toggle_model_status(model_id, status)
            self.write(json.dumps({"status": "success", "message": "状态更新成功"}))
        elif action == "test":
            model_id = int(self.get_body_argument("id", 0))
            model = AIModelRepository.get_model_by_id(model_id)
            if model:
                result = AIModelService.test_model(model)
                if result["success"]:
                    AIModelRepository.update_tokens(model_id, result["prompt_tokens"], result["completion_tokens"])
                self.write(json.dumps(result))
            else:
                self.write(json.dumps({"status": "error", "message": "模型不存在"}))


class AdminModelTestHandler(AdminBaseHandler):
    def get(self):
        model_id = int(self.get_query_argument("model_id", 0))
        prompt = self.get_query_argument("prompt", "")
        
        model = AIModelRepository.get_model_by_id(model_id)
        if not model:
            self.write(json.dumps({"error": "模型不存在"}))
            return

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        
        messages = [{"role": "user", "content": prompt}]
        full_content = ""
        prompt_tokens = AIModelService.estimate_tokens(prompt)
        completion_tokens = 0
        
        try:
            if model.get("model_type", "text") == "text":
                for chunk in AIModelService.chat_completion(model, messages):
                    if "choices" in chunk and chunk["choices"]:
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            content = delta["content"]
                            full_content += content
                            completion_tokens += AIModelService.estimate_tokens(content)
                            self.write(f"data: {json.dumps({
                                'type': 'token',
                                'content': content,
                                'prompt_tokens': prompt_tokens,
                                'completion_tokens': completion_tokens,
                                'total_tokens': prompt_tokens + completion_tokens
                            }, ensure_ascii=False)}\n\n")
                            self.flush()
            else:
                result = AIModelService.generate_multimodal(model, prompt)
                full_content = result.get("content", "")
                completion_tokens = AIModelService.estimate_tokens(full_content)
                self.write(f"data: {json.dumps({
                    'type': 'token',
                    'content': full_content,
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': prompt_tokens + completion_tokens
                }, ensure_ascii=False)}\n\n")
                self.flush()
            self.write(f"data: {json.dumps({
                'type': 'done',
                'content': full_content,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': prompt_tokens + completion_tokens
            }, ensure_ascii=False)}\n\n")
            AIModelRepository.update_tokens(model_id, prompt_tokens, completion_tokens)
        except Exception as e:
            self.write(f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n")
        self.finish()


class AdminDashboardHandler(AdminBaseHandler):
    def get(self):
        self.render("admin/dashboard.html", title="数智大屏")


class AdminScreenHandler(AdminBaseHandler):
    def get(self):
        if not self.require_function_permission("/admin/screen"):
            return
        self.render("admin/screen.html", title="瞭望采集数智可视化大屏")


class AdminSentimentHandler(AdminBaseHandler):
    def get(self):
        stats = SecurityAlertRepository.get_stats()
        scan_stats = SensitiveWordRepository.get_scan_stats()
        source_dist = SecurityAlertRepository.get_source_distribution()
        risk_dist = SecurityAlertRepository.get_risk_level_distribution()
        trend = SecurityAlertRepository.get_trend(7)
        top_words = SecurityAlertRepository.get_top_matched_words(10)
        recent_alerts = SecurityAlertRepository.get_recent_alerts(5)
        self.render(
            "admin/sentiment.html",
            title="舆情大屏",
            stats=stats,
            scan_stats=scan_stats,
            source_dist=json.dumps(source_dist, ensure_ascii=False),
            risk_dist=json.dumps(risk_dist, ensure_ascii=False),
            trend=json.dumps(trend, ensure_ascii=False),
            top_words=json.dumps(top_words, ensure_ascii=False),
            recent_alerts=recent_alerts,
        )


class AdminSensitiveWordHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        category = self.get_query_argument("category", "")
        words, total = SensitiveWordRepository.get_words(page=page, page_size=20, keyword=keyword, category=category)
        categories = SensitiveWordRepository.get_categories()
        self.render(
            "admin/sensitive_word.html",
            title="敏感词管理",
            words=words, total=total, page=page,
            keyword=keyword, category=category, categories=categories,
        )

    def post(self):
        action = self.get_body_argument("action", "")
        if action == "add":
            word = self.get_body_argument("word", "")
            category = self.get_body_argument("category", "通用")
            severity = int(self.get_body_argument("severity", 1))
            patterns = self.get_body_argument("patterns", "")
            if SensitiveWordRepository.create_word(word, category, severity, patterns):
                self.write(json.dumps({"status": "success", "message": "添加成功"}))
            else:
                self.write(json.dumps({"status": "error", "message": "敏感词已存在"}))
        elif action == "edit":
            word_id = int(self.get_body_argument("id", 0))
            word = self.get_body_argument("word", "")
            category = self.get_body_argument("category", "通用")
            severity = int(self.get_body_argument("severity", 1))
            patterns = self.get_body_argument("patterns", "")
            if SensitiveWordRepository.update_word(word_id, word, category, severity, patterns):
                self.write(json.dumps({"status": "success", "message": "更新成功"}))
            else:
                self.write(json.dumps({"status": "error", "message": "敏感词已存在或更新失败"}))
        elif action == "delete":
            word_id = int(self.get_body_argument("id", 0))
            SensitiveWordRepository.delete_word(word_id)
            self.write(json.dumps({"status": "success", "message": "删除成功"}))
        elif action == "toggle":
            word_id = int(self.get_body_argument("id", 0))
            status = int(self.get_body_argument("status", 0))
            SensitiveWordRepository.toggle_status(word_id, status)
            self.write(json.dumps({"status": "success", "message": "状态更新成功"}))
        elif action == "batch_import":
            words_text = self.get_body_argument("words_text", "")
            added, skipped = SensitiveWordRepository.batch_import(words_text)
            self.write(json.dumps({"status": "success", "message": f"导入完成，成功 {added} 条，跳过 {skipped} 条"}))


class AdminSecurityAlertHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        source_type = self.get_query_argument("source_type", "")
        risk_level = int(self.get_query_argument("risk_level", 0))
        status_filter = int(self.get_query_argument("status_filter", -1))
        alerts, total = SecurityAlertRepository.get_alerts(
            page=page, page_size=20, keyword=keyword,
            source_type=source_type, risk_level=risk_level, status_filter=status_filter,
        )
        stats = SecurityAlertRepository.get_stats()
        self.render(
            "admin/security_alert.html",
            title="预警记录",
            alerts=alerts, total=total, page=page,
            keyword=keyword, source_type=source_type,
            risk_level=risk_level, status_filter=status_filter,
            stats=stats,
        )

    def post(self):
        action = self.get_body_argument("action", "")
        if action == "handle":
            alert_id = int(self.get_body_argument("id", 0))
            status = int(self.get_body_argument("status", 1))
            SecurityAlertRepository.update_alert_status(alert_id, status)
            self.write(json.dumps({"status": "success", "message": "处理成功"}))
        elif action == "ai_analyze":
            alert_id = int(self.get_body_argument("id", 0))
            analysis = SecurityAlertService.analyze_risk(alert_id)
            self.write(json.dumps({"status": "success", "data": analysis}, ensure_ascii=False))
        elif action == "view":
            alert_id = int(self.get_body_argument("id", 0))
            alert = SecurityAlertRepository.get_alert_by_id(alert_id)
            if alert:
                self.write(json.dumps({"status": "success", "data": alert}, ensure_ascii=False))
            else:
                self.write(json.dumps({"status": "error", "message": "预警不存在"}))


class AdminAPIInterfaceHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        
        interfaces, total = APIInterfaceRepository.get_interfaces(page=page, page_size=20, keyword=keyword)
        
        self.render("admin/api_interface.html", title="接口管理", 
                    interfaces=interfaces, total=total, page=page, keyword=keyword)

    def post(self):
        action = self.get_body_argument("action", "")
        
        if action == "get":
            interface_id = int(self.get_body_argument("id", 0))
            interface = APIInterfaceRepository.get_interface_by_id(interface_id)
            if interface:
                self.write(json.dumps(interface))
            else:
                self.write(json.dumps({"status": "error", "message": "接口不存在"}))
        elif action == "add":
            name = self.get_body_argument("name", "")
            url = self.get_body_argument("url", "")
            method = self.get_body_argument("method", "GET")
            headers = self.get_body_argument("headers", "{}")
            params = self.get_body_argument("params", "{}")
            body = self.get_body_argument("body", "{}")
            response_mapping = self.get_body_argument("response_mapping", "{}")
            description = self.get_body_argument("description", "")
            
            if APIInterfaceRepository.create_interface(
                name, url, method, headers, params, body, response_mapping, description
            ):
                self.write(json.dumps({"status": "success", "message": "接口添加成功"}))
            else:
                self.write(json.dumps({"status": "error", "message": "名称已存在"}))
        
        elif action == "edit":
            interface_id = int(self.get_body_argument("id", 0))
            name = self.get_body_argument("name", "")
            url = self.get_body_argument("url", "")
            method = self.get_body_argument("method", "GET")
            headers = self.get_body_argument("headers", "{}")
            params = self.get_body_argument("params", "{}")
            body = self.get_body_argument("body", "{}")
            response_mapping = self.get_body_argument("response_mapping", "{}")
            description = self.get_body_argument("description", "")
            status = int(self.get_body_argument("status", 1))
            
            if APIInterfaceRepository.update_interface(
                interface_id, name, url, method, headers, params, body, response_mapping, description, status
            ):
                self.write(json.dumps({"status": "success", "message": "接口更新成功"}))
            else:
                self.write(json.dumps({"status": "error", "message": "名称已存在"}))
        
        elif action == "delete":
            interface_id = int(self.get_body_argument("id", 0))
            APIInterfaceRepository.delete_interface(interface_id)
            self.write(json.dumps({"status": "success", "message": "删除成功"}))
        
        elif action == "toggle":
            interface_id = int(self.get_body_argument("id", 0))
            status = int(self.get_body_argument("status", 0))
            APIInterfaceRepository.toggle_interface_status(interface_id, status)
            self.write(json.dumps({"status": "success", "message": "状态更新成功"}))


class AdminNoPermissionHandler(AdminBaseHandler):
    def get(self):
        self.render("admin/no_permission.html", title="无访问权限")


class AdminSettingHandler(AdminBaseHandler):
    def get(self):
        groups = SystemSettingRepository.get_grouped_settings()
        self.render("admin/setting.html", title="系统设置", groups=groups)

    def post(self):
        action = self.get_body_argument("action", "")
        if action == "save":
            settings = SystemSettingRepository.get_all_settings()
            for s in settings:
                key = s["key"]
                new_value = self.get_body_argument(key, None)
                if new_value is not None:
                    SystemSettingRepository.update_setting(key, new_value)
            self.write(json.dumps({"status": "success", "message": "设置保存成功"}))
        elif action == "reset":
            # For reset, we could re-seed but simplest is to redirect back
            self.write(json.dumps({"status": "success", "message": "已重置"}))
        else:
            self.write(json.dumps({"status": "error", "message": "未知操作"}))


class AdminConversationHandler(AdminBaseHandler):
    """会话管理"""
    
    def get(self):
        page = int(self.get_query_argument("page", 1))
        user_id = self.get_query_argument("user_id", None)
        business_type = self.get_query_argument("business_type", None)
        archive_status = self.get_query_argument("archive_status", None)
        status = self.get_query_argument("status", None)
        start_date = self.get_query_argument("start_date", None)
        end_date = self.get_query_argument("end_date", None)
        keyword = self.get_query_argument("keyword", None)
        
        # 转换参数类型
        user_id = int(user_id) if user_id else None
        business_type = int(business_type) if business_type else None
        archive_status = int(archive_status) if archive_status else None
        status = int(status) if status else None
        
        # 获取会话列表
        conversations, total = ConversationRepository.get_all_conversations_admin(
            page=page,
            user_id=user_id,
            business_type=business_type,
            archive_status=archive_status,
            status=status,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword
        )
        
        # 获取统计数据
        stats = ConversationRepository.get_conversation_stats()
        
        # 获取用户列表（用于筛选下拉）
        users, _ = UserRepository.get_users(page=1, page_size=1000)
        
        self.render(
            "admin/conversations.html",
            title="会话管理",
            conversations=conversations,
            total=total,
            page=page,
            stats=stats,
            users=users,
            filters=SimpleNamespace(
                user_id=user_id or "",
                business_type=business_type if business_type is not None else "",
                archive_status=archive_status if archive_status is not None else "",
                status=status if status is not None else "",
                start_date=start_date or "",
                end_date=end_date or "",
                keyword=keyword or ""
            )
        )
    
    def post(self):
        action = self.get_body_argument("action", "")
        
        if action == "archive":
            conversation_id = int(self.get_body_argument("conversation_id", 0))
            ConversationRepository.archive_conversation(conversation_id)
            self.write(json.dumps({"status": "success", "message": "会话已归档"}))
        
        elif action == "unarchive":
            conversation_id = int(self.get_body_argument("conversation_id", 0))
            ConversationRepository.unarchive_conversation(conversation_id)
            self.write(json.dumps({"status": "success", "message": "会话已取消归档"}))
        
        elif action == "delete":
            conversation_id = int(self.get_body_argument("conversation_id", 0))
            ConversationRepository.delete_conversation(conversation_id)
            self.write(json.dumps({"status": "success", "message": "会话已删除"}))
        
        elif action == "batch_archive":
            ids_json = self.get_body_argument("ids", "[]")
            ids = json.loads(ids_json)
            ConversationRepository.batch_archive_conversations(ids)
            self.write(json.dumps({"status": "success", "message": f"已归档 {len(ids)} 个会话"}))
        
        elif action == "batch_delete":
            ids_json = self.get_body_argument("ids", "[]")
            ids = json.loads(ids_json)
            ConversationRepository.batch_delete_conversations(ids)
            self.write(json.dumps({"status": "success", "message": f"已删除 {len(ids)} 个会话"}))
        
        else:
            self.write(json.dumps({"status": "error", "message": "未知操作"}))


class AdminMessageHandler(AdminBaseHandler):
    """对话管理"""
    
    def get(self):
        page = int(self.get_query_argument("page", 1))
        conversation_id = self.get_query_argument("conversation_id", None)
        user_id = self.get_query_argument("user_id", None)
        start_date = self.get_query_argument("start_date", None)
        end_date = self.get_query_argument("end_date", None)
        keyword = self.get_query_argument("keyword", None)
        
        # 转换参数类型
        conversation_id = int(conversation_id) if conversation_id else None
        user_id = int(user_id) if user_id else None
        
        # 获取消息列表
        messages, total = MessageRepository.get_all_messages_admin(
            page=page,
            conversation_id=conversation_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword
        )
        
        # 获取用户列表（用于筛选下拉）
        users, _ = UserRepository.get_users(page=1, page_size=1000)
        
        self.render(
            "admin/messages.html",
            title="对话管理",
            messages=messages,
            total=total,
            page=page,
            users=users,
            filters=SimpleNamespace(
                conversation_id=conversation_id or "",
                user_id=user_id or "",
                start_date=start_date or "",
                end_date=end_date or "",
                keyword=keyword or ""
            )
        )
    
    def post(self):
        action = self.get_body_argument("action", "")

        if action == "get_messages":
            conversation_id = int(self.get_body_argument("conversation_id", 0))
            messages = ConversationRepository.get_messages(conversation_id)
            self.write(json.dumps({"status": "success", "messages": messages}))

        elif action == "delete":
            message_id = int(self.get_body_argument("message_id", 0))
            MessageRepository.delete_message(message_id)
            self.write(json.dumps({"status": "success", "message": "消息已删除"}))
        
        elif action == "batch_delete":
            ids_json = self.get_body_argument("ids", "[]")
            ids = json.loads(ids_json)
            MessageRepository.batch_delete_messages(ids)
            self.write(json.dumps({"status": "success", "message": f"已删除 {len(ids)} 条消息"}))
        
        elif action == "clear_conversation":
            conversation_id = int(self.get_body_argument("conversation_id", 0))
            MessageRepository.clear_conversation_messages(conversation_id)
            self.write(json.dumps({"status": "success", "message": "会话消息已清空"}))
        
        elif action == "export":
            conversation_id = self.get_body_argument("conversation_id", None)
            user_id = self.get_body_argument("user_id", None)
            start_date = self.get_body_argument("start_date", None)
            end_date = self.get_body_argument("end_date", None)
            
            conversation_id = int(conversation_id) if conversation_id else None
            user_id = int(user_id) if user_id else None
            
            messages = MessageRepository.export_messages_to_excel(
                conversation_id=conversation_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date
            )
            
            # 生成 CSV 内容
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["消息ID", "会话ID", "会话标题", "用户ID", "用户名", "角色", "内容", "消息类型", "序号", "创建时间"])
            for msg in messages:
                writer.writerow([
                    msg.get("id", ""),
                    msg.get("conversation_id", ""),
                    msg.get("conversation_title", ""),
                    msg.get("user_id", ""),
                    msg.get("username", ""),
                    msg.get("role", ""),
                    msg.get("content", ""),
                    msg.get("msg_type", ""),
                    msg.get("msg_index", ""),
                    msg.get("created_at", "")
                ])
            
            csv_content = output.getvalue()
            output.close()
            
            # 添加 BOM 以支持 Excel 打开中文
            csv_bytes = ("\ufeff" + csv_content).encode("utf-8")
            
            self.set_header("Content-Type", "text/csv; charset=utf-8")
            self.set_header("Content-Disposition", "attachment; filename=messages_export.csv")
            self.write(csv_bytes)
            return

        else:
            self.write(json.dumps({"status": "error", "message": "未知操作"}))


class AdminSkillHandler(AdminBaseHandler):
    """技能管理"""

    def get(self):
        page = int(self.get_query_argument("page", 1))
        category = self.get_query_argument("category", None)
        status = self.get_query_argument("status", None)
        keyword = self.get_query_argument("keyword", None)
        employee_id = self.get_query_argument("employee_id", None)

        category = int(category) if category else None
        status = int(status) if status else None
        employee_id = int(employee_id) if employee_id else None

        skills, total = SkillRepository.get_skills(
            page=page,
            category=category,
            status=status,
            keyword=keyword,
            employee_id=employee_id
        )

        from app.models.digital_employee import DigitalEmployeeRepository
        employees, _ = DigitalEmployeeRepository.get_employees(page=1, page_size=1000)

        categories = [
            SimpleNamespace(value=1, label="瞭望采集"),
            SimpleNamespace(value=2, label="问数分析"),
            SimpleNamespace(value=3, label="可视化大屏"),
        ]

        self.render(
            "admin/skills.html",
            title="技能管理",
            skills=_to_obj_list(skills),
            total=total,
            page=page,
            employees=_to_obj_list(employees),
            categories=categories,
            filters=SimpleNamespace(
                category=category if category is not None else "",
                status=status if status is not None else "",
                keyword=keyword or "",
                employee_id=employee_id or ""
            )
        )

    def post(self):
        action = self.get_body_argument("action", "")

        if action == "get":
            skill_id = int(self.get_body_argument("id", 0))
            skill = SkillRepository.get_skill_detail(skill_id)
            if skill:
                self.write(json.dumps({"status": "success", "skill": skill}))
            else:
                self.write(json.dumps({"status": "error", "message": "技能不存在"}))

        elif action == "add":
            name = self.get_body_argument("name", "").strip()
            category = int(self.get_body_argument("category", 1))
            description = self.get_body_argument("description", "").strip()
            config_json = self.get_body_argument("config_json", "{}").strip()
            enhancement_config = self.get_body_argument("enhancement_config", "{}").strip()

            if not name:
                self.write(json.dumps({"status": "error", "message": "技能名称不能为空"}))
                return
            if category not in (1, 2, 3):
                self.write(json.dumps({"status": "error", "message": "无效的技能分类"}))
                return

            for field_name, val in [("config_json", config_json), ("enhancement_config", enhancement_config)]:
                try:
                    json.loads(val)
                except json.JSONDecodeError as e:
                    self.write(json.dumps({"status": "error", "message": f"{field_name} 格式错误: {str(e)}"}))
                    return

            skill_id = SkillRepository.create_skill(name, category, description, config_json, enhancement_config)
            if skill_id:
                self.write(json.dumps({"status": "success", "message": "技能创建成功", "id": skill_id}))
            else:
                self.write(json.dumps({"status": "error", "message": "创建失败"}))

        elif action == "edit":
            skill_id = int(self.get_body_argument("id", 0))
            name = self.get_body_argument("name", "").strip()
            category = self.get_body_argument("category", None)
            description = self.get_body_argument("description", None)
            config_json = self.get_body_argument("config_json", None)
            enhancement_config = self.get_body_argument("enhancement_config", None)

            category = int(category) if category else None

            if category is not None and category not in (1, 2, 3):
                self.write(json.dumps({"status": "error", "message": "无效的技能分类"}))
                return

            for field_name, val in [("config_json", config_json), ("enhancement_config", enhancement_config)]:
                if val is not None:
                    try:
                        json.loads(val)
                    except json.JSONDecodeError as e:
                        self.write(json.dumps({"status": "error", "message": f"{field_name} 格式错误: {str(e)}"}))
                        return

            if SkillRepository.update_skill(skill_id, name=name or None, category=category,
                                             description=description, config_json=config_json,
                                             enhancement_config=enhancement_config):
                self.write(json.dumps({"status": "success", "message": "技能更新成功"}))
            else:
                self.write(json.dumps({"status": "error", "message": "更新失败"}))

        elif action == "delete":
            skill_id = int(self.get_body_argument("id", 0))
            SkillRepository.delete_skill(skill_id)
            self.write(json.dumps({"status": "success", "message": "技能已删除（关联关系已解绑）"}))

        elif action == "toggle":
            skill_id = int(self.get_body_argument("id", 0))
            status = int(self.get_body_argument("status", 0))
            SkillRepository.toggle_status(skill_id, status)
            self.write(json.dumps({"status": "success", "message": "状态已更新"}))

        elif action == "batch_assign":
            skill_id = int(self.get_body_argument("id", 0))
            ids_json = self.get_body_argument("employee_ids", "[]")
            employee_ids = json.loads(ids_json)

            if not isinstance(employee_ids, list) or not employee_ids:
                self.write(json.dumps({"status": "error", "message": "请选择至少一个数字员工"}))
                return

            from app.models.digital_employee import DigitalEmployeeRepository
            invalid_ids = []
            for eid in employee_ids:
                emp = DigitalEmployeeRepository.get_employee_by_id(eid)
                if not emp:
                    invalid_ids.append(eid)

            if invalid_ids:
                self.write(json.dumps({"status": "error", "message": f"数字员工不存在: {invalid_ids}"}))
                return

            SkillRepository.batch_assign_employees(skill_id, employee_ids)
            self.write(json.dumps({"status": "success", "message": f"已分配 {len(employee_ids)} 名数字员工"}))

        elif action == "batch_disable":
            ids_json = self.get_body_argument("ids", "[]")
            ids = json.loads(ids_json)
            if not ids:
                self.write(json.dumps({"status": "error", "message": "请选择至少一个技能"}))
                return
            for sid in ids:
                SkillRepository.toggle_status(sid, 0)
            self.write(json.dumps({"status": "success", "message": f"已禁用 {len(ids)} 个技能"}))

        else:
            self.write(json.dumps({"status": "error", "message": "未知操作"}))
