import tornado.web

from app.controllers.base import BaseHandler
from app.models.user import UserRepository

class LoginHandler(BaseHandler):
    def get(self):
        self.render("login.html",title="用户登录",error=None)

    def post(self):
        username = self.get_body_argument("username","")
        password = self.get_body_argument("password","")
        if not username or not password:
            self.set_status(400)
            return self.render("login.html",title="用户登录",error="请输入用户名和密码")

        if not UserRepository.verify_user(username,password):
            self.set_status(401)
            return self.render("login.html",title="用户登录",error="用户名或密码不正确")

        self.set_secure_cookie("username",username)
        self.redirect("/index")

class LogoutHandler(BaseHandler):
    def post(self):
        self.clear_cookie("username")
        self.redirect("/")


class RegisterHandler(BaseHandler):
    def get(self):
        self.render("register.html", title="用户注册", error=None)

    def post(self):
        username = self.get_body_argument("username", "")
        password = self.get_body_argument("password", "")
        confirm_password = self.get_body_argument("confirm_password", "")

        if not username or not password:
            self.set_status(400)
            return self.render("register.html", title="用户注册", error="请输入用户名和密码")

        if password != confirm_password:
            self.set_status(400)
            return self.render("register.html", title="用户注册", error="两次输入的密码不一致")

        if not UserRepository.create_user(username, password):
            self.set_status(400)
            return self.render("register.html", title="用户注册", error="用户名已存在")

        self.redirect("/")
