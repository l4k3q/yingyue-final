import json
import re

from app.models.model import AIModelRepository, AIModelService


class IntentService:
    INTENT_TYPES = {
        "database_query": "数据库查询",
        "digital_employee": "数字员工调用",
        "report_generation": "报表生成",
        "data_search": "数据搜索",
        "data_analysis": "数据分析",
        "relationship_mining": "关系挖掘",
        "general_chat": "普通聊天"
    }

    @staticmethod
    def recognize(content: str) -> dict:
        if not content or not content.strip():
            return {"intent": "general_chat", "confidence": 0.0, "params": {}}

        content = content.strip()

        employee_match = re.match(r"@(\w+)", content)
        if employee_match:
            return {
                "intent": "digital_employee",
                "confidence": 1.0,
                "params": {
                    "employee_name": employee_match.group(1),
                    "args": content[len(employee_match.group(0)):].strip()
                }
            }

        keywords = {
            "database_query": [
                "查询", "统计", "有多少", "多少条", "数据", "记录", "总数",
                "列表", "排行", "排名", "汇总", "统计数据", "数据库",
                "有多少个", "多少个", "数量", "个数", "总计", "合计"
            ],
            "report_generation": [
                "报表", "图表", "趋势", "可视化", "图", "折线图", "柱状图",
                "饼图", "分析", "对比", "趋势图", "报表分析", "生成报表",
                "数据可视化", "数据图表", "展示", "呈现", "画图", "统计图"
            ],
            "data_search": [
                "搜索", "查找", "查询", "包含", "关于", "相关", "搜索数据",
                "查找数据", "搜索信息", "查找信息", "内容", "关键词",
                "搜索结果", "检索", "搜索记录", "查找记录"
            ],
            "data_analysis": [
                "分析", "对比", "比较", "评估", "趋势", "预测", "洞察",
                "分析报告", "数据分析", "数据洞察", "趋势分析", "对比分析",
                "深度分析", "综合分析", "统计分析", "业务分析", "解读"
            ],
            "relationship_mining": [
                "关系", "关联", "联系", "挖掘", "图谱", "网络", "关系图",
                "关联分析", "关系挖掘", "数据关系", "实体关系", "关系网络",
                "关联图谱", "知识图谱", "数据图谱"
            ]
        }

        scores = {}
        for intent, kw_list in keywords.items():
            scores[intent] = sum(1 for kw in kw_list if kw in content)

        max_score = max(scores.values())
        
        if max_score == 0:
            return {"intent": "general_chat", "confidence": 0.95, "params": {"question": content}}

        top_intents = [intent for intent, score in scores.items() if score == max_score]

        intent_priority = ["relationship_mining", "report_generation", "data_analysis", "data_search", "database_query"]
        for intent in intent_priority:
            if intent in top_intents:
                confidence = min(0.9, max_score * 0.25)
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "params": {"question": content}
                }

        return {"intent": "database_query", "confidence": min(0.85, max_score * 0.2), "params": {"question": content}}

    @staticmethod
    def recognize_with_llm(content: str) -> dict:
        model = AIModelRepository.get_default_model()
        if not model:
            return IntentService.recognize(content)

        system_prompt = """你是一个专业的意图识别助手。请分析用户输入，判断其意图类型，并返回JSON格式结果。

可用意图类型：
- database_query: 用户想要查询数据库中的数据，如统计、查询记录数、获取列表等
- digital_employee: 用户想要调用数字员工（以@开头）
- report_generation: 用户想要生成数据报表或可视化图表
- data_search: 用户想要在数据仓库中搜索特定内容
- data_analysis: 用户想要对数据进行深度分析，包括趋势分析、对比分析等
- relationship_mining: 用户想要挖掘数据之间的关系或生成数据图谱
- general_chat: 普通聊天对话，不涉及数据查询或分析

意图识别规则：
1. 如果用户输入以@开头，意图应为digital_employee
2. 如果用户询问数据统计、查询列表、获取记录数等，意图应为database_query
3. 如果用户要求生成图表、报表、可视化等，意图应为report_generation
4. 如果用户搜索特定内容、查找相关信息等，意图应为data_search
5. 如果用户要求深度分析、趋势分析、对比分析等，意图应为data_analysis
6. 如果用户询问数据关系、关联分析、图谱等，意图应为relationship_mining
7. 其他情况意图为general_chat

请严格按照以下JSON格式返回，不要包含任何额外内容：
{
    "intent": "意图类型",
    "confidence": 0.0-1.0之间的置信度,
    "params": {
        "question": "原始问题",
        "entities": ["识别到的实体列表"],
        "action": "具体操作描述",
        "target_table": "目标表名（如果能识别）",
        "analysis_type": "分析类型（统计/趋势/对比/分布/排名/详情）"
    }
}"""

        user_prompt = f"<user_input>{content}</user_input>"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            result = AIModelService.chat_completion(model, messages, stream=False)
            if "choices" in result and result["choices"]:
                response_text = result["choices"][0]["message"]["content"]
                try:
                    json_match = re.search(r'\{[\s\S]*\}', response_text)
                    if json_match:
                        intent_data = json.loads(json_match.group())
                        
                        if intent_data.get("intent") == "digital_employee":
                            employee_match = re.match(r"@(\S+)", content)
                            if employee_match:
                                intent_data["params"]["employee_name"] = employee_match.group(1)
                                intent_data["params"]["args"] = content[len(employee_match.group(0)):].strip()
                        
                        return intent_data
                except json.JSONDecodeError:
                    pass

            return IntentService.recognize(content)
        except Exception:
            return IntentService.recognize(content)