import json
import tornado.web
import tornado.websocket

from app.controllers.base import BaseHandler


class ChatHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        username = self.current_user
        self.render("chat.html", title="智能对话", username=username)


class ChatWebSocketHandler(BaseHandler, tornado.websocket.WebSocketHandler):
    def open(self):
        username = self.get_current_user()
        if not username:
            self.close(code=401, reason="未登录")
            return
        self.username = username

    def on_message(self, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            msg_data = data.get("data")

            if msg_type == "message":
                self.handle_message(msg_data)
            elif msg_type == "ping":
                self.write_message({"type": "pong"})
        except json.JSONDecodeError:
            self.write_message({"type": "error", "data": "无效的消息格式"})

    def handle_message(self, content):
        self.write_message({"type": "stream", "data": "正在处理您的请求..."})
        self.write_message({"type": "done"})

    def on_close(self):
        pass

    def check_origin(self, origin):
        return True