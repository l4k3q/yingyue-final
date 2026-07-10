import tornado.web

from app.controllers.base import BaseHandler


class ExportHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.set_header("Content-Type", "application/octet-stream")
        self.set_header("Content-Disposition", "attachment; filename=report.pdf")
        self.write(b"PDF report content")