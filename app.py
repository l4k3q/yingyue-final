import os
import tornado.ioloop
import tornado.web
from tornado.httpserver import HTTPServer

from app.controllers.auth import LoginHandler, LogoutHandler, RegisterHandler
from app.controllers.home import IndexHandler
from app.controllers.chat import ChatWebSocketHandler, ConversationAPIHandler, DigitalEmployeeAPIHandler
from app.controllers.report import ReportHandler
from app.controllers.history import HistoryHandler
from app.controllers.export import ExportHandler
from app.controllers.admin import (
    AdminLoginHandler, AdminLogoutHandler, AdminIndexHandler,
    AdminUserHandler, AdminFunctionHandler, AdminMenuHandler,
    AdminRoleHandler, AdminRoleFunctionsHandler, AdminWatchHandler,
    AdminWatchSourceHandler, AdminDataHandler, AdminCollectionHandler,
    AdminDigitalEmployeeHandler, AdminModelHandler, AdminModelTestHandler,
    AdminDashboardHandler, AdminScreenHandler, AdminSentimentHandler,
    AdminNoPermissionHandler
)
from app.controllers.screen_api import (
    ScreenSourcesHandler, ScreenKeywordsHandler,
    ScreenGeoHandler, ScreenRealtimeHandler
)
from app.models.db import init_db


def webapp():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    settings = dict(
        template_path=os.path.join(base_dir, "app", "templates"),
        static_path=os.path.join(base_dir, "app", "static"),
        cookie_secret="datafinderagentos-token",
        login_url="/",
        xsrf_cookies=True,
        debug=True,
        autoreload=True,
    )
    return tornado.web.Application([
        # ========== 用户侧（前台）路由 ==========
        (r"/", LoginHandler),
        (r"/logout", LogoutHandler),
        (r"/index", IndexHandler),
        (r"/register", RegisterHandler),
        
        (r"/report", ReportHandler),
        (r"/history", HistoryHandler),
        (r"/export", ExportHandler),

        # ========== API 路由 ==========
        (r"/api/conversations", ConversationAPIHandler),
        (r"/api/digital_employees", DigitalEmployeeAPIHandler),

        # ========== WebSocket 路由 ==========
        (r"/ws/chat", ChatWebSocketHandler),

        # ========== 管理侧（后台）路由 ==========
        (r"/admin/login", AdminLoginHandler),
        (r"/admin/logout", AdminLogoutHandler),
        (r"/admin/index", AdminIndexHandler),
        (r"/admin/users", AdminUserHandler),
        (r"/admin/functions", AdminFunctionHandler),
        (r"/admin/menus", AdminMenuHandler),
        (r"/admin/roles", AdminRoleHandler),
        (r"/admin/roles/functions", AdminRoleFunctionsHandler),
        (r"/admin/watch", AdminWatchHandler),
        (r"/admin/watch/source", AdminWatchSourceHandler),
        (r"/admin/data", AdminDataHandler),
        (r"/admin/collection", AdminCollectionHandler),
        (r"/admin/digital_employee", AdminDigitalEmployeeHandler),
        (r"/admin/model", AdminModelHandler),
        (r"/admin/model/test", AdminModelTestHandler),
        (r"/admin/dashboard", AdminDashboardHandler),
        (r"/admin/screen", AdminScreenHandler),
        (r"/admin/sentiment", AdminSentimentHandler),
        (r"/admin/no_permission", AdminNoPermissionHandler),

        # ========== 大屏统计 API 路由 ==========
        (r"/api/screen/sources", ScreenSourcesHandler),
        (r"/api/screen/keywords", ScreenKeywordsHandler),
        (r"/api/screen/geo", ScreenGeoHandler),
        (r"/api/screen/realtime", ScreenRealtimeHandler),
    ],
        **settings
    )


if __name__ == '__main__':
    init_db()
    webapp = webapp()
    server = HTTPServer(webapp)
    server.listen(10010)
    print("Server Started: http://localhost:10010/", flush=True)
    print("Admin: http://localhost:10010/admin/login", flush=True)
    tornado.ioloop.IOLoop.current().start()