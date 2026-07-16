import json
import re
import time
import asyncio
import base64

import tornado.websocket

from app.controllers.base import BaseHandler
from app.models.user import UserRepository
from app.models.conversations import ConversationRepository
from app.models.digital_employee import DigitalEmployeeService, DigitalEmployeeRepository
from app.models.model import AIModelRepository, AIModelService
from app.models.intent import IntentService
from app.models.db_query import DBQueryService
from app.models.report import ReportService
from app.models.sensitive_word import SensitiveWordRepository
from app.models.security_alert import SecurityAlertRepository


class ConversationAPIHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        username = self.current_user
        user = UserRepository.get_user_by_username(username)
        if not user:
            self.write(json.dumps({"success": False, "error": "用户不存在"}))
            return
        
        user_id = user["id"]
        conversations, total = ConversationRepository.get_conversations(user_id)
        self.write(json.dumps({
            "success": True,
            "conversations": conversations,
            "total": total
        }))


class DigitalEmployeeAPIHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        employees, total = DigitalEmployeeRepository.get_employees()
        employee_list = []
        for emp in employees:
            employee_list.append({
                "id": emp["id"],
                "name": emp["name"],
                "code_name": emp["code_name"],
                "description": emp.get("description", ""),
                "type": emp["type"]
            })
        self.write(json.dumps({
            "success": True,
            "employees": employee_list,
            "total": total
        }))


class ModelListAPIHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        models, _ = AIModelRepository.get_models(page=1, page_size=100)
        model_list = []
        for m in models:
            if m.get("status") == 1:
                model_list.append({
                    "id": m["id"],
                    "name": m["name"],
                    "model_id": m["model_id"],
                    "description": m.get("description", ""),
                    "provider": m.get("provider", ""),
                    "is_default": m.get("is_default", 0)
                })
        self.write(json.dumps({"success": True, "models": model_list}))


class ChatWebSocketHandler(BaseHandler, tornado.websocket.WebSocketHandler):
    def open(self):
        self.username = self.get_current_user()
        if not self.username:
            self.close(code=401, reason="未登录")
            return
        user = UserRepository.get_user_by_username(self.username)
        self.user_id = user["id"] if user else 0
        self.conversation_id = None
        self.selected_model_id = None

    def on_message(self, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            msg_data = data.get("data")

            # Store model selection if provided
            if data.get("model_id") is not None:
                self.selected_model_id = data.get("model_id")

            if msg_type == "message":
                if isinstance(msg_data, dict):
                    content = msg_data.get("content", "")
                    model_id = msg_data.get("model_id")
                else:
                    content = msg_data
                    model_id = None
                self.handle_message(content, model_id=model_id)
            elif msg_type == "new_conversation":
                self.handle_new_conversation()
            elif msg_type == "load_conversation":
                self.handle_load_conversation(data.get("conversation_id"))
            elif msg_type == "delete_conversation":
                self.handle_delete_conversation(data.get("conversation_id"))
            elif msg_type == "set_model":
                self.selected_model_id = msg_data.get("model_id") if isinstance(msg_data, dict) else None
            elif msg_type == "ping":
                self.write_message({"type": "pong"})
            elif msg_type == "gesture":
                self.handle_gesture(msg_data)
        except json.JSONDecodeError:
            self.write_message({"type": "error", "data": "无效的消息格式"})

    def handle_new_conversation(self):
        self.conversation_id = ConversationRepository.create_conversation(self.user_id, "新对话")
        self.write_message({"type": "conversation_created", "data": {"conversation_id": self.conversation_id}})

    def handle_load_conversation(self, conversation_id):
        if not conversation_id:
            return
        self.conversation_id = conversation_id
        messages = ConversationRepository.get_messages(conversation_id)
        self.write_message({"type": "messages_loaded", "data": messages})

    def handle_delete_conversation(self, conversation_id):
        if not conversation_id:
            return
        ConversationRepository.delete_conversation(conversation_id)
        self.write_message({"type": "conversation_deleted", "data": conversation_id})

    def handle_gesture(self, gesture_data):
        if not gesture_data or not self.user_id:
            return
        
        gesture = gesture_data.get("gesture", "")
        
        gesture_mapping = {
            "scissors": {"employee": "天气", "args": ""},
            "fist": {"employee": "音乐", "args": ""},
            "palm": {"employee": "新闻", "args": ""}
        }
        
        if gesture == "thumbs_up":
            self.write_message({"type": "stream", "data": "生成已停止"})
            self.write_message({"type": "done"})
            return
        
        if gesture in gesture_mapping:
            mapping = gesture_mapping[gesture]
            self.handle_employee_message(mapping["employee"], mapping["args"])

    def handle_message(self, content, model_id=None):
        if not content or not self.user_id:
            return

        is_safe, matched = SensitiveWordRepository.scan(content)
        SensitiveWordRepository.create_scan_log(
            "conversation_message", 0, content, is_safe, len(matched)
        )
        if not is_safe:
            risk = SensitiveWordRepository.highest_risk_level(matched)
            SecurityAlertRepository.create_alert(
                "conversation", self.conversation_id or 0,
                self.user_id, self.username or "", matched,
                content[:300], risk,
            )
            words_list = ", ".join([word["word"] for word in matched[:5]])
            self.write_message({
                "type": "warning",
                "data": {
                    "message": f"您发送的内容包含敏感信息，已被系统拦截。命中敏感词: {words_list}",
                    "words": matched,
                    "risk_level": risk,
                },
            })
            return

        if not self.conversation_id:
            self.conversation_id = ConversationRepository.create_conversation(self.user_id, content[:30] if len(content) > 30 else content)

        ConversationRepository.add_message(self.conversation_id, "user", content)

        intent_result = IntentService.recognize_with_llm(content)
        intent = intent_result.get("intent", "general_chat")
        confidence = intent_result.get("confidence", 0.0)
        params = intent_result.get("params", {})

        self.write_message({"type": "typing", "data": f"正在分析意图: {IntentService.INTENT_TYPES.get(intent, intent)}..."})

        # 检测天气相关关键词 → 自动路由到 @天气 数字员工
        weather_keywords = ["天气", "气温", "温度", "下雨", "刮风", "湿度", "晴", "阴", "多云", "下雪", "台风"]
        if intent == "general_chat" and any(kw in content for kw in weather_keywords):
            self.handle_employee_message("天气", content)
        elif intent == "digital_employee":
            employee_name = params.get("employee_name", "")
            args = params.get("args", "")
            self.handle_employee_message(employee_name, args)
        elif intent == "database_query":
            self.handle_database_query(content)
        elif intent == "report_generation":
            self.handle_report_generation(content)
        elif intent == "data_search":
            self.handle_data_search(content)
        elif intent == "data_analysis":
            self.handle_data_analysis(content)
        elif intent == "relationship_mining":
            self.handle_relationship_mining(content)
        else:
            self.handle_general_chat(content, model_id=model_id)

    def handle_employee_message(self, employee_code, args):
        start_time = time.time()
        
        employee = DigitalEmployeeRepository.get_employee_by_name(employee_code)
        if not employee:
            employee = DigitalEmployeeRepository.get_employee_by_code_name(employee_code)
        
        if not employee:
            self.write_message({"type": "error", "data": f"数字员工 @{employee_code} 不存在"})
            return
        
        employee_name = employee.get("name", employee_code)
        self.write_message({"type": "typing", "data": f"正在调用 @{employee_name}..."})
        
        try:
            # 智能提取城市名（天气员工需要纯城市名调用 wttr.in API）
            # wttr.in 对中文城市名解析不稳定，使用中英映射
            CITY_MAP = {
                "成都": "Chengdu", "北京": "Beijing", "上海": "Shanghai", "深圳": "Shenzhen",
                "广州": "Guangzhou", "杭州": "Hangzhou", "武汉": "Wuhan", "南京": "Nanjing",
                "重庆": "Chongqing", "西安": "Xian", "天津": "Tianjin", "苏州": "Suzhou",
                "长沙": "Changsha", "郑州": "Zhengzhou", "青岛": "Qingdao", "大连": "Dalian",
                "厦门": "Xiamen", "福州": "Fuzhou", "昆明": "Kunming", "哈尔滨": "Harbin",
                "沈阳": "Shenyang", "济南": "Jinan", "合肥": "Hefei", "南昌": "Nanchang",
                "贵阳": "Guiyang", "南宁": "Nanning", "海口": "Haikou", "兰州": "Lanzhou",
                "拉萨": "Lhasa", "乌鲁木齐": "Urumqi",
            }
            if employee.get("code_name") == "weather" and args:
                # 优先匹配已知城市名（避免把"生成一张"等误判为城市）
                city_cn = None
                for cn_name in CITY_MAP:
                    if cn_name in args:
                        city_cn = cn_name
                        break
                if not city_cn:
                    # 去除常见非城市词后提取前2-3个汉字
                    text = args.strip()
                    for word in ["生成一张", "生成", "一张", "查询", "近五天", "近三天", "今天", "明天",
                                 "天气预报", "天气", "气温", "温度", "的", "表格", "情况", "怎么样", "如何"]:
                        text = text.replace(word, "")
                    import re as re_mod
                    city_match = re_mod.match(r'[一-鿿]{2,3}', text.strip())
                    city_cn = city_match.group(0) if city_match else (text.strip().split()[0] if text.strip().split() else text.strip()[:2])
                city = CITY_MAP.get(city_cn, city_cn) if city_cn else args.strip()[:2]
            elif args:
                parts = args.split()
                city = parts[-1] if parts else args.strip()
            else:
                city = ""
            result = DigitalEmployeeService.execute(employee, {"query": args, "city": city})
            
            if result.get("success", False):
                content = result.get("content", "")
                card_template = employee.get("card_template", "")

                # 天气预报卡片：先渲染卡片，再发送预报表格
                if card_template and isinstance(content, dict):
                    try:
                        ai_response = card_template.format(**content)
                    except KeyError:
                        ai_response = json.dumps(content, ensure_ascii=False, indent=2)
                elif isinstance(content, dict):
                    ai_response = json.dumps(content, ensure_ascii=False, indent=2)
                else:
                    ai_response = str(content)

                # 天气员工有预报数据时发送表格
                if employee.get("code_name") == "weather" and isinstance(content, dict):
                    forecast = content.get("forecast", [])
                    if forecast:
                        forecast_table = {
                            "title": f"{content.get('location', '')} 未来{len(forecast)}天天气预报",
                            "columns": [
                                {"key": "date", "title": "日期"},
                                {"key": "max_temp", "title": "最高温", "align": "right"},
                                {"key": "min_temp", "title": "最低温", "align": "right"},
                                {"key": "condition", "title": "天气"},
                                {"key": "wind", "title": "风力", "align": "right"},
                                {"key": "humidity", "title": "湿度", "align": "right"},
                            ],
                            "rows": forecast,
                            "total_count": len(forecast),
                            "display_count": len(forecast),
                            "truncated": False,
                        }
                        self.write_message({"type": "table", "data": forecast_table})
            else:
                ai_response = f"调用 @{employee_name} 失败: {result.get('error', '未知错误')}"

            elapsed_time = round(time.time() - start_time, 2)
            token_count = len(ai_response) // 4

            if self.conversation_id:
                # 注意：handle_message 已写入用户消息，此处只写入助手回复
                ConversationRepository.add_message(self.conversation_id, "assistant", ai_response)

            self.write_message({"type": "stream", "data": ai_response})
            self.write_message({"type": "metadata", "data": {"time": elapsed_time, "tokens": token_count}})
            self.write_message({"type": "done"})
        except Exception as e:
            error_msg = f"调用 @{employee_name} 时发生错误: {str(e)}"
            self.write_message({"type": "error", "data": error_msg})

    def handle_database_query(self, content):
        start_time = time.time()

        try:
            self.write_message({"type": "typing", "data": "正在查询数据库..."})

            result = DBQueryService.query(content)

            if result.get("success", False):
                # 1. 发送结构化表格
                title = content[:30] if len(content) <= 30 else content[:30] + "..."
                table_data = DBQueryService.to_structured_table(result, title=title)
                if table_data:
                    self.write_message({"type": "table", "data": table_data})

                # 2. 发送简要文字总结
                count = result.get("count", 0)
                summary = f"查询完成，共返回 {count} 条结果。具体数据请查看上方表格。"
                self.write_message({"type": "stream", "data": summary})

                # 3. 持久化（结构化 + 文本）
                if self.conversation_id:
                    ConversationRepository.add_message(self.conversation_id, "assistant",
                        json.dumps({"text": summary, "table": table_data}, ensure_ascii=False))
            else:
                error_text = f"数据库查询失败: {result.get('error', '未知错误')}"
                self.write_message({"type": "error", "data": error_text})
                if self.conversation_id:
                    ConversationRepository.add_message(self.conversation_id, "assistant", error_text)

            elapsed_time = round(time.time() - start_time, 2)
            self.write_message({"type": "metadata", "data": {"time": elapsed_time}})
            self.write_message({"type": "done"})
        except Exception as e:
            error_msg = f"数据库查询错误: {str(e)}"
            self.write_message({"type": "error", "data": error_msg})
            self.handle_general_chat(content)

    def handle_report_generation(self, content):
        start_time = time.time()

        try:
            self.write_message({"type": "typing", "data": "正在生成报表..."})

            result = ReportService.generate_report(content)

            if result.get("success", False):
                chart_type = result.get("chart_type", "bar")
                option = result.get("option", {})
                data = result.get("data", [])
                columns = result.get("columns", [])

                # 1. 发送图表
                self.write_message({"type": "chart", "data": {"chart_type": chart_type, "option": option}})

                # 2. 发送数据表格（图表下方）
                table_data = DBQueryService.to_structured_table(
                    {"success": True, "columns": columns, "results": data, "count": len(data)},
                    title=content[:30]
                )
                if table_data:
                    self.write_message({"type": "table", "data": table_data})

                # 3. 持久化
                if self.conversation_id:
                    ConversationRepository.add_message(self.conversation_id, "assistant",
                        json.dumps({"text": f"报表生成成功: {content}", "chart": {"chart_type": chart_type, "option": option}, "table": table_data}, ensure_ascii=False))

                elapsed_time = round(time.time() - start_time, 2)
                token_count = len(str(option)) // 4
                self.write_message({"type": "metadata", "data": {"time": elapsed_time, "tokens": token_count}})
                self.write_message({"type": "done"})
            else:
                ai_response = f"报表生成失败: {result.get('error', '未知错误')}"
                if self.conversation_id:
                    ConversationRepository.add_message(self.conversation_id, "assistant", ai_response)
                self.write_message({"type": "stream", "data": ai_response})
                self.write_message({"type": "done"})
        except Exception as e:
            error_msg = f"报表生成错误: {str(e)}"
            self.write_message({"type": "error", "data": error_msg})
            self.handle_general_chat(content)

    def handle_data_search(self, content):
        start_time = time.time()

        try:
            self.write_message({"type": "typing", "data": "正在数据仓库中搜索..."})

            keyword = content
            result = DBQueryService.search_data_warehouse(keyword)

            if result.get("success", False):
                # 1. 发送结构化表格
                table_data = DBQueryService.to_structured_table(result, title=f"搜索: {content[:25]}")
                if table_data:
                    self.write_message({"type": "table", "data": table_data})

                # 2. 简要总结
                count = result.get("count", 0)
                summary = f"在数据仓库中找到 {count} 条与「{content}」相关的结果。"
                self.write_message({"type": "stream", "data": summary})

                # 3. 持久化
                if self.conversation_id:
                    ConversationRepository.add_message(self.conversation_id, "assistant",
                        json.dumps({"text": summary, "table": table_data}, ensure_ascii=False))
            else:
                error_text = f"数据搜索失败: {result.get('error', '未知错误')}"
                self.write_message({"type": "error", "data": error_text})
                if self.conversation_id:
                    ConversationRepository.add_message(self.conversation_id, "assistant", error_text)

            elapsed_time = round(time.time() - start_time, 2)
            self.write_message({"type": "metadata", "data": {"time": elapsed_time}})
            self.write_message({"type": "done"})
        except Exception as e:
            error_msg = f"数据搜索错误: {str(e)}"
            self.write_message({"type": "error", "data": error_msg})
            self.handle_general_chat(content)

    def handle_data_analysis(self, content):
        start_time = time.time()

        try:
            self.write_message({"type": "typing", "data": "正在进行深度数据分析..."})

            query_result = DBQueryService.query(content)

            if query_result.get("success", False):
                analysis_result = DBQueryService.analyze_data(content, query_result)
                ai_analysis = analysis_result.get("analysis", "")

                if analysis_result.get("success", False) and ai_analysis:
                    # 构建 analysis_card 消息
                    card_data = {
                        "title": content[:30] if len(content) <= 30 else content[:30] + "...",
                        "analysis_text": ai_analysis,
                        "insights": analysis_result.get("insights", []),
                        "table": analysis_result.get("table_data"),
                        "chart": analysis_result.get("chart_data")
                    }
                    self.write_message({"type": "analysis_card", "data": card_data})

                    # 持久化
                    if self.conversation_id:
                        ConversationRepository.add_message(self.conversation_id, "assistant",
                            json.dumps({"analysis_card": card_data}, ensure_ascii=False))
                else:
                    self.write_message({"type": "stream", "data": ai_analysis or "分析完成但无结果。"})
            else:
                error_text = f"数据分析失败: {query_result.get('error', '未知错误')}"
                self.write_message({"type": "error", "data": error_text})
                if self.conversation_id:
                    ConversationRepository.add_message(self.conversation_id, "assistant", error_text)

            elapsed_time = round(time.time() - start_time, 2)
            self.write_message({"type": "metadata", "data": {"time": elapsed_time}})
            self.write_message({"type": "done"})
        except Exception as e:
            error_msg = f"数据分析错误: {str(e)}"
            self.write_message({"type": "error", "data": error_msg})
            self.handle_general_chat(content)

    def handle_relationship_mining(self, content):
        start_time = time.time()

        try:
            self.write_message({"type": "typing", "data": "正在挖掘数据关系..."})

            model = self._get_model()
            if not model:
                ai_response = "关系挖掘需要配置大模型服务，请联系管理员。"
                ConversationRepository.add_message(self.conversation_id, "assistant", ai_response)
                self.write_message({"type": "stream", "data": ai_response})
                self.write_message({"type": "done"})
                return
            
            summary = DBQueryService.get_data_summary()
            data_str = json.dumps(summary, ensure_ascii=False, indent=2)
            
            system_prompt = """你是一个专业的数据关系挖掘助手。请根据系统数据摘要，分析数据之间的关系，并生成数据关系图谱描述。

分析要求：
1. 分析各数据实体之间的关联关系
2. 识别数据模式和趋势
3. 生成数据关系图谱的文字描述
4. 提供数据洞察和业务建议

请用中文输出详细的分析报告。"""
            
            user_prompt = f"""用户问题：{content}

系统数据摘要：
{data_str}

请分析数据关系并生成图谱描述："""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            result = AIModelService.chat_completion(model, messages, stream=False)
            
            if "choices" in result and result["choices"]:
                ai_response = result["choices"][0]["message"]["content"]
            else:
                ai_response = "关系挖掘失败，请稍后重试。"
            
            ConversationRepository.add_message(self.conversation_id, "assistant", ai_response)
            
            elapsed_time = round(time.time() - start_time, 2)
            token_count = len(ai_response) // 4
            
            self.write_message({"type": "stream", "data": ai_response})
            self.write_message({"type": "metadata", "data": {"time": elapsed_time, "tokens": token_count}})
            self.write_message({"type": "done"})
        except Exception as e:
            error_msg = f"关系挖掘错误: {str(e)}"
            self.write_message({"type": "error", "data": error_msg})
            self.handle_general_chat(content)

    def _get_model(self, model_id=None):
        """获取模型：优先使用指定的 model_id，其次使用 WebSocket 选中的模型，最后使用默认模型"""
        model = None
        if model_id:
            model = AIModelRepository.get_model_by_id(int(model_id))
        if not model and self.selected_model_id:
            model = AIModelRepository.get_model_by_id(int(self.selected_model_id))
        if not model:
            model = AIModelRepository.get_default_model()
        return model

    def _build_chat_messages(self):
        """构建 messages 数组：system prompt + 对话历史。
        handle_message() 已先将用户消息写入 DB，所以 get_messages() 已包含当前问题。
        """
        SYSTEM_PROMPT = (
            "你是智能问数助手，一个专业的数据分析和查询助手。"
            "你可以帮助用户查询数据库、分析数据、生成报表、搜索信息。"
            "请用中文回复，保持专业、准确、简洁。"
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if self.conversation_id:
            history = ConversationRepository.get_messages(self.conversation_id)
            MAX_HISTORY = 30
            if len(history) > MAX_HISTORY:
                history = history[-MAX_HISTORY:]
            messages.extend(history)

        return messages

    def handle_general_chat(self, content, model_id=None):
        start_time = time.time()

        try:
            model = self._get_model(model_id)
            if not model:
                fallback = (
                    f"您好！我是智能问数助手。您的问题是：\"{content}\"\n\n"
                    f"由于尚未配置大模型服务，我暂时无法为您提供完整的AI分析。"
                    f"请联系管理员配置模型引擎后，我将能为您提供更强大的智能分析能力！"
                )
                if self.conversation_id:
                    ConversationRepository.add_message(self.conversation_id, "assistant", fallback)
                self.write_message({"type": "stream", "data": fallback})
                self.write_message({"type": "done"})
                return

            messages = self._build_chat_messages()

            # 通知前端创建流式消息气泡
            self.write_message({"type": "stream_start"})

            full_response = ""
            token_count = 0
            stream_failed = False

            try:
                stream_gen = AIModelService.chat_completion(model, messages, stream=True)
                for chunk in stream_gen:
                    if "choices" in chunk and chunk["choices"]:
                        delta = chunk["choices"][0].get("delta", {})
                        content_piece = delta.get("content", "")
                        if content_piece:
                            full_response += content_piece
                            self.write_message({"type": "stream_chunk", "data": content_piece})
                    if "usage" in chunk:
                        token_count = chunk["usage"].get("completion_tokens", 0)
            except Exception:
                # 流式失败时回退到非流式
                stream_failed = True
                result = AIModelService.chat_completion(model, messages, stream=False)
                if isinstance(result, dict) and "choices" in result and result["choices"]:
                    full_response = result["choices"][0]["message"]["content"]
                    token_count = result.get("usage", {}).get("completion_tokens", 0)
                    # 使用 stream_chunk 填充已有的流式气泡，避免空消息残留
                    self.write_message({"type": "stream_chunk", "data": full_response})
                else:
                    self.write_message({"type": "error", "data": "AI 响应失败，请稍后重试。"})
                    self.write_message({"type": "done"})
                    return

            # 持久化助手回复
            if self.conversation_id and full_response:
                ConversationRepository.add_message(self.conversation_id, "assistant", full_response)

            # 更新 token 统计
            if model.get("id") and token_count:
                try:
                    AIModelRepository.update_tokens(model["id"], 0, token_count)
                except Exception:
                    pass

            elapsed_time = round(time.time() - start_time, 2)
            self.write_message({"type": "metadata", "data": {"time": elapsed_time, "tokens": token_count or len(full_response) // 4}})
            self.write_message({"type": "done"})

        except Exception as e:
            error_msg = f"AI 响应错误: {str(e)}"
            self.write_message({"type": "error", "data": error_msg})

    def generate_ai_response(self, content):
        model = self._get_model()
        
        if not model:
            return f"您好！我是智能问数助手。您的问题是：\"{content}\"\n\n由于尚未配置大模型服务，我暂时无法为您提供完整的AI分析。请联系管理员配置模型引擎后，我将能为您提供更强大的智能分析能力！", 0
        
        try:
            messages = [{"role": "user", "content": content}]
            result = AIModelService.chat_completion(model, messages, stream=False)
            
            if isinstance(result, dict) and "error" in result:
                err = result["error"]
                if isinstance(err, dict):
                    error_msg = err.get("message", str(err))
                else:
                    error_msg = str(err)
                if "Authentication" in error_msg or "api key" in error_msg.lower() or "invalid" in error_msg.lower():
                    return f"AI 响应失败：API Key 无效或认证失败。请检查模型配置中的 API Key 是否正确。\n\n错误详情：{error_msg}\n\n您的问题是：\"{content}\"", 0
                return f"AI 响应失败：{error_msg}\n\n您的问题是：\"{content}\"", 0
            
            if "choices" in result and result["choices"]:
                ai_response = result["choices"][0]["message"]["content"]
                token_count = result.get("usage", {}).get("completion_tokens", len(ai_response) // 4)
                
                if model.get("id"):
                    AIModelRepository.update_tokens(
                        model["id"],
                        result.get("usage", {}).get("prompt_tokens", 0),
                        result.get("usage", {}).get("completion_tokens", 0)
                    )
                
                return ai_response, token_count
            else:
                return f"AI 响应失败，请检查模型配置。", 0
        except Exception as e:
            error_str = str(e)
            if "401" in error_str or "Authentication" in error_str:
                return f"AI 响应失败：API Key 无效或认证失败。请检查模型配置中的 API Key 是否正确。\n\n错误详情：{error_str}\n\n您的问题是：\"{content}\"", 0
            return f"调用大模型时发生错误: {error_str}\n\n您的问题是：\"{content}\"", 0

    def on_close(self):
        pass

    def check_origin(self, origin):
        return True


class TTSHandler(BaseHandler):
    @tornado.web.authenticated
    async def post(self):
        try:
            data = json.loads(self.request.body)
            text = data.get("text", "")
            
            if not text:
                self.write(json.dumps({"success": False, "message": "请输入要合成的文本"}))
                return

            try:
                import edge_tts
                communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
                audio_data = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data += chunk["data"]
                
                audio_base64 = base64.b64encode(audio_data).decode("utf-8")
                self.write(json.dumps({"success": True, "audio": audio_base64}))
            except Exception as e:
                print(f"[TTS] 语音合成失败: {e}", flush=True)
                self.write(json.dumps({"success": False, "message": f"语音合成失败: {str(e)}"}))
        except json.JSONDecodeError:
            self.write(json.dumps({"success": False, "message": "请求格式错误"}))
