import tornado.web

from app.models.admin import AdminRepository


class AdminBaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        admin = self.get_secure_cookie("admin")
        if not admin:
            return None
        return admin.decode("utf-8")


class AdminLoginHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("admin/login.html", title="管理员登录", error=None)

    def post(self):
        username = self.get_body_argument("username", "")
        password = self.get_body_argument("password", "")

        if AdminRepository.verify_admin(username, password):
            self.set_secure_cookie("admin", username)
            self.redirect("/admin/index")
        else:
            self.set_status(401)
            self.render("admin/login.html", title="管理员登录", error="用户名或密码不正确")


class AdminLogoutHandler(AdminBaseHandler):
    def post(self):
        self.clear_cookie("admin")
        self.redirect("/admin/login")


class AdminIndexHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/index.html", title="后台管理")


class AdminUserHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/users.html", title="用户管理")


class AdminFunctionHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/functions.html", title="功能管理")


class AdminMenuHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/menus.html", title="菜单管理")


class AdminRoleHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/roles.html", title="角色管理")


class AdminWatchHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/watch.html", title="瞭望管理")


class AdminDataHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/data.html", title="数据管理")


class AdminCollectionHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/collection.html", title="采集管理")


class AdminDigitalEmployeeHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/digital_employee.html", title="数字员工")


class AdminModelHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/model.html", title="模型引擎")


class AdminDashboardHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/dashboard.html", title="数智大屏")


class AdminSentimentHandler(AdminBaseHandler):
    def get(self):
        if not self.get_current_user():
            self.redirect("/admin/login")
            return
        self.render("admin/sentiment.html", title="舆情大屏")