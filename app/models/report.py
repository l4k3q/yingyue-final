import json

from app.models.db_query import DBQueryService


class ReportService:
    @staticmethod
    def generate_report(question: str) -> dict:
        db_result = DBQueryService.query(question)
        return ReportService.generate_report_with_data(question, db_result)

    @staticmethod
    def generate_report_with_data(question: str, db_result: dict) -> dict:
        """与 generate_report 相同，但接受预取的查询结果，避免重复查询。"""
        if not db_result.get("success", False):
            return {"success": False, "error": db_result.get("error", "查询失败")}

        data = db_result.get("results", [])
        columns = db_result.get("columns", [])

        if len(data) == 0:
            return {"success": False, "error": "没有数据可以生成报表"}

        chart_type = ReportService._determine_chart_type(data, columns, question)
        option = ReportService._build_chart_option(chart_type, data, columns, question)

        return {
            "success": True,
            "chart_type": chart_type,
            "option": option,
            "data": data,
            "columns": columns
        }

    @staticmethod
    def _determine_chart_type(data, columns, question) -> str:
        numeric_cols = ReportService._get_numeric_columns(columns)
        text_cols = ReportService._get_text_columns(columns)
        
        if "趋势" in question or "变化" in question or "时间" in question or "走势" in question:
            for col in columns:
                if "date" in col.lower() or "time" in col.lower():
                    return "line"
        
        if "对比" in question or "排行" in question or "排名" in question or "比较" in question:
            if len(numeric_cols) >= 1 and len(text_cols) >= 1:
                return "bar"
        
        if "占比" in question or "比例" in question or "分布" in question or "构成" in question:
            if len(numeric_cols) >= 1 and len(text_cols) >= 1:
                return "pie"
        
        if "散点" in question or "关联" in question or "相关" in question:
            if len(numeric_cols) >= 2:
                return "scatter"
        
        if len(numeric_cols) >= 2:
            return "bar"
        
        if len(data) <= 10 and len(numeric_cols) >= 1:
            return "pie"
        
        if len(data) > 20 and len(numeric_cols) >= 1:
            return "line"
        
        return "bar"

    @staticmethod
    def _get_numeric_columns(columns):
        numeric_cols = []
        for col in columns:
            lower_col = col.lower()
            if "id" in lower_col or "count" in lower_col or "num" in lower_col or \
               "amount" in lower_col or "total" in lower_col or "score" in lower_col or \
               "price" in lower_col or "value" in lower_col or "sum" in lower_col or \
               "avg" in lower_col or "max" in lower_col or "min" in lower_col:
                numeric_cols.append(col)
        return numeric_cols

    @staticmethod
    def _get_text_columns(columns):
        text_cols = []
        for col in columns:
            lower_col = col.lower()
            if lower_col not in ["id", "status"] and not (
                "count" in lower_col or "num" in lower_col or "amount" in lower_col or
                "total" in lower_col or "score" in lower_col or "price" in lower_col or
                "value" in lower_col or "sum" in lower_col or "avg" in lower_col
            ):
                text_cols.append(col)
        return text_cols

    @staticmethod
    def _build_chart_option(chart_type, data, columns, question) -> dict:
        numeric_cols = ReportService._get_numeric_columns(columns)
        text_cols = ReportService._get_text_columns(columns)
        
        if chart_type == "pie":
            return ReportService._build_pie_option(data, text_cols, numeric_cols, question)
        elif chart_type == "line":
            return ReportService._build_line_option(data, text_cols, numeric_cols, question)
        elif chart_type == "scatter":
            return ReportService._build_scatter_option(data, text_cols, numeric_cols, question)
        else:
            return ReportService._build_bar_option(data, text_cols, numeric_cols, question)

    @staticmethod
    def _build_bar_option(data, text_cols, numeric_cols, question) -> dict:
        category_col = text_cols[0] if text_cols else "name"
        value_col = numeric_cols[0] if numeric_cols else "value"
        
        categories = [str(row.get(category_col, "")) for row in data]
        values = [int(row.get(value_col, 0)) if isinstance(row.get(value_col), (int, float)) else 0 for row in data]
        
        return {
            "title": {
                "text": question,
                "left": "center",
                "textStyle": {
                    "fontSize": 16,
                    "fontWeight": "bold"
                }
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {
                    "type": "shadow"
                }
            },
            "grid": {
                "left": "3%",
                "right": "8%",
                "bottom": "15%",
                "top": "15%",
                "containLabel": True
            },
            "xAxis": {
                "type": "category",
                "data": categories,
                "axisLabel": {
                    "rotate": 35,
                    "fontSize": 11,
                    "interval": 0,
                    "overflow": "truncate",
                    "width": 100
                }
            },
            "yAxis": {
                "type": "value"
            },
            "dataZoom": [{
                "type": "slider",
                "show": len(categories) > 15,
                "start": 0,
                "end": 100
            }] if len(categories) > 15 else [],
            "series": [{
                "name": value_col,
                "type": "bar",
                "data": values,
                "itemStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0,
                        "y": 0,
                        "x2": 0,
                        "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "#667eea"},
                            {"offset": 1, "color": "#764ba2"}
                        ]
                    },
                    " borderRadius": [4, 4, 0, 0]
                }
            }]
        }

    @staticmethod
    def _build_line_option(data, text_cols, numeric_cols, question) -> dict:
        category_col = text_cols[0] if text_cols else "date"
        value_col = numeric_cols[0] if numeric_cols else "value"
        
        categories = [str(row.get(category_col, "")) for row in data]
        values = [int(row.get(value_col, 0)) if isinstance(row.get(value_col), (int, float)) else 0 for row in data]
        
        return {
            "title": {
                "text": question,
                "left": "center",
                "textStyle": {
                    "fontSize": 16,
                    "fontWeight": "bold"
                }
            },
            "tooltip": {
                "trigger": "axis"
            },
            "grid": {
                "left": "3%",
                "right": "8%",
                "bottom": "15%",
                "top": "15%",
                "containLabel": True
            },
            "xAxis": {
                "type": "category",
                "boundaryGap": False,
                "data": categories,
                "axisLabel": {
                    "rotate": 35,
                    "fontSize": 11,
                    "interval": 0,
                    "overflow": "truncate",
                    "width": 100
                }
            },
            "yAxis": {
                "type": "value"
            },
            "dataZoom": [{
                "type": "slider",
                "show": len(categories) > 15,
                "start": 0,
                "end": 100
            }] if len(categories) > 15 else [],
            "series": [{
                "name": value_col,
                "type": "line",
                "data": values,
                "smooth": True,
                "areaStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0,
                        "y": 0,
                        "x2": 0,
                        "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "rgba(102, 126, 234, 0.3)"},
                            {"offset": 1, "color": "rgba(102, 126, 234, 0.05)"}
                        ]
                    }
                },
                "itemStyle": {
                    "color": "#667eea"
                }
            }]
        }

    @staticmethod
    def _build_pie_option(data, text_cols, numeric_cols, question) -> dict:
        category_col = text_cols[0] if text_cols else "name"
        value_col = numeric_cols[0] if numeric_cols else "value"
        
        pie_data = []
        for row in data:
            name = str(row.get(category_col, ""))
            value = int(row.get(value_col, 0)) if isinstance(row.get(value_col), (int, float)) else 0
            pie_data.append({"name": name, "value": value})
        
        colors = ["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe", "#00f2fe", "#43e97b", "#38f9d7"]
        
        return {
            "title": {
                "text": question,
                "left": "center",
                "textStyle": {
                    "fontSize": 16,
                    "fontWeight": "bold"
                }
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c} ({d}%)"
            },
            "legend": {
                "type": "scroll",
                "orient": "horizontal",
                "bottom": "0",
                "left": "center",
                "textStyle": {"fontSize": 11},
                "itemWidth": 10,
                "itemHeight": 10,
                "itemGap": 12
            },
            "series": [{
                "name": value_col,
                "type": "pie",
                "radius": ["45%", "75%"],
                "center": ["50%", "45%"],
                "avoidLabelOverlap": True,
                "itemStyle": {
                    "borderRadius": 6,
                    "borderColor": "#fff",
                    "borderWidth": 2
                },
                "label": {
                    "show": True,
                    "fontSize": 11,
                    "formatter": "{b} {d}%",
                    "overflow": "truncate",
                    "width": 80
                },
                "emphasis": {
                    "label": {
                        "show": True,
                        "fontSize": 13,
                        "fontWeight": "bold"
                    }
                },
                "labelLine": {
                    "show": True,
                    "length": 15,
                    "length2": 20
                },
                "data": pie_data,
                "color": colors
            }]
        }

    @staticmethod
    def _build_scatter_option(data, text_cols, numeric_cols, question) -> dict:
        x_col = numeric_cols[0] if numeric_cols else "x"
        y_col = numeric_cols[1] if len(numeric_cols) > 1 else "y"
        category_col = text_cols[0] if text_cols else None
        
        scatter_data = []
        for row in data:
            x_val = int(row.get(x_col, 0)) if isinstance(row.get(x_col), (int, float)) else 0
            y_val = int(row.get(y_col, 0)) if isinstance(row.get(y_col), (int, float)) else 0
            item = {"value": [x_val, y_val]}
            if category_col:
                item["name"] = str(row.get(category_col, ""))
            scatter_data.append(item)
        
        return {
            "title": {
                "text": question,
                "left": "center",
                "textStyle": {
                    "fontSize": 16,
                    "fontWeight": "bold"
                }
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: ({c[0]}, {c[1]})"
            },
            "legend": {
                "show": category_col is not None
            },
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "3%",
                "containLabel": True
            },
            "xAxis": {
                "type": "value",
                "name": x_col
            },
            "yAxis": {
                "type": "value",
                "name": y_col
            },
            "series": [{
                "type": "scatter",
                "data": scatter_data,
                "symbolSize": 10,
                "itemStyle": {
                    "color": "#667eea"
                }
            }]
        }