import json
from datetime import datetime, timedelta

import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.db import get_connection
from app.models.watch import WatchSourceRepository, WatchRecordRepository
from app.models.warehouse import DataWarehouseRepository, DeepCollectTaskRepository


class ScreenAPIBaseHandler(AdminBaseHandler):
    """大屏专用接口基类，未登录或无大屏权限时返回 JSON，不重定向页面。"""

    def prepare(self):
        if not self.get_current_user():
            self.set_status(401)
            self.write_json({"success": False, "error": "未登录"})
            self.finish()
            return
        if not self.has_function_permission("/admin/screen"):
            self.set_status(403)
            self.write_json({"success": False, "error": "无大屏访问权限"})
            self.finish()
            return

    def write_json(self, data):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(data, ensure_ascii=False))


# ========== 分类与地理映射规则 ==========

CATEGORY_RULES = [
    ("政务", ["政府", "政策", "政务", "国家", "部委", "国务院", "两会", "改革"]),
    ("财经", ["经济", "财经", "金融", "市场", "股市", "投资", "消费", "GDP", "贸易"]),
    ("科技", ["科技", "人工智能", "AI", "大模型", "5G", "芯片", "云计算", "物联网", "区块链", "数字经济", "新能源", "自动驾驶", "元宇宙", "工业互联网"]),
    ("民生", ["民生", "教育", "医疗", "住房", "就业", "养老", "社保", "交通", "环境", "食品安全"]),
    ("国际", ["国际", "全球", "外交", "美国", "欧洲", "俄罗斯", "中东", "亚太", "联合国"]),
]

CITY_COORDS = {
    "北京": [116.40, 39.90],
    "上海": [121.47, 31.23],
    "广州": [113.26, 23.13],
    "深圳": [114.17, 22.32],
    "杭州": [120.15, 30.28],
    "西安": [108.93, 34.34],
    "重庆": [106.55, 29.56],
    "成都": [104.06, 30.67],
    "天津": [117.20, 39.08],
    "武汉": [114.30, 30.59],
    "南京": [118.78, 32.07],
    "苏州": [120.58, 31.30],
}

KEYWORD_CITY_RULES = {
    "人工智能": "北京", "AI": "北京", "大模型": "北京",
    "数字经济": "上海", "金融": "上海", "股市": "上海",
    "智慧城市": "深圳", "5G": "深圳", "物联网": "深圳",
    "碳中和": "成都", "新能源": "成都", "环境": "成都",
    "区块链": "杭州", "云计算": "杭州", "大数据": "杭州",
    "工业互联网": "天津", "智能制造": "天津",
    "自动驾驶": "武汉", "芯片": "南京", "元宇宙": "苏州",
}


def classify_text(text):
    """根据关键词规则对文本进行资讯分类。"""
    if not text:
        return "其他"
    text = text.lower()
    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.lower() in text:
                return category
    return "其他"


def keyword_to_city(keyword, seed=0):
    """将关键词映射到城市坐标，未命中规则时按 seed 轮询 fallback。"""
    if keyword:
        for kw, city in KEYWORD_CITY_RULES.items():
            if kw in keyword:
                return city
    cities = list(CITY_COORDS.keys())
    return cities[seed % len(cities)]


# ========== 接口实现 ==========

class ScreenSourcesHandler(ScreenAPIBaseHandler):
    """① 多瞭望源采集总量接口：柱状图 + 资讯占比饼图。"""

    def get(self):
        with get_connection() as conn:
            # 按来源统计入库资讯量
            cursor = conn.execute(
                """SELECT source, COUNT(*) as value
                   FROM data_warehouse
                   WHERE status=1 AND source IS NOT NULL AND source != ''
                   GROUP BY source
                   ORDER BY value DESC"""
            )
            source_rows = [dict(r) for r in cursor.fetchall()]

            # 按关键词分类统计资讯占比
            cursor = conn.execute(
                """SELECT keyword
                   FROM data_warehouse
                   WHERE status=1"""
            )
            category_counts = {}
            for row in cursor.fetchall():
                cat = classify_text(row["keyword"])
                category_counts[cat] = category_counts.get(cat, 0) + 1

        news_types = [
            {"name": name, "value": value}
            for name, value in sorted(category_counts.items(), key=lambda x: -x[1])
        ]

        self.write_json({
            "success": True,
            "sources": source_rows,
            "news_types": news_types
        })


class ScreenKeywordsHandler(ScreenAPIBaseHandler):
    """② 热点关键词统计接口：词云。"""

    def get(self):
        limit = int(self.get_query_argument("limit", 30))
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT keyword as name, COUNT(*) as value
                   FROM data_warehouse
                   WHERE status=1 AND keyword IS NOT NULL AND keyword != ''
                   GROUP BY keyword
                   ORDER BY value DESC
                   LIMIT ?""",
                (limit,)
            )
            words = [dict(r) for r in cursor.fetchall()]

        self.write_json({
            "success": True,
            "words": words
        })


class ScreenGeoHandler(ScreenAPIBaseHandler):
    """③ 资讯地理点位接口：3D 地球城市分布 + 飞线。"""

    def get(self):
        limit = int(self.get_query_argument("limit", 200))
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, keyword, title
                   FROM data_warehouse
                   WHERE status=1
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (limit,)
            )
            rows = [dict(r) for r in cursor.fetchall()]

        city_counts = {}
        for idx, row in enumerate(rows):
            text = row.get("keyword") or row.get("title") or ""
            city = keyword_to_city(text, seed=row.get("id", idx))
            city_counts[city] = city_counts.get(city, 0) + 1

        # 取前 8 个城市生成点位与飞线
        top_cities = sorted(city_counts.items(), key=lambda x: -x[1])[:8]
        points = []
        for city, count in top_cities:
            coord = CITY_COORDS.get(city, [116.40, 39.90])
            points.append({
                "name": city,
                "value": coord + [count]
            })

        # 以第一个城市为中心，向其他城市生成飞线
        lines = []
        if len(points) > 1:
            center = points[0]["value"][:2]
            for point in points[1:]:
                target = point["value"][:2]
                lines.append({
                    "from": center,
                    "to": target,
                    "from_name": points[0]["name"],
                    "to_name": point["name"]
                })

        self.write_json({
            "success": True,
            "points": points,
            "lines": lines
        })


class ScreenRealtimeHandler(ScreenAPIBaseHandler):
    """④ 实时运营数据接口：总量、在线源、深度任务、实时日志。"""

    def get(self):
        log_limit = int(self.get_query_argument("log_limit", 10))
        today = datetime.now().strftime("%Y-%m-%d")

        with get_connection() as conn:
            # 总入库数
            total_records = conn.execute(
                "SELECT COUNT(*) FROM data_warehouse WHERE status=1"
            ).fetchone()[0]

            # 今日入库数（按 created_at 日期前缀匹配）
            today_records = conn.execute(
                "SELECT COUNT(*) FROM data_warehouse WHERE status=1 AND created_at LIKE ?",
                (f"{today}%",)
            ).fetchone()[0]

            # 深度采集任务数
            deep_tasks = conn.execute(
                "SELECT COUNT(*) FROM deep_collect_tasks"
            ).fetchone()[0]

        # 在线/启用采集源数
        online_sources = len(WatchSourceRepository.get_enabled_sources())

        # 实时日志：合并 watch_records 与 deep_collect_tasks
        logs = self._build_logs(log_limit)

        self.write_json({
            "success": True,
            "total_records": total_records,
            "today_records": today_records,
            "online_sources": online_sources,
            "deep_tasks": deep_tasks,
            "logs": logs
        })

    def _build_logs(self, limit):
        logs = []
        today = datetime.now()

        with get_connection() as conn:
            # 最近采集记录
            cursor = conn.execute(
                """SELECT r.id, r.source_id, s.name as source_name, r.keyword, r.status, r.created_at
                   FROM watch_records r
                   LEFT JOIN watch_sources s ON r.source_id = s.id
                   ORDER BY r.created_at DESC
                   LIMIT ?""",
                (limit,)
            )
            for row in cursor.fetchall():
                row = dict(row)
                source = row.get("source_name") or "未知来源"
                status = "success" if row.get("status") == 1 else "fail"
                text = f"采集关键词“{row.get('keyword', '')}”相关资讯"
                logs.append({
                    "time": row.get("created_at", ""),
                    "source": source,
                    "text": text,
                    "status": status
                })

            # 最近深度采集任务
            cursor = conn.execute(
                """SELECT t.id, t.record_id, t.step, t.log, t.status, t.created_at, d.title
                   FROM deep_collect_tasks t
                   LEFT JOIN data_warehouse d ON t.record_id = d.id
                   ORDER BY t.created_at DESC
                   LIMIT ?""",
                (limit,)
            )
            for row in cursor.fetchall():
                row = dict(row)
                status_map = {2: "success", 3: "fail"}
                status = status_map.get(row.get("status"), "success")
                title = row.get("title") or f"记录#{row.get('record_id', '')}"
                logs.append({
                    "time": row.get("created_at", ""),
                    "source": "深度采集",
                    "text": f"{row.get('step', '执行深度采集')}：{title}",
                    "status": status
                })

        # 按时间倒序合并并截取
        logs.sort(key=lambda x: x["time"], reverse=True)
        logs = logs[:limit]

        # 为无时间的数据补充兜底时间
        for idx, log in enumerate(logs):
            if not log.get("time"):
                t = today - timedelta(minutes=idx * 2)
                log["time"] = t.strftime("%Y-%m-%d %H:%M:%S")
        return logs
