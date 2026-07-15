import json
import re
import time

import tornado.websocket

from app.controllers.base import BaseHandler
from app.models.user import UserRepository
from app.models.conversations import ConversationRepository
from app.models.digital_employee import DigitalEmployeeService, DigitalEmployeeRepository
from app.models.model import AIModelRepository, AIModelService
from app.models.intent import IntentService
from app.models.db_query import DBQueryService
from app.models.report import ReportService


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
        self.write(json.dumps({
            "success": True,
            "models": model_list
        }))


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
                self.handle_message(msg_data)
            elif msg_type == "new_conversation":
                self.handle_new_conversation()
            elif msg_type == "load_conversation":
                self.handle_load_conversation(data.get("conversation_id"))
            elif msg_type == "delete_conversation":
                self.handle_delete_conversation(data.get("conversation_id"))
            elif msg_type == "ping":
                self.write_message({"type": "pong"})
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

    def handle_message(self, content):
        if not content or not self.user_id:
            return
        
        if not self.conversation_id:
            self.conversation_id = ConversationRepository.create_conversation(self.user_id, content[:30] if len(content) > 30 else content)
        
        ConversationRepository.add_message(self.conversation_id, "user", content)
        
        intent_result = IntentService.recognize_with_llm(content)
        intent = intent_result.get("intent", "general_chat")
        confidence = intent_result.get("confidence", 0.0)
        params = intent_result.get("params", {})
        
        self.write_message({"type": "typing", "data": f"正在分析意图: {IntentService.INTENT_TYPES.get(intent, intent)}..."})
        
        if intent == "digital_employee":
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
            self.handle_general_chat(content)

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
            result = DigitalEmployeeService.execute(employee, {"query": args, "city": args.split()[-1] if args else ""})
            
            if result.get("success", False):
                content = result.get("content", "")
                card_template = employee.get("card_template", "")
                
                if card_template and isinstance(content, dict):
                    try:
                        ai_response = card_template.format(**content)
                    except KeyError:
                        ai_response = json.dumps(content, ensure_ascii=False, indent=2)
                elif isinstance(content, dict):
                    ai_response = json.dumps(content, ensure_ascii=False, indent=2)
                else:
                    ai_response = str(content)
            else:
                ai_response = f"调用 @{employee_name} 失败: {result.get('error', '未知错误')}"
            
            elapsed_time = round(time.time() - start_time, 2)
            token_count = len(ai_response) // 4
            
            if self.conversation_id:
                ConversationRepository.add_message(self.conversation_id, "user", f"@{employee_name} {args}" if args else f"@{employee_name}")
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
                formatted_result = DBQueryService.format_results(result)
                ai_response = f"数据库查询结果：\n\n{formatted_result}"
            else:
                ai_response = f"数据库查询失败: {result.get('error', '未知错误')}"
            
            ConversationRepository.add_message(self.conversation_id, "assistant", ai_response)
            
            elapsed_time = round(time.time() - start_time, 2)
            token_count = len(ai_response) // 4
            
            self.write_message({"type": "stream", "data": ai_response})
            self.write_message({"type": "metadata", "data": {"time": elapsed_time, "tokens": token_count}})
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
                
                ConversationRepository.add_message(self.conversation_id, "assistant", f"报表生成成功: {content}")
                
                elapsed_time = round(time.time() - start_time, 2)
                token_count = len(str(option)) // 4
                
                self.write_message({"type": "chart", "data": {"chart_type": chart_type, "option": option}})
                self.write_message({"type": "metadata", "data": {"time": elapsed_time, "tokens": token_count}})
                self.write_message({"type": "done"})
            else:
                ai_response = f"报表生成失败: {result.get('error', '未知错误')}"
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
                formatted_result = DBQueryService.format_results(result)
                ai_response = f"数据搜索结果：\n\n{formatted_result}"
            else:
                ai_response = f"数据搜索失败: {result.get('error', '未知错误')}"
            
            ConversationRepository.add_message(self.conversation_id, "assistant", ai_response)
            
            elapsed_time = round(time.time() - start_time, 2)
            token_count = len(ai_response) // 4
            
            self.write_message({"type": "stream", "data": ai_response})
            self.write_message({"type": "metadata", "data": {"time": elapsed_time, "tokens": token_count}})
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
                ai_response = analysis_result.get("analysis", DBQueryService.format_results(query_result))
            else:
                ai_response = f"数据分析失败: {query_result.get('error', '未知错误')}"
            
            ConversationRepository.add_message(self.conversation_id, "assistant", ai_response)
            
            elapsed_time = round(time.time() - start_time, 2)
            token_count = len(ai_response) // 4
            
            self.write_message({"type": "stream", "data": ai_response})
            self.write_message({"type": "metadata", "data": {"time": elapsed_time, "tokens": token_count}})
            self.write_message({"type": "done"})
        except Exception as e:
            error_msg = f"数据分析错误: {str(e)}"
            self.write_message({"type": "error", "data": error_msg})
            self.handle_general_chat(content)

    def _get_model(self):
        """Get the selected model, or fall back to the default model."""
        if self.selected_model_id:
            model = AIModelRepository.get_model_by_id(self.selected_model_id)
            if model and model.get("status") == 1:
                return model
        return AIModelRepository.get_default_model()

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

    def handle_general_chat(self, content):
        start_time = time.time()
        
        try:
            ai_response, token_count = self.generate_ai_response(content)
            
            ConversationRepository.add_message(self.conversation_id, "assistant", ai_response)
            
            elapsed_time = round(time.time() - start_time, 2)
            
            self.write_message({"type": "stream", "data": ai_response})
            self.write_message({"type": "metadata", "data": {"time": elapsed_time, "tokens": token_count}})
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
                error_msg = result["error"].get("message", str(result["error"]))
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