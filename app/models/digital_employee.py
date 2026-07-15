import json
import sqlite3
import requests
import urllib.parse

from app.models.db import get_connection


class DigitalEmployeeRepository:
    @staticmethod
    def get_employees(page: int = 1, page_size: int = 20, keyword: str = "", type: int = 0):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            conditions = ["status=1"]
            params = []
            if keyword:
                conditions.append("(name LIKE ? OR code_name LIKE ? OR description LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
            if type > 0:
                conditions.append("type=?")
                params.append(type)
            where_clause = " AND ".join(conditions)
            
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM digital_employees WHERE {where_clause}",
                params
            )
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                f"""SELECT * FROM digital_employees WHERE {where_clause} 
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                params + [page_size, offset]
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_employee_by_id(employee_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM digital_employees WHERE id=?",
                (employee_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_employee_by_code_name(code_name: str):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM digital_employees WHERE code_name=? AND status=1",
                (code_name,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_employee_by_name(name: str):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM digital_employees WHERE name=? AND status=1",
                (name,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def create_employee(name: str, code_name: str, type: int = 1, model_id: int = 0,
                        prompt: str = "", skills: str = "", use_crawl4ai: int = 0,
                        api_url: str = "", api_method: str = "GET", api_headers: str = "",
                        api_params: str = "", api_body: str = "", description: str = "",
                        md_files_path: str = "") -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO digital_employees 
                    (name, code_name, type, model_id, prompt, skills, use_crawl4ai,
                     api_url, api_method, api_headers, api_params, api_body, description,
                     md_files_path)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, code_name, type, model_id, prompt, skills, use_crawl4ai,
                     api_url, api_method, api_headers, api_params, api_body, description,
                     md_files_path)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_employee(employee_id: int, name: str, code_name: str, type: int = 1,
                        model_id: int = 0, prompt: str = "", skills: str = "",
                        use_crawl4ai: int = 0, api_url: str = "", api_method: str = "GET",
                        api_headers: str = "", api_params: str = "", api_body: str = "",
                        description: str = "", status: int = 1, md_files_path: str = "") -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """UPDATE digital_employees SET name=?, code_name=?, type=?, model_id=?, 
                    prompt=?, skills=?, use_crawl4ai=?, api_url=?, api_method=?, 
                    api_headers=?, api_params=?, api_body=?, description=?, status=?,
                    md_files_path=?, updated_at=datetime('now','localtime') WHERE id=?""",
                    (name, code_name, type, model_id, prompt, skills, use_crawl4ai,
                     api_url, api_method, api_headers, api_params, api_body, description, status,
                     md_files_path, employee_id)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_employee(employee_id: int) -> bool:
        with get_connection() as conn:
            conn.execute("UPDATE digital_employees SET status=2 WHERE id=?", (employee_id,))
        return True

    @staticmethod
    def toggle_employee_status(employee_id: int, status: int) -> bool:
        with get_connection() as conn:
            conn.execute("UPDATE digital_employees SET status=? WHERE id=?", (status, employee_id))
        return True

    @staticmethod
    def get_stats():
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT COUNT(*) as total,
                   SUM(CASE WHEN type=1 THEN 1 ELSE 0 END) as llm_count,
                   SUM(CASE WHEN type=2 THEN 1 ELSE 0 END) as api_count,
                   SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) as active_count
                   FROM digital_employees WHERE status=1"""
            )
            row = cursor.fetchone()
        return dict(row) if row else {"total": 0, "llm_count": 0, "api_count": 0, "active_count": 0}


class DigitalEmployeeService:
    @staticmethod
    def execute(employee: dict, params: dict = None) -> dict:
        employee_type = employee.get("type", 1)
        
        if employee_type == 1:
            return DigitalEmployeeService._execute_llm_type(employee, params)
        elif employee_type == 2:
            return DigitalEmployeeService._execute_api_type(employee, params)
        else:
            return {"success": False, "error": "未知的数字员工类型"}

    @staticmethod
    def _execute_llm_type(employee: dict, params: dict = None) -> dict:
        from app.models.model import AIModelRepository, AIModelService
        
        model_id = employee.get("model_id", 0)
        model = None
        
        if model_id > 0:
            model = AIModelRepository.get_model_by_id(model_id)
        
        if not model:
            model = AIModelRepository.get_default_model()
        
        if not model:
            return {"success": False, "error": "未找到可用的模型"}
        
        prompt = employee.get("prompt", "")
        use_crawl4ai = employee.get("use_crawl4ai", 0)
        
        md_content = DigitalEmployeeService._read_md_files(employee.get("md_files_path", ""))
        if md_content:
            prompt = f"参考文档：\n{md_content}\n\n{prompt}"
        
        crawled_content = ""
        if use_crawl4ai == 1 and params and params.get("url"):
            crawled_content = DigitalEmployeeService._crawl_with_crawl4ai(params["url"])
        
        if params:
            try:
                prompt = prompt.format(**params)
            except KeyError as e:
                return {"success": False, "error": f"Prompt参数缺失: {e}"}
        
        if crawled_content:
            prompt = f"网页内容：\n{crawled_content}\n\n{prompt}"
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            result = AIModelService.chat_completion(model, messages, stream=False)
            if "choices" in result and result["choices"]:
                content = result["choices"][0]["message"]["content"]
                return {
                    "success": True,
                    "content": content,
                    "type": "llm",
                    "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                    "completion_tokens": result.get("usage", {}).get("completion_tokens", 0),
                    "crawled": True if crawled_content else False
                }
            # 模型无响应数据，但如果有crawl4ai采集的内容，则返回该内容
            if crawled_content:
                return {
                    "success": True,
                    "content": crawled_content,
                    "type": "crawl4ai_fallback",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "crawled": True,
                    "warning": "模型无响应，使用crawl4ai采集的原始内容"
                }
            return {"success": False, "error": "模型无响应数据"}
        except Exception as e:
            # 模型调用异常，但如果有crawl4ai采集的内容，则返回该内容
            if crawled_content:
                return {
                    "success": True,
                    "content": crawled_content,
                    "type": "crawl4ai_fallback",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "crawled": True,
                    "warning": f"模型调用异常({str(e)})，使用crawl4ai采集的原始内容"
                }
            return {"success": False, "error": str(e)}

    @staticmethod
    def _crawl_with_crawl4ai(url: str) -> str:
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
            import asyncio
            import threading

            result_holder = [None]

            def _run():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    browser_config = BrowserConfig(headless=True)
                    crawler_config = CrawlerRunConfig()
                    crawler = AsyncWebCrawler(config=browser_config)
                    result_holder[0] = loop.run_until_complete(crawler.arun(url=url, config=crawler_config))
                finally:
                    loop.close()

            t = threading.Thread(target=_run)
            t.start()
            t.join(timeout=60)

            result = result_holder[0]
            if result is None:
                return "crawl4ai采集超时或失败"

            if result.success:
                content = ""
                if hasattr(result, 'markdown') and result.markdown:
                    content = result.markdown
                elif hasattr(result, 'html') and result.html:
                    content = result.html

                # 确保内容是UTF-8编码的字符串
                if isinstance(content, bytes):
                    try:
                        content = content.decode('utf-8', errors='ignore')
                    except:
                        content = content.decode('gbk', errors='ignore')

                # 清理乱码字符
                content = content.replace('\ufffd', '')  # 替换替换字符
                content = content.replace('\x00', '')    # 移除空字符

                if len(content) > 5000:
                    content = content[:5000] + "\n\n[内容过长，已截断]"

                return content
            else:
                error_msg = ""
                if hasattr(result, 'error_message'):
                    error_msg = result.error_message
                return f"采集失败: {error_msg}"
        except Exception as e:
            return f"crawl4ai采集异常: {str(e)}"

    @staticmethod
    def _read_md_files(md_files_path: str) -> str:
        import os
        if not md_files_path or not os.path.exists(md_files_path):
            return ""
        
        md_contents = []
        try:
            for filename in os.listdir(md_files_path):
                if filename.endswith(".md"):
                    file_path = os.path.join(md_files_path, filename)
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        md_contents.append(f"文件: {filename}\n{content}")
        except Exception:
            pass
        
        return "\n\n".join(md_contents)

    @staticmethod
    def _execute_api_type(employee: dict, params: dict = None) -> dict:
        api_url = employee.get("api_url", "")
        api_method = employee.get("api_method", "GET").upper()
        api_headers = employee.get("api_headers", "")
        api_params = employee.get("api_params", "")
        api_body = employee.get("api_body", "")
        
        if not api_url:
            return {"success": False, "error": "API URL未配置"}
        
        try:
            headers = json.loads(api_headers) if api_headers else {}
            query_params = json.loads(api_params) if api_params else {}
            body = json.loads(api_body) if api_body else {}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"配置JSON解析错误: {e}"}
        
        if params:
            api_url = api_url.format(**params)
            if employee.get("code_name") == "weather":
                query_params = {}
                url_parts = urllib.parse.urlparse(api_url)
                path = urllib.parse.quote(url_parts.path, safe='/')
                api_url = urllib.parse.urlunparse((url_parts.scheme, url_parts.netloc, path, url_parts.params, url_parts.query, url_parts.fragment))
            else:
                query_params.update(params)
                if isinstance(body, dict):
                    body.update(params)
        
        try:
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            
            if api_method == "GET":
                url = api_url
                if query_params:
                    if "?" in url:
                        url += "&" + urllib.parse.urlencode(query_params, encoding='utf-8')
                    else:
                        url += "?" + urllib.parse.urlencode(query_params, encoding='utf-8')
                response = requests.get(url, headers=headers, timeout=30, verify=False)
            elif api_method == "POST":
                response = requests.post(api_url, headers=headers, params=query_params, json=body, timeout=30, verify=False)
            elif api_method == "PUT":
                response = requests.put(api_url, headers=headers, params=query_params, json=body, timeout=30, verify=False)
            elif api_method == "DELETE":
                response = requests.delete(api_url, headers=headers, params=query_params, timeout=30, verify=False)
            else:
                return {"success": False, "error": f"不支持的HTTP方法: {api_method}"}
            
            response.raise_for_status()
            
            try:
                result = response.json()
                
                if employee.get("code_name") == "weather" and isinstance(result, dict):
                    try:
                        current_condition = result.get("current_condition", [])[0]
                        location = result.get("nearest_area", [])[0].get("areaName", [])[0].get("value", "")
                        date = current_condition.get("observation_time", "")
                        temp = f"{current_condition.get('temp_C', '')}°C"
                        condition = current_condition.get("weatherDesc", [])[0].get("value", "")
                        humidity = f"{current_condition.get('humidity', '')}%"
                        wind = current_condition.get("windspeedKmph", "") + " km/h"
                        visibility = current_condition.get("visibility", "") + " km"
                        
                        return {
                            "success": True,
                            "content": {
                                "location": location,
                                "date": date,
                                "temp": temp,
                                "condition": condition,
                                "humidity": humidity,
                                "wind": wind,
                                "visibility": visibility
                            },
                            "type": "api",
                            "raw": response.text
                        }
                    except (IndexError, KeyError):
                        pass
                
                return {"success": True, "content": result, "type": "api", "raw": response.text}
            except json.JSONDecodeError:
                return {"success": True, "content": response.text, "type": "api", "raw": response.text}
        
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def test_employee(employee_id: int, test_params: dict = None) -> dict:
        employee = DigitalEmployeeRepository.get_employee_by_id(employee_id)
        if not employee:
            return {"success": False, "error": "数字员工不存在"}
        
        if employee.get("status", 1) != 1:
            return {"success": False, "error": "数字员工已禁用"}
        
        return DigitalEmployeeService.execute(employee, test_params)

    @staticmethod
    def get_employee_by_code(code_name: str):
        return DigitalEmployeeRepository.get_employee_by_code_name(code_name)

    @staticmethod
    def execute_by_code(code_name: str, args: str = "") -> dict:
        employee = DigitalEmployeeRepository.get_employee_by_code_name(code_name)
        if not employee:
            return {"success": False, "error": f"数字员工 @{code_name} 不存在"}
        
        if employee.get("status", 1) != 1:
            return {"success": False, "error": f"数字员工 @{code_name} 已禁用"}
        
        params = {}
        if args:
            params["query"] = args
            parts = args.split()
            if employee.get("code_name") == "weather":
                params["city"] = args.strip()
            elif len(parts) >= 2:
                params["city"] = parts[-1]
                params["keywords"] = " ".join(parts[:-1])
            else:
                params["keywords"] = args
        
        result = DigitalEmployeeService.execute(employee, params)
        
        if result.get("success", False):
            content = result.get("content", "")
            if isinstance(content, dict):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            return {"success": True, "result": content}
        else:
            return {"success": False, "error": result.get("error", "未知错误")}
