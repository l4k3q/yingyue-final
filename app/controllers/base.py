"""
Controller公共基础类（BaseHandler）
在tornado中，
-每个URL对应一个RequestHandler(可以理解成是一个Controller)
-RequestHandler中 提供常用的请求和响应逻辑，同时支持重写生命周期内的方法
-get/post/put/delete...

本BaseHandler主要是提供统一的登陆状态获得逻辑，供其他Handler继承使用
"""

import tornado.web


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        username = self.get_secure_cookie("username")
        if not username:
            return None
        return username.decode("utf-8")