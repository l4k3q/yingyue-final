import json
import os
import shutil
import tornado.web

from app.models.admin import AdminRepository
from app.models.user import UserRepository
from app.models.role import RoleRepository
from app.models.function import FunctionRepository
from app.models.watch import WatchSourceRepository, WatchRecordRepository, WatchCollector
from app.models.model import AIModelRepository, AIModelService
from app.models.warehouse import DataWarehouseRepository, DeepCollectTaskRepository, DeepCollectService
from app.models.digital_employee import DigitalEmployeeRepository, DigitalEmployeeService


class AdminBaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        admin = self.get_secure_cookie("admin")
        if not admin:
            return None
        return admin.decode("utf-8")

    def prepare(self):
        if not self.get_current_user():
            self.redirect("/admin/login")


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
        self.render("admin/index.html", title="后台管理", users=users, admins=admins, roles=roles, functions=functions)


class AdminUserHandler(AdminBaseHandler):
    def get(self):
        page = int(self.get_query_argument("page", 1))
        keyword = self.get_query_argument("keyword", "")
        users, total = UserRepository.get_users(page=page, page_size=20, keyword=keyword)
        roles, _ = RoleRepository.get_roles(page=1, page_size=100)
        current_user = self.get_current_user()
        is_admin = current_user == "admin"
        self.render("admin/users.html", title="用户管理", users=users, total=total, page=page, keyword=keyword, roles=roles, is_admin=is_admin)

    def post(self):
        action = self.get_body_argument("action", "")
        current_user = self.get_current_user()
        
        if action == "add":
            if current_user != "admin":
                self.write(json.dumps({"status": "error", "message": "只有超级管理员可以添加用户"}))
                return
            username = self.get_body_argument("username", "")
            password = self.get_body_argument("password", "")
            role_id = int(self.get_body_argument("role_id", 1))
            if UserRepository.create_user(username, password, role_id):
                self.redirect("/admin/users")
            else:
                self.write(json.dumps({"status": "error", "message": "用户名已存在"}))
        elif action == "edit":
            if current_user != "admin":
                self.write(json.dumps({"status": "error", "message": "只有超级管理员可以编辑用户"}))
                return
            user_id = int(self.get_body_argument("id", 0))
            user = UserRepository.get_user_by_id(user_id)
            if user and user["username"] == "admin":
                self.write(json.dumps({"status": "error", "message": "超级管理员不允许修改用户名和权限"}))
                return
            username = self.get_body_argument("username", "")
            role_id = int(self.get_body_argument("role_id", 1))
            if UserRepository.update_user(user_id, username, role_id):
                self.redirect("/admin/users")
            else:
                self.write(json.dumps({"status": "error", "message": "用户名已存在"}))
        elif action == "change_pwd":
            user_id = int(self.get_body_argument("id", 0))
            user = UserRepository.get_user_by_id(user_id)
            if user and user["username"] != current_user:
                self.write(json.dumps({"status": "error", "message": "只允许修改自己的密码"}))
                return
            password = self.get_body_argument("password", "")
            if UserRepository.update_password(user_id, password):
                self.write(json.dumps({"status": "success", "message": "密码修改成功"}))
            else:
                self.write(json.dumps({"status": "error", "message": "密码修改失败"}))
        elif action == "delete":
            if current_user != "admin":
                self.write(json.dumps({"status": "error", "message": "只有超级管理员可以删除用户"}))
                return
            user_id = int(self.get_body_argument("id", 0))
            user = UserRepository.get_user_by_id(user_id)
            if user and user["username"] == "admin":
                self.write(json.dumps({"status": "error", "message": "超级管理员不允许删除"}))
                return
            UserRepository.delete_user(user_id)
            self.write(json.dumps({"status": "success"}))
        elif action == "toggle":
            if current_user != "admin":
                self.write(json.dumps({"status": "error", "message": "只有超级管理员可以禁用用户"}))
                return
            user_id = int(self.get_body_argument("id", 0))
            user = UserRepository.get_user_by_id(user_id)
            if user and user["username"] == "admin":
                self.write(json.dumps({"status": "error", "message": "超级管理员不允许禁用"}))
                return
            status = int(self.get_body_argument("status", 0))
            UserRepository.toggle_user_status(user_id, status)
            self.write(json.dumps({"status": "success"}))


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
        function_tree = FunctionRepository.get_function_tree()
        selected_ids = RoleRepository.get_role_functions(role_id)
        self.render("admin/role_functions.html", title="角色权限配置", role=role, function_tree=json.dumps(function_tree), selected_ids=json.dumps(selected_ids))

    def post(self):
        role_id = int(self.get_body_argument("role_id", 0))
        function_ids = self.get_body_argument("function_ids", "")
        function_ids = [int(f) for f in function_ids.split(",") if f.strip()]
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
                html_content = WatchCollector.collect(source_id, keyword, page=1)
                if html_content and "采集失败" not in html_content:
                    articles = WatchCollector.parse_baidu_news(html_content)
                    WatchRecordRepository.create_record(source_id, keyword, page=1, data=json.dumps(articles), status=1)
                else:
                    WatchRecordRepository.create_record(source_id, keyword, page=1, data=html_content or "", status=0)
            
            sources = WatchSourceRepository.get_enabled_sources()
            records, total = WatchRecordRepository.get_records(page=1, page_size=36)
            processed_records = self._process_records(records)
            self.render("admin/watch.html", title="瞭望采集", sources=sources, records=processed_records)
    
    def _process_records(self, records):
        processed = []
        for record in records:
            articles = []
            if record.get("data"):
                try:
                    articles = json.loads(record["data"])
                except:
                    articles = []
            if isinstance(articles, list):
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
            WatchSourceRepository.create_source(name, url, request_headers, params, description)
            self.redirect("/admin/watch/source")
        elif action == "edit":
            source_id = int(self.get_body_argument("id", 0))
            name = self.get_body_argument("name", "")
            url = self.get_body_argument("url", "")
            request_headers = self.get_body_argument("request_headers", "")
            params = self.get_body_argument("params", "")
            description = self.get_body_argument("description", "")
            WatchSourceRepository.update_source(source_id, name, url, request_headers, params, description)
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
            html_content = WatchCollector.collect(source_id, keyword, page=1)
            if html_content and "采集失败" not in html_content:
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
                    records.append((
                        article.get("title", ""),
                        article.get("summary", article.get("description", "")),
                        "",
                        article.get("url", ""),
                        source_name,
                        0,
                        keyword,
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
        
        self.render("admin/digital_employee.html", title="数字员工", 
                    employees=employees, total=total, page=page, 
                    keyword=keyword, type=employee_type, stats=stats, models=models)

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
            description = self.get_body_argument("description", "")
            
            md_files_path = ""
            
            uploaded_files = self.request.files.get("md_files", [])
            if uploaded_files:
                md_files_path = self._save_md_files(code_name, uploaded_files)
            
            if DigitalEmployeeRepository.create_employee(
                name, code_name, employee_type, model_id, prompt, skills,
                use_crawl4ai, api_url, api_method, api_headers, api_params, api_body, description,
                md_files_path=md_files_path
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
                md_files_path=md_files_path
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
        token_stats = AIModelRepository.get_token_stats()
        self.render("admin/model.html", title="模型引擎", models=models, total=total, page=page, keyword=keyword, token_stats=token_stats)

    def post(self):
        action = self.get_body_argument("action", "")
        if action == "get":
            model_id = int(self.get_body_argument("id", 0))
            model = AIModelRepository.get_model_by_id(model_id)
            if model:
                self.write(json.dumps(model))
            else:
                self.write(json.dumps({"error": "模型不存在"}))
            return
        elif action == "add":
            name = self.get_body_argument("name", "")
            model_id = self.get_body_argument("model_id", "")
            api_key = self.get_body_argument("api_key", "")
            base_url = self.get_body_argument("base_url", "")
            temperature = float(self.get_body_argument("temperature", 0.7))
            max_tokens = int(self.get_body_argument("max_tokens", 4096))
            top_p = float(self.get_body_argument("top_p", 0.9))
            frequency_penalty = float(self.get_body_argument("frequency_penalty", 0.0))
            presence_penalty = float(self.get_body_argument("presence_penalty", 0.0))
            description = self.get_body_argument("description", "")
            provider = self.get_body_argument("provider", "openai")
            
            if AIModelRepository.create_model(name, model_id, api_key, base_url, temperature, max_tokens, top_p, frequency_penalty, presence_penalty, description, provider):
                self.write(json.dumps({"status": "success", "message": "模型添加成功"}))
            else:
                self.write(json.dumps({"status": "error", "message": "模型名称已存在"}))
        elif action == "edit":
            model_id = int(self.get_body_argument("id", 0))
            name = self.get_body_argument("name", "")
            model_id_str = self.get_body_argument("model_id", "")
            api_key = self.get_body_argument("api_key", "")
            base_url = self.get_body_argument("base_url", "")
            temperature = float(self.get_body_argument("temperature", 0.7))
            max_tokens = int(self.get_body_argument("max_tokens", 4096))
            top_p = float(self.get_body_argument("top_p", 0.9))
            frequency_penalty = float(self.get_body_argument("frequency_penalty", 0.0))
            presence_penalty = float(self.get_body_argument("presence_penalty", 0.0))
            description = self.get_body_argument("description", "")
            provider = self.get_body_argument("provider", "openai")
            
            if AIModelRepository.update_model(model_id, name, model_id_str, api_key, base_url, temperature, max_tokens, top_p, frequency_penalty, presence_penalty, description, provider):
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
    def post(self):
        model_id = int(self.get_body_argument("model_id", 0))
        prompt = self.get_body_argument("prompt", "")
        
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
                        })}\n\n")
                        self.flush()
            self.write(f"data: {json.dumps({
                'type': 'done',
                'content': full_content,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': prompt_tokens + completion_tokens
            })}\n\n")
            AIModelRepository.update_tokens(model_id, prompt_tokens, completion_tokens)
        except Exception as e:
            self.write(f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n")
        self.finish()


class AdminDashboardHandler(AdminBaseHandler):
    def get(self):
        self.render("admin/dashboard.html", title="数智大屏")


class AdminSentimentHandler(AdminBaseHandler):
    def get(self):
        self.render("admin/sentiment.html", title="舆情大屏")