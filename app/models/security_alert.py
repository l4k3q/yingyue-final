import json
from app.models.db import get_connection


class SecurityAlertRepository:

    @staticmethod
    def get_alerts(page=1, page_size=20, keyword="", source_type="", risk_level=0, status_filter=-1):
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            conditions.append("(content_snippet LIKE ? OR username LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if source_type:
            conditions.append("source_type=?")
            params.append(source_type)
        if risk_level > 0:
            conditions.append("risk_level=?")
            params.append(risk_level)
        if status_filter >= 0:
            conditions.append("status=?")
            params.append(status_filter)
        where = " AND ".join(conditions) if conditions else "1=1"
        with get_connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM security_alerts WHERE {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM security_alerts WHERE {where} ORDER BY risk_level DESC, id DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()
        alerts = []
        for r in rows:
            d = dict(r)
            try:
                d["matched_words"] = json.loads(d["matched_words"])
            except (json.JSONDecodeError, TypeError):
                d["matched_words"] = []
            alerts.append(d)
        return alerts, total

    @staticmethod
    def get_alert_by_id(alert_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM security_alerts WHERE id=?", (alert_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["matched_words"] = json.loads(d["matched_words"])
        except (json.JSONDecodeError, TypeError):
            d["matched_words"] = []
        return d

    @staticmethod
    def create_alert(source_type, source_id, user_id, username, matched_words, content_snippet, risk_level):
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO security_alerts (source_type, source_id, user_id, username, matched_words, content_snippet, risk_level)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    source_type, source_id, user_id, username,
                    json.dumps(matched_words, ensure_ascii=False),
                    content_snippet[:500] if content_snippet else "",
                    risk_level,
                ),
            )
            return cursor.lastrowid

    @staticmethod
    def update_alert_status(alert_id, status, handler_id=0):
        with get_connection() as conn:
            conn.execute(
                "UPDATE security_alerts SET status=?, handler_id=?, handled_at=datetime('now','localtime') WHERE id=?",
                (status, handler_id, alert_id),
            )
        return True

    @staticmethod
    def update_ai_analysis(alert_id, analysis):
        with get_connection() as conn:
            conn.execute(
                "UPDATE security_alerts SET ai_analysis=? WHERE id=?",
                (analysis, alert_id),
            )
        return True

    @staticmethod
    def get_stats():
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM security_alerts").fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE status=0"
            ).fetchone()[0]
            handled = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE status=1"
            ).fetchone()[0]
            high_risk = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE risk_level=3 AND status=0"
            ).fetchone()[0]
            ignored = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE status=2"
            ).fetchone()[0]
        return {
            "total": total,
            "pending": pending,
            "handled": handled,
            "high_risk": high_risk,
            "ignored": ignored,
        }

    @staticmethod
    def get_trend(days=7):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT date(created_at) as dt, COUNT(*) as cnt
                   FROM security_alerts
                   WHERE created_at >= datetime('now','localtime','-' || ? || ' days')
                   GROUP BY dt ORDER BY dt""",
                (days,),
            ).fetchall()
        return [{"date": r["dt"], "count": r["cnt"]} for r in rows]

    @staticmethod
    def get_source_distribution():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT source_type, COUNT(*) as cnt FROM security_alerts GROUP BY source_type"
            ).fetchall()
        return [{"name": r["source_type"], "value": r["cnt"]} for r in rows]

    @staticmethod
    def get_top_matched_words(limit=10):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT matched_words FROM security_alerts WHERE matched_words != ''"
            ).fetchall()
        word_count = {}
        for r in rows:
            try:
                words = json.loads(r["matched_words"])
                for w in words:
                    key = w.get("word", "")
                    if key:
                        word_count[key] = word_count.get(key, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{"word": w, "count": c} for w, c in sorted_words]

    @staticmethod
    def get_risk_level_distribution():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT risk_level, COUNT(*) as cnt FROM security_alerts GROUP BY risk_level"
            ).fetchall()
        labels = {1: "低风险", 2: "中风险", 3: "高风险"}
        return [{"name": labels.get(r["risk_level"], "未知"), "value": r["cnt"]} for r in rows]

    @staticmethod
    def get_recent_alerts(limit=5):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM security_alerts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        alerts = []
        for r in rows:
            d = dict(r)
            try:
                d["matched_words"] = json.loads(d["matched_words"])
            except (json.JSONDecodeError, TypeError):
                d["matched_words"] = []
            alerts.append(d)
        return alerts


class SecurityAlertService:

    @staticmethod
    def analyze_risk(alert_id):
        """Use AI to analyze a specific alert's risk."""
        from app.models.model import AIModelRepository, AIModelService

        alert = SecurityAlertRepository.get_alert_by_id(alert_id)
        if not alert:
            return "预警记录不存在"

        model = AIModelRepository.get_default_model()
        if not model:
            return "无可用AI模型，无法进行风险分析"

        content = alert.get("content_snippet", "")
        matched = alert.get("matched_words", [])
        matched_str = ", ".join(
            [f"{w.get('word', '')}({w.get('category', '')}, 严重级别:{w.get('severity', 0)})" for w in matched]
        ) if matched else "无"

        system_prompt = """你是一个专业的内容安全风险分析师。请根据以下信息，分析该预警记录的风险情况。
请从以下几个方面进行分析：
1. 风险等级评估：结合实际内容评估真实风险等级（低/中/高）
2. 风险类型判断：判断内容的潜在风险类型
3. 潜在影响分析：分析可能造成的影响
4. 处理建议：给出具体的处理建议

请用简洁的专业语言回答，控制在300字以内。"""

        user_prompt = f"""请分析以下安全预警：

内容来源: {alert.get('source_type', '未知')}
命中敏感词: {matched_str}
内容片段: {content}
综合风险级别: {alert.get('risk_level', 1)}级"""

        try:
            result = AIModelService.chat_completion(
                model,
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
            )
            analysis = result["choices"][0]["message"]["content"]
            SecurityAlertRepository.update_ai_analysis(alert_id, analysis)
            return analysis
        except Exception as e:
            return f"AI分析失败: {str(e)}"

    @staticmethod
    def analyze_overall_trend():
        """Use AI to analyze overall risk trend from recent alerts."""
        from app.models.model import AIModelRepository, AIModelService

        model = AIModelRepository.get_default_model()
        if not model:
            return "无可用AI模型，无法进行综合分析"

        stats = SecurityAlertRepository.get_stats()
        trend = SecurityAlertRepository.get_trend(7)
        source_dist = SecurityAlertRepository.get_source_distribution()
        risk_dist = SecurityAlertRepository.get_risk_level_distribution()

        trend_desc = ", ".join([f"{t['date']}: {t['count']}条" for t in trend])
        source_desc = ", ".join([f"{s['name']}: {s['value']}条" for s in source_dist])
        risk_desc = ", ".join([f"{r['name']}: {r['value']}条" for r in risk_dist])

        system_prompt = """你是一个专业的舆情安全分析师。请根据提供的统计数据，生成一份简洁的舆情安全态势分析报告。
报告应包含：
1. 整体态势：当前舆情安全总体情况
2. 趋势分析：近7天预警趋势及值得关注的信号
3. 风险分布：不同来源和风险等级的分布特征
4. 应对建议：基于数据的实际建议

请用专业、简洁的语言，控制在400字以内。"""

        user_prompt = f"""请分析以下舆情安全数据：

总预警数: {stats['total']}
待处理: {stats['pending']}
已处理: {stats['handled']}
高风险预警: {stats['high_risk']}

近7天趋势: {trend_desc}
来源分布: {source_desc}
风险等级分布: {risk_desc}"""

        try:
            result = AIModelService.chat_completion(
                model,
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
            )
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"AI综合分析失败: {str(e)}"
