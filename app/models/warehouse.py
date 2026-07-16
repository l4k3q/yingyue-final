import json
from app.models.db import get_connection


class DataWarehouseRepository:
    @staticmethod
    def add_record(title, summary="", content="", url="", source="", source_id=0, keyword="", image_url=""):
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO data_warehouse 
                (title, summary, content, url, source, source_id, keyword, image_url)
                VALUES (?,?,?,?,?,?,?,?)""",
                (title, summary, content, url, source, source_id, keyword, image_url)
            )

    @staticmethod
    def add_records(records):
        with get_connection() as conn:
            conn.executemany(
                """INSERT INTO data_warehouse 
                (title, summary, content, url, source, source_id, keyword, image_url)
                VALUES (?,?,?,?,?,?,?,?)""",
                records
            )

    @staticmethod
    def get_records(page=1, page_size=20, keyword="", source=""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            conditions = ["status=1"]
            params = []
            if keyword:
                conditions.append("(title LIKE ? OR summary LIKE ? OR keyword LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
            if source:
                conditions.append("source LIKE ?")
                params.append(f"%{source}%")
            where_clause = " AND ".join(conditions)
            
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM data_warehouse WHERE {where_clause}",
                params
            )
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                f"""SELECT * FROM data_warehouse WHERE {where_clause} 
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                params + [page_size, offset]
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_record_by_id(record_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM data_warehouse WHERE id=?",
                (record_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def update_record(record_id, **kwargs):
        fields = []
        params = []
        for key, value in kwargs.items():
            fields.append(f"{key}=?")
            params.append(value)
        params.append(record_id)
        with get_connection() as conn:
            conn.execute(
                f"UPDATE data_warehouse SET {', '.join(fields)} WHERE id=?",
                params
            )

    @staticmethod
    def delete_record(record_id):
        with get_connection() as conn:
            conn.execute("UPDATE data_warehouse SET status=0 WHERE id=?", (record_id,))

    @staticmethod
    def mark_deep_collected(record_id):
        with get_connection() as conn:
            conn.execute(
                "UPDATE data_warehouse SET is_deep_collected=1, deep_collect_time=datetime('now','localtime') WHERE id=?",
                (record_id,)
            )

    @staticmethod
    def get_stats():
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT COUNT(*) as total, 
                   SUM(CASE WHEN is_deep_collected=1 THEN 1 ELSE 0 END) as deep_collected
                   FROM data_warehouse WHERE status=1"""
            )
            row = cursor.fetchone()
        return dict(row) if row else {"total": 0, "deep_collected": 0}


class DeepCollectTaskRepository:
    @staticmethod
    def create_task(record_id, employee_id=0, employee_name=""):
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO deep_collect_tasks 
                (record_id, employee_id, employee_name, status, progress)
                VALUES (?,?,?,?,?)""",
                (record_id, employee_id, employee_name, 0, 0)
            )
            cursor = conn.execute("SELECT last_insert_rowid()")
            return cursor.fetchone()[0]

    @staticmethod
    def get_tasks(page=1, page_size=20, record_id=0, status=0):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            conditions = []
            params = []
            if record_id > 0:
                conditions.append("record_id=?")
                params.append(record_id)
            if status >= 0:
                conditions.append("status=?")
                params.append(status)
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM deep_collect_tasks WHERE {where_clause}",
                params
            )
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                f"""SELECT * FROM deep_collect_tasks WHERE {where_clause} 
                ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                params + [page_size, offset]
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows], total

    @staticmethod
    def get_task_by_id(task_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM deep_collect_tasks WHERE id=?",
                (task_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_task_by_record_id(record_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM deep_collect_tasks WHERE record_id=? ORDER BY created_at DESC LIMIT 1",
                (record_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def update_task(task_id, **kwargs):
        fields = []
        params = []
        for key, value in kwargs.items():
            fields.append(f"{key}=?")
            params.append(value)
        params.append(task_id)
        with get_connection() as conn:
            conn.execute(
                f"UPDATE deep_collect_tasks SET {', '.join(fields)}, updated_at=datetime('now','localtime') WHERE id=?",
                params
            )

    @staticmethod
    def update_task_status(task_id, status, progress=0, step="", log="", result=""):
        with get_connection() as conn:
            conn.execute(
                """UPDATE deep_collect_tasks SET status=?, progress=?, step=?, 
                   log=?, result=?, updated_at=datetime('now','localtime') WHERE id=?""",
                (status, progress, step, log, result, task_id)
            )

    @staticmethod
    def add_log(task_id, log_message):
        with get_connection() as conn:
            conn.execute(
                """UPDATE deep_collect_tasks SET log=log || ? || '\n', 
                   updated_at=datetime('now','localtime') WHERE id=?""",
                (log_message, task_id)
            )

    @staticmethod
    def delete_task(task_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM deep_collect_tasks WHERE id=?", (task_id,))


class DeepCollectService:
    @staticmethod
    def execute_deep_collect(record_id):
        record = DataWarehouseRepository.get_record_by_id(record_id)
        if not record:
            return {"success": False, "error": "记录不存在"}

        employee = DeepCollectService._find_collect_employee()
        
        task_id = DeepCollectTaskRepository.create_task(
            record_id, 
            employee.get("id", 0) if employee else 0,
            employee.get("name", "") if employee else ""
        )

        try:
            DeepCollectTaskRepository.update_task_status(
                task_id, 1, 10, "初始化", f"开始深度采集，记录ID: {record_id}", ""
            )

            if employee:
                DeepCollectTaskRepository.update_task_status(
                    task_id, 1, 20, "调度数字员工", f"调度数字员工: {employee['name']} (@{employee['code_name']})", ""
                )
                DeepCollectTaskRepository.add_log(task_id, f"数字员工类型: {'LLM' if employee['type'] == 1 else 'API'}")
                
                params = {
                    "url": record.get("url", ""),
                    "title": record.get("title", ""),
                    "summary": record.get("summary", ""),
                    "keyword": record.get("keyword", "")
                }
                
                DeepCollectTaskRepository.update_task_status(
                    task_id, 1, 30, "执行采集", "正在执行数字员工采集...", ""
                )
                
                result = DeepCollectService._execute_employee(employee, params, task_id)
                
                if result.get("success", False):
                    DeepCollectTaskRepository.update_task_status(
                        task_id, 1, 80, "处理结果", "采集完成，处理结果数据...", ""
                    )
                    
                    DeepCollectService._save_result(record_id, result, task_id)
                    
                    DeepCollectTaskRepository.update_task_status(
                        task_id, 2, 100, "完成", "深度采集完成", json.dumps(result)
                    )
                    
                    DataWarehouseRepository.mark_deep_collected(record_id)
                    
                    return {"success": True, "message": "深度采集完成", "task_id": task_id}
                else:
                    # 数字员工采集失败，尝试使用crawl4ai作为fallback
                    DeepCollectTaskRepository.add_log(task_id, f"数字员工采集失败，尝试使用crawl4ai作为fallback: {result.get('error', '')}")
                    DeepCollectTaskRepository.update_task_status(
                        task_id, 1, 60, "Fallback采集", "数字员工采集失败，使用crawl4ai采集...", ""
                    )
                    
                    fallback_result = DeepCollectService._default_collect(record, task_id)
                    
                    if fallback_result.get("success", False):
                        DeepCollectTaskRepository.update_task_status(
                            task_id, 2, 100, "完成", "深度采集完成(fallback方式)", json.dumps(fallback_result)
                        )
                        DataWarehouseRepository.mark_deep_collected(record_id)
                        return {"success": True, "message": "深度采集完成(fallback方式)", "task_id": task_id}
                    else:
                        DeepCollectTaskRepository.update_task_status(
                            task_id, 3, 0, "失败", f"采集失败: {fallback_result.get('error', '未知错误')}", ""
                        )
                        return {"success": False, "error": fallback_result.get("error", "采集失败"), "task_id": task_id}
            else:
                DeepCollectTaskRepository.update_task_status(
                    task_id, 1, 50, "默认采集", "未找到采集专员，使用默认采集方式...", ""
                )
                
                result = DeepCollectService._default_collect(record, task_id)
                
                if result.get("success", False):
                    DeepCollectTaskRepository.update_task_status(
                        task_id, 2, 100, "完成", "深度采集完成", json.dumps(result)
                    )
                    DataWarehouseRepository.mark_deep_collected(record_id)
                    return {"success": True, "message": "深度采集完成(默认方式)", "task_id": task_id}
                else:
                    DeepCollectTaskRepository.update_task_status(
                        task_id, 3, 0, "失败", f"采集失败: {result.get('error', '未知错误')}", ""
                    )
                    return {"success": False, "error": result.get("error", "采集失败"), "task_id": task_id}
                    
        except Exception as e:
            DeepCollectTaskRepository.update_task_status(
                task_id, 3, 0, "异常", f"系统异常: {str(e)}", ""
            )
            return {"success": False, "error": str(e), "task_id": task_id}

    @staticmethod
    def _find_collect_employee():
        from app.models.digital_employee import DigitalEmployeeRepository
        
        employee = DigitalEmployeeRepository.get_employee_by_code_name("collector")
        if employee:
            return employee
        
        employees, _ = DigitalEmployeeRepository.get_employees(page=1, page_size=10, type=1)
        for emp in employees:
            if "采集" in emp.get("name", "") or "collect" in emp.get("code_name", "").lower():
                return emp
        
        return None

    @staticmethod
    def _execute_employee(employee, params, task_id):
        from app.models.digital_employee import DigitalEmployeeService
        
        DeepCollectTaskRepository.add_log(task_id, f"执行参数: {json.dumps(params)}")
        
        result = DigitalEmployeeService.execute(employee, params)
        
        if result.get("success", False):
            DeepCollectTaskRepository.add_log(task_id, f"执行成功")
            DeepCollectTaskRepository.add_log(task_id, f"返回类型: {result.get('type', 'unknown')}")
        else:
            DeepCollectTaskRepository.add_log(task_id, f"执行失败: {result.get('error', '')}")
        
        return result

    @staticmethod
    def _default_collect(record, task_id):
        url = record.get("url", "")
        if not url:
            return {"success": False, "error": "记录没有URL"}
        
        try:
            DeepCollectTaskRepository.add_log(task_id, f"使用crawl4ai开始采集URL: {url}")

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
                DeepCollectTaskRepository.add_log(task_id, "crawl4ai采集超时或失败")
                return {"success": False, "error": "crawl4ai采集超时或失败"}

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

                title = record.get("title", "")
                metadata = {}
                if hasattr(result, 'metadata') and result.metadata:
                    metadata = result.metadata
                    if metadata.get("title"):
                        title = metadata["title"]

                DeepCollectTaskRepository.add_log(task_id, f"crawl4ai采集完成，内容长度: {len(content)}")
                
                return {
                    "success": True,
                    "content": content,
                    "title": title,
                    "type": "crawl4ai",
                    "metadata": metadata
                }
            else:
                error_msg = ""
                if hasattr(result, 'error_message'):
                    error_msg = result.error_message
                error_msg = f"crawl4ai采集失败: {error_msg}"
                DeepCollectTaskRepository.add_log(task_id, error_msg)
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            DeepCollectTaskRepository.add_log(task_id, f"crawl4ai采集异常: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _save_result(record_id, result, task_id):
        content = result.get("content", "")
        
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False)
        
        DataWarehouseRepository.update_record(
            record_id,
            content=content,
            is_deep_collected=1,
            deep_collect_time="datetime('now','localtime')"
        )
        
        DeepCollectTaskRepository.add_log(task_id, "结果已保存到数据仓库")

    @staticmethod
    def batch_deep_collect(record_ids):
        results = []
        for record_id in record_ids:
            result = DeepCollectService.execute_deep_collect(record_id)
            results.append({"record_id": record_id, **result})
        return results

    @staticmethod
    def get_deep_collect_detail(record_id):
        record = DataWarehouseRepository.get_record_by_id(record_id)
        task = DeepCollectTaskRepository.get_task_by_record_id(record_id)
        
        return {
            "record": record,
            "task": task
        }