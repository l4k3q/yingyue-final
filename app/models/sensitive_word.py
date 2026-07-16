import re
import json
import time
import hashlib
from app.models.db import get_connection

_cache = {"entries": [], "loaded_at": 0}
CACHE_TTL = 300


# Common neutral Chinese bigrams that should NOT be used as match patterns
_STOP_BIGRAMS = {
    "购买", "销售", "服务", "使用", "方法", "如何", "什么", "怎么", "一个",
    "这个", "那个", "可以", "没有", "已经", "知道", "自己", "我们", "他们",
    "因为", "所以", "但是", "而且", "然后", "不过", "还是", "或者",
    "进行", "需要", "通过", "提供", "包括", "取得", "获得", "实现",
    "处理", "管理", "支持", "利用", "分析", "影响", "发生", "之间",
    "有关", "信息", "文件", "内容", "网站", "软件", "数据",
    "系统", "程序", "电话", "联系", "下载", "安装", "打开",
    "查看", "搜索", "选择", "设置", "关注", "注册", "登录",
    "安全", "什么", "这样", "部分", "全部", "以下",
    "电影", "视频", "图片", "广告", "新闻", "文章", "发布",
}


def _refresh_cache():
    now = time.time()
    if now - _cache["loaded_at"] < CACHE_TTL:
        return
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, word, category, severity, patterns FROM sensitive_words WHERE status=1 ORDER BY severity DESC"
        ).fetchall()
    entries = []
    for r in rows:
        d = dict(r)
        patterns = []
        try:
            patterns = json.loads(d.get("patterns", "") or "[]")
        except (json.JSONDecodeError, TypeError):
            patterns = []
        word = d["word"]
        # auto-generate 2-gram sub-patterns for 2-6 character words
        # filtering out common neutral bigrams to reduce false positives
        if 2 <= len(word) <= 6:
            for i in range(len(word) - 1):
                sub = word[i:i + 2]
                if sub not in _STOP_BIGRAMS and sub not in patterns:
                    patterns.append(sub)
        d["_patterns"] = patterns
        entries.append(d)
    _cache["entries"] = entries
    _cache["loaded_at"] = now


class SensitiveWordRepository:

    @staticmethod
    def get_words(page=1, page_size=20, keyword="", category=""):
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            conditions.append("word LIKE ?")
            params.append(f"%{keyword}%")
        if category:
            conditions.append("category=?")
            params.append(category)
        where = " AND ".join(conditions) if conditions else "1=1"
        with get_connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM sensitive_words WHERE {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM sensitive_words WHERE {where} ORDER BY severity DESC, id DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()
        return [dict(r) for r in rows], total

    @staticmethod
    def get_word_by_id(word_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sensitive_words WHERE id=?", (word_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create_word(word, category, severity, patterns=""):
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO sensitive_words (word, category, severity, patterns) VALUES (?,?,?,?)",
                    (word, category, severity, patterns),
                )
            _cache["loaded_at"] = 0
            return True
        except Exception:
            return False

    @staticmethod
    def update_word(word_id, word, category, severity, patterns=""):
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE sensitive_words SET word=?, category=?, severity=?, patterns=? WHERE id=?",
                    (word, category, severity, patterns, word_id),
                )
            _cache["loaded_at"] = 0
            return True
        except Exception:
            return False

    @staticmethod
    def delete_word(word_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM sensitive_words WHERE id=?", (word_id,))
        _cache["loaded_at"] = 0
        return True

    @staticmethod
    def toggle_status(word_id, status):
        with get_connection() as conn:
            conn.execute(
                "UPDATE sensitive_words SET status=? WHERE id=?", (status, word_id)
            )
        _cache["loaded_at"] = 0
        return True

    @staticmethod
    def batch_import(words_text):
        lines = [l.strip() for l in words_text.strip().split("\n") if l.strip()]
        added = 0
        skipped = 0
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            word = parts[0]
            category = parts[1] if len(parts) > 1 else "通用"
            try:
                severity = int(parts[2]) if len(parts) > 2 else 1
            except ValueError:
                severity = 1
            patterns = parts[3] if len(parts) > 3 else ""
            try:
                with get_connection() as conn:
                    conn.execute(
                        "INSERT INTO sensitive_words (word, category, severity, patterns) VALUES (?,?,?,?)",
                        (word, category, severity, patterns),
                    )
                added += 1
            except Exception:
                skipped += 1
        _cache["loaded_at"] = 0
        return added, skipped

    @staticmethod
    def get_categories():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM sensitive_words WHERE status=1 ORDER BY category"
            ).fetchall()
        return [r["category"] for r in rows]

    @staticmethod
    def scan(content):
        """Scan content for sensitive terms using multi-level fuzzy matching.
        Returns (is_safe, matched_words_list)."""
        if not content or not isinstance(content, str):
            return True, []
        _refresh_cache()
        entries = _cache["entries"]
        if not entries:
            return True, []
        matched = []
        seen_words = set()
        content_lower = content.lower()
        for entry in entries:
            word = entry["word"]
            if word in seen_words:
                continue
            hit = False
            # Level 1: direct whole-word match (case-insensitive)
            if word.lower() in content_lower:
                hit = True
            # Level 2: check auto-generated sub-patterns (2-gram strings only)
            if not hit:
                for pat in entry.get("_patterns", []):
                    if isinstance(pat, str) and len(pat) >= 2 and pat.lower() in content_lower:
                        hit = True
                        break
            # Level 3: check explicit proximity patterns from user-defined patterns field
            if not hit:
                extra_patterns = []
                try:
                    extra_patterns = json.loads(entry.get("patterns", "") or "[]")
                except (json.JSONDecodeError, TypeError):
                    extra_patterns = []
                for pp in extra_patterns:
                    if isinstance(pp, dict) and pp.get("type") == "proximity":
                        words = pp.get("words", [])
                        distance = pp.get("distance", 3)
                        if SensitiveWordRepository._check_proximity(content, words, distance):
                            hit = True
                            break
                    elif isinstance(pp, str):
                        if pp.lower() in content_lower:
                            hit = True
                            break
            if hit:
                seen_words.add(word)
                matched.append({
                    "word": word,
                    "category": entry["category"],
                    "severity": entry["severity"],
                })
        if matched:
            matched.sort(key=lambda x: x["severity"], reverse=True)
        return len(matched) == 0, matched

    @staticmethod
    def _check_proximity(content, words, max_distance):
        """Check if all given words appear within max_distance characters of each other."""
        positions = []
        for w in words:
            pos = content.find(w)
            if pos == -1:
                return False
            positions.append(pos)
        positions.sort()
        return (positions[-1] - positions[0]) <= max_distance + max(len(w) for w in words)

    @staticmethod
    def highest_risk_level(matched_words):
        if not matched_words:
            return 0
        return max(w["severity"] for w in matched_words)

    @staticmethod
    def create_scan_log(target_type, target_id, content, is_safe, matched_count):
        content_hash = hashlib.md5(
            (content or "").encode("utf-8", errors="ignore")
        ).hexdigest()
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO content_scan_logs (target_type, target_id, content_hash, is_safe, matched_count) VALUES (?,?,?,?,?)",
                    (target_type, target_id, content_hash, 1 if is_safe else 0, matched_count),
                )
        except Exception:
            pass

    @staticmethod
    def get_scan_stats():
        with get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM content_scan_logs"
            ).fetchone()[0]
            unsafe = conn.execute(
                "SELECT COUNT(*) FROM content_scan_logs WHERE is_safe=0"
            ).fetchone()[0]
        return {"total": total, "unsafe": unsafe}
