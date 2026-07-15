import json
import re
import os

from app.models.db import get_connection
from app.models.model import AIModelRepository, AIModelService


class DBQueryService:
    ALLOWED_TABLES = [
        "users",
        "watch_sources",
        "watch_records",
        "data_warehouse",
        "digital_employees",
        "ai_models",
        "conversations",
        "deep_collect_tasks"
    ]
    
    PREDEFINED_QUERIES = {
        "用户总数": "SELECT COUNT(*) as user_count FROM users WHERE status=1",
        "用户列表": "SELECT id, username, role_id, status, created_at FROM users WHERE status=1 LIMIT 20",
        "活跃用户数": "SELECT COUNT(*) as active_count FROM users WHERE status=1",
        "用户注册趋势": "SELECT DATE(created_at) as date, COUNT(*) as count FROM users WHERE status=1 GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 30",
        "角色分布": "SELECT role_id, COUNT(*) as count FROM users WHERE status=1 GROUP BY role_id",
        
        "数字员工总数": "SELECT COUNT(*) as employee_count FROM digital_employees WHERE status=1",
        "数字员工列表": "SELECT id, name, code_name, type, status, description, created_at FROM digital_employees WHERE status=1",
        "数字员工类型统计": "SELECT type, COUNT(*) as count FROM digital_employees WHERE status=1 GROUP BY type",
        "数字员工启用状态": "SELECT status, COUNT(*) as count FROM digital_employees GROUP BY status",
        
        "模型总数": "SELECT COUNT(*) as model_count FROM ai_models WHERE status=1",
        "模型列表": "SELECT id, name, model_id, provider, is_default, status FROM ai_models",
        "模型提供商统计": "SELECT provider, COUNT(*) as count FROM ai_models WHERE status=1 GROUP BY provider",
        "默认模型": "SELECT id, name, model_id FROM ai_models WHERE is_default=1 AND status=1",
        
        "采集源总数": "SELECT COUNT(*) as source_count FROM watch_sources WHERE status=1",
        "采集源列表": "SELECT id, name, url, status, description FROM watch_sources WHERE status=1",
        "采集源状态统计": "SELECT status, COUNT(*) as count FROM watch_sources GROUP BY status",
        "采集记录总数": "SELECT COUNT(*) as record_count FROM watch_records WHERE status=1",
        "采集记录趋势": "SELECT DATE(created_at) as date, COUNT(*) as count FROM watch_records WHERE status=1 GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 30",
        
        "数据仓库总数": "SELECT COUNT(*) as record_count FROM data_warehouse WHERE status=1",
        "数据仓库列表": "SELECT id, title, summary, source, is_deep_collected, created_at FROM data_warehouse WHERE status=1 LIMIT 20",
        "深度采集统计": "SELECT is_deep_collected, COUNT(*) as count FROM data_warehouse WHERE status=1 GROUP BY is_deep_collected",
        "数据来源统计": "SELECT source, COUNT(*) as count FROM data_warehouse WHERE status=1 GROUP BY source",
        "最近采集的数据": "SELECT id, title, summary, source, created_at FROM data_warehouse WHERE status=1 ORDER BY created_at DESC LIMIT 20",
        
        "对话记录总数": "SELECT COUNT(*) as conversation_count FROM conversations WHERE status=1",
        "对话记录趋势": "SELECT DATE(created_at) as date, COUNT(*) as count FROM conversations WHERE status=1 GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 30",
        "用户对话统计": "SELECT user_id, COUNT(*) as count FROM conversations WHERE status=1 GROUP BY user_id ORDER BY count DESC LIMIT 10",
        
        "深度采集任务总数": "SELECT COUNT(*) as task_count FROM deep_collect_tasks",
        "任务状态统计": "SELECT status, COUNT(*) as count FROM deep_collect_tasks GROUP BY status",
        "任务进度统计": "SELECT progress, COUNT(*) as count FROM deep_collect_tasks GROUP BY progress",
        
        "系统概览": "SELECT '用户' as type, COUNT(*) as value FROM users WHERE status=1 UNION ALL SELECT '数字员工', COUNT(*) FROM digital_employees WHERE status=1 UNION ALL SELECT '模型', COUNT(*) FROM ai_models WHERE status=1 UNION ALL SELECT '采集源', COUNT(*) FROM watch_sources WHERE status=1 UNION ALL SELECT '数据仓库', COUNT(*) FROM data_warehouse WHERE status=1 UNION ALL SELECT '对话', COUNT(*) FROM conversations WHERE status=1"
    }

    @staticmethod
    def get_schema() -> str:
        tables_info = []
        
        table_descriptions = {
            "users": "用户表，存储用户账号信息",
            "watch_sources": "瞭望采集源表，存储采集源配置",
            "watch_records": "瞭望采集记录表，存储采集记录",
            "data_warehouse": "数据仓库表，存储采集到的数据（包括深度采集的数据）",
            "digital_employees": "数字员工表，存储数字员工配置",
            "ai_models": "AI模型表，存储模型配置",
            "conversations": "对话记录表，存储用户对话历史",
            "deep_collect_tasks": "深度采集任务表，存储深度采集任务状态"
        }
        
        with get_connection() as conn:
            for table_name in DBQueryService.ALLOWED_TABLES:
                try:
                    cursor = conn.execute(f"PRAGMA table_info({table_name})")
                    columns = []
                    for col in cursor.fetchall():
                        columns.append({
                            "name": col[1],
                            "type": col[2],
                            "not_null": bool(col[3]),
                            "pk": bool(col[5])
                        })
                    
                    tables_info.append({
                        "table_name": table_name,
                        "description": table_descriptions.get(table_name, ""),
                        "columns": columns
                    })
                except Exception:
                    continue
        
        schema_str = "数据库表结构信息：\n\n"
        for table in tables_info:
            schema_str += f"表名：{table['table_name']}\n"
            schema_str += f"描述：{table['description']}\n"
            schema_str += "字段：\n"
            for col in table["columns"]:
                schema_str += f"  - {col['name']} ({col['type']})"
                if col["pk"]:
                    schema_str += " [主键]"
                if col["not_null"]:
                    schema_str += " [必填]"
                schema_str += "\n"
            schema_str += "\n"
        
        return schema_str

    @staticmethod
    def validate_sql(sql: str) -> bool:
        sql_upper = sql.strip().upper()
        
        if not sql_upper.startswith("SELECT"):
            return False
        
        dangerous_patterns = [
            r'\bINSERT\b',
            r'\bUPDATE\b',
            r'\bDELETE\b',
            r'\bDROP\b',
            r'\bCREATE\b',
            r'\bALTER\b',
            r'\bTRUNCATE\b',
            r'\bEXEC\b',
            r'\bEXECUTE\b',
            r';\s*SELECT',
            r';\s*INSERT',
            r';\s*UPDATE',
            r';\s*DELETE'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sql_upper):
                return False
        
        return True

    @staticmethod
    def generate_sql(question: str) -> str:
        model = AIModelRepository.get_default_model()
        if not model:
            return ""

        schema = DBQueryService.get_schema()
        
        system_prompt = """你是一个专业的SQL生成助手。请根据用户的问题和提供的数据库表结构，生成高质量的SQL查询语句。

数据库表结构：
{schema}

注意事项：
1. 只允许生成SELECT语句，禁止生成INSERT、UPDATE、DELETE、DROP、CREATE等修改数据的语句
2. SQL必须是针对SQLite数据库的语法
3. 只使用提供的表和字段，不要猜测不存在的表或字段
4. 优先查询data_warehouse表（数据仓库），这是最重要的数据来源
5. 对于日期字段，可以使用DATE()、datetime('now')等函数
6. 对于统计需求，可以使用COUNT、SUM、AVG、MAX、MIN等聚合函数
7. 支持GROUP BY进行分组统计
8. 支持ORDER BY进行排序
9. 支持LIMIT限制返回数量
10. 支持WHERE条件筛选
11. 如果需要进行数据关系分析，可以使用JOIN关联多个表
12. 如果无法生成安全的SQL，请返回空字符串

分析用户问题并生成最合适的SQL：
- 如果用户询问统计信息，使用COUNT、SUM等聚合函数
- 如果用户询问趋势，按日期分组
- 如果用户询问分布，按分类字段分组
- 如果用户询问排名，使用ORDER BY和LIMIT
- 如果用户询问详情，返回具体字段信息

请只返回SQL语句，不要包含任何解释或额外内容。""".format(schema=schema)

        user_prompt = f"用户问题：<user_input>{question}</user_input>\n\n请生成相应的SQL查询语句："

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            result = AIModelService.chat_completion(model, messages, stream=False)
            if "choices" in result and result["choices"]:
                sql = result["choices"][0]["message"]["content"].strip()
                
                sql_match = re.search(r'SELECT[\s\S]*?(?=\n\n|$)', sql, re.IGNORECASE)
                if sql_match:
                    sql = sql_match.group(0).strip()
                
                if DBQueryService.validate_sql(sql):
                    return sql
        except Exception:
            pass
        
        return ""

    @staticmethod
    def execute_query(sql: str) -> dict:
        if not sql or not sql.strip():
            return {"success": False, "error": "SQL语句为空"}
        
        if not DBQueryService.validate_sql(sql):
            return {"success": False, "error": "SQL语句不安全"}
        
        try:
            with get_connection() as conn:
                cursor = conn.execute(sql)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    results.append(dict(row))
                
                return {
                    "success": True,
                    "columns": columns,
                    "results": results,
                    "count": len(results),
                    "sql": sql
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def query(question: str) -> dict:
        for key, sql in DBQueryService.PREDEFINED_QUERIES.items():
            if key in question:
                return DBQueryService.execute_query(sql)
        
        sql = DBQueryService.generate_sql(question)
        if not sql:
            return {"success": False, "error": "无法生成安全的SQL查询"}
        
        return DBQueryService.execute_query(sql)

    @staticmethod
    def format_results(results: dict) -> str:
        if not results.get("success", False):
            return f"查询失败: {results.get('error', '未知错误')}"
        
        data = results.get("results", [])
        columns = results.get("columns", [])
        count = results.get("count", 0)
        
        if count == 0:
            return "查询结果为空"
        
        if count == 1:
            result = data[0]
            lines = ["查询结果："]
            for col in columns:
                lines.append(f"- {col}: {result.get(col, '')}")
            return "\n".join(lines)
        
        if count <= 10:
            lines = ["查询结果（共{}条）：".format(count)]
            lines.append(" | ".join(columns))
            lines.append("-" * 80)
            for row in data:
                row_values = [str(row.get(col, "")) for col in columns]
                lines.append(" | ".join(row_values))
            return "\n".join(lines)
        
        lines = ["查询结果（共{}条，显示前10条）：".format(count)]
        lines.append(" | ".join(columns))
        lines.append("-" * 80)
        for row in data[:10]:
            row_values = [str(row.get(col, "")) for col in columns]
            lines.append(" | ".join(row_values))
        lines.append("...")
        return "\n".join(lines)

    @staticmethod
    def to_structured_table(results: dict, title: str = "查询结果", max_display: int = 50) -> dict:
        """将原始查询结果转换为结构化表格数据，供前端 table 消息类型使用。"""
        if not results.get("success", False):
            return None

        data_rows = results.get("results", [])
        col_names = results.get("columns", [])
        total = results.get("count", len(data_rows))

        columns = []
        for col in col_names:
            col_lower = col.lower()
            is_numeric = any(kw in col_lower for kw in
                ("id", "count", "num", "amount", "total", "score", "price", "value", "sum", "avg"))
            col_def = {
                "key": col,
                "title": col,
                "width": "100px" if is_numeric else "auto",
                "align": "right" if is_numeric else "left"
            }
            columns.append(col_def)

        display_rows = data_rows[:max_display]
        truncated = total > max_display

        return {
            "title": title,
            "columns": columns,
            "rows": display_rows,
            "total_count": total,
            "display_count": len(display_rows),
            "truncated": truncated,
            "sql": results.get("sql", "")
        }

    @staticmethod
    def to_html_table(results: dict, title: str = "查询结果", max_display: int = 50) -> str:
        """将查询结果生成为内联样式的 HTML 表格字符串，用于 stream 消息的直接注入。"""
        if not results.get("success", False):
            return f"<p style='color:#dc2626'>查询失败: {results.get('error', '未知错误')}</p>"

        data_rows = results.get("results", [])
        col_names = results.get("columns", [])
        total = results.get("count", len(data_rows))
        display_rows = data_rows[:max_display]

        if total == 0:
            return "<p style='color:#9ca3af'>查询结果为空</p>"

        style = """
        <style>
            .inline-table{width:100%;border-collapse:collapse;font-size:13px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
            .inline-table thead th{background:#1f2937;color:#fff;padding:10px 12px;text-align:left;font-weight:600;border-bottom:2px solid #374151;white-space:nowrap}
            .inline-table tbody td{padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#374151}
            .inline-table tbody tr:nth-child(even){background:#f9fafb}
            .inline-table tbody tr:hover{background:#f3f4f6}
            .inline-table .num{text-align:right;font-variant-numeric:tabular-nums}
            .table-caption{font-size:12px;color:#9ca3af;margin-top:8px}
        </style>
        """

        header_cells = "".join(f"<th>{c}</th>" for c in col_names)
        body_rows = ""
        for row in display_rows:
            cells = ""
            for c in col_names:
                val = row.get(c, "")
                cls = ' class="num"' if isinstance(val, (int, float)) else ""
                cells += f"<td{cls}>{val}</td>"
            body_rows += f"<tr>{cells}</tr>"

        trunc_note = ""
        if total > max_display:
            trunc_note = f"<p class='table-caption'>显示前 {max_display} 条，共 {total} 条记录</p>"
        else:
            trunc_note = f"<p class='table-caption'>共 {total} 条记录</p>"

        return f"""{style}
        <div style="overflow-x:auto;border-radius:8px;border:1px solid #e5e7eb;box-shadow:0 1px 3px rgba(0,0,0,0.06)">
            <div style="padding:10px 16px;background:#f8fafc;border-bottom:1px solid #e5e7eb;font-weight:600;font-size:14px;color:#1f2937">{title}</div>
            <table class="inline-table">
                <thead><tr>{header_cells}</tr></thead>
                <tbody>{body_rows}</tbody>
            </table>
        </div>
        {trunc_note}"""

    @staticmethod
    def analyze_data(question: str, results: dict) -> dict:
        if not results.get("success", False):
            return {"success": False, "error": "查询结果为空"}

        data = results.get("results", [])
        columns = results.get("columns", [])

        # 构建结构化表格数据
        table_data = DBQueryService.to_structured_table(results, title=question[:30])

        # 尝试生成图表建议
        chart_data = None
        try:
            from app.models.report import ReportService
            report_result = ReportService.generate_report_with_data(question, results)
            if report_result.get("success"):
                chart_data = {
                    "chart_type": report_result.get("chart_type", "bar"),
                    "option": report_result.get("option", {})
                }
        except Exception:
            pass

        model = AIModelRepository.get_default_model()
        if not model:
            return {
                "success": True,
                "analysis": DBQueryService.format_results(results),
                "raw_data": data,
                "columns": columns,
                "table_data": table_data,
                "chart_data": chart_data
            }

        data_str = json.dumps(data, ensure_ascii=False, indent=2)

        system_prompt = """你是一个专业的数据分析助手。请根据用户的问题和查询结果，进行深度分析并给出专业的分析报告。

分析要求：
1. 根据查询结果进行统计分析
2. 识别数据中的趋势和模式
3. 提供数据洞察和业务建议
4. 如果数据包含时间序列，分析趋势变化
5. 如果数据包含分类信息，分析分布情况
6. 如果数据包含多个维度，进行交叉分析

请用中文输出，语言简洁专业，200字以内。结尾用一行 [INSIGHTS] 列出 2-3 个关键洞察，每行一条，以 - 开头。"""

        user_prompt = f"""用户问题：{question}

查询结果（共 {len(data)} 条）：
{data_str}

请进行分析："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            result = AIModelService.chat_completion(model, messages, stream=False)
            if "choices" in result and result["choices"]:
                analysis = result["choices"][0]["message"]["content"]

                # 解析洞察列表
                insights = []
                if "[INSIGHTS]" in analysis:
                    parts = analysis.split("[INSIGHTS]")
                    analysis = parts[0].strip()
                    for line in parts[1].strip().split("\n"):
                        line = line.strip().lstrip("- ").strip()
                        if line:
                            insights.append(line)

                return {
                    "success": True,
                    "analysis": analysis,
                    "insights": insights,
                    "raw_data": data,
                    "columns": columns,
                    "table_data": table_data,
                    "chart_data": chart_data
                }
        except Exception:
            pass

        return {
            "success": True,
            "analysis": DBQueryService.format_results(results),
            "insights": [],
            "raw_data": data,
            "columns": columns,
            "table_data": table_data,
            "chart_data": chart_data
        }

    @staticmethod
    def search_data_warehouse(keyword: str, limit: int = 20) -> dict:
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, title, summary, content, url, source, is_deep_collected, created_at 
                   FROM data_warehouse 
                   WHERE status=1 AND (title LIKE ? OR summary LIKE ? OR content LIKE ? OR keyword LIKE ?)
                   ORDER BY created_at DESC LIMIT ?""",
                (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit)
            )
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append(dict(row))
            
            return {
                "success": True,
                "columns": columns,
                "results": results,
                "count": len(results)
            }

    @staticmethod
    def get_data_summary() -> dict:
        summary = {}
        
        with get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM users WHERE status=1")
            summary["total_users"] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM digital_employees WHERE status=1")
            summary["total_employees"] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM ai_models WHERE status=1")
            summary["total_models"] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM watch_sources WHERE status=1")
            summary["total_sources"] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM data_warehouse WHERE status=1")
            summary["total_data_records"] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM conversations WHERE status=1")
            summary["total_conversations"] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM data_warehouse WHERE status=1 AND is_deep_collected=1")
            summary["deep_collected_count"] = cursor.fetchone()[0]
        
        return {"success": True, "summary": summary}