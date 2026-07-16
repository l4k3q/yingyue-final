import tornado.web

from app.controllers.base import BaseHandler


class HistoryHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.redirect("/index")
