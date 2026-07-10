import tornado.web

from app.controllers.base import BaseHandler


class HistoryHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        username = self.current_user
        self.render("history.html", title="历史记录", username=username)