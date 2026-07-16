import json
import tornado.web
from app.models.security_alert import SecurityAlertRepository, SecurityAlertService
from app.models.sensitive_word import SensitiveWordRepository


class SentimentAPIHandler(tornado.web.RequestHandler):

    def prepare(self):
        admin = self.get_secure_cookie("admin")
        if not admin:
            self.set_status(401)
            self.finish(json.dumps({"status": "error", "message": "未登录"}))
            return
        self.set_header("Content-Type", "application/json")

    def get(self):
        action = self.get_query_argument("action", "stats")

        if action == "stats":
            alert_stats = SecurityAlertRepository.get_stats()
            scan_stats = SensitiveWordRepository.get_scan_stats()
            self.write(json.dumps({
                "status": "success",
                "data": {
                    "alerts": alert_stats,
                    "scans": scan_stats,
                },
            }, ensure_ascii=False))

        elif action == "trend":
            days = int(self.get_query_argument("days", "7"))
            data = SecurityAlertRepository.get_trend(days)
            self.write(json.dumps({"status": "success", "data": data}, ensure_ascii=False))

        elif action == "source_distribution":
            data = SecurityAlertRepository.get_source_distribution()
            self.write(json.dumps({"status": "success", "data": data}, ensure_ascii=False))

        elif action == "risk_distribution":
            data = SecurityAlertRepository.get_risk_level_distribution()
            self.write(json.dumps({"status": "success", "data": data}, ensure_ascii=False))

        elif action == "top_words":
            limit = int(self.get_query_argument("limit", "10"))
            data = SecurityAlertRepository.get_top_matched_words(limit)
            self.write(json.dumps({"status": "success", "data": data}, ensure_ascii=False))

        elif action == "recent_alerts":
            limit = int(self.get_query_argument("limit", "5"))
            data = SecurityAlertRepository.get_recent_alerts(limit)
            self.write(json.dumps({"status": "success", "data": data}, ensure_ascii=False))

        elif action == "ai_overall":
            analysis = SecurityAlertService.analyze_overall_trend()
            self.write(json.dumps({"status": "success", "data": analysis}, ensure_ascii=False))

        elif action == "ai_analyze_alert":
            alert_id = int(self.get_query_argument("alert_id", "0"))
            if alert_id <= 0:
                self.write(json.dumps({"status": "error", "message": "无效的预警ID"}, ensure_ascii=False))
                return
            analysis = SecurityAlertService.analyze_risk(alert_id)
            self.write(json.dumps({"status": "success", "data": analysis}, ensure_ascii=False))

        else:
            self.write(json.dumps({"status": "error", "message": "未知操作"}, ensure_ascii=False))
