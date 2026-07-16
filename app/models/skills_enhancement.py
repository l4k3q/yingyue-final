"""
Skills 增强引擎
- 配置驱动的增强逻辑管理
- 动态加载 Skills 增强配置
- 至少完成：采集数据自动清洗增强（瞭望采集类技能）
- 预留扩展入口，支持新增多套独立增强模块

增强类型（enhancement_type）：
  - data_clean:   采集数据自动清洗（HTML去标签、文本规范化、关键词过滤）
  - context_augment: 问答上下文检索增强（知识库检索、同义词扩展）
  - data_visualize: 可视化预处理增强（数据聚合、格式转换）

设计原则：
  1. 每个增强模块独立、互不冲突
  2. 配置通过后台 JSON 可视化编辑，无需修改代码
  3. 运行时自动加载最新配置
"""
import json
import re
import html as html_module


class SkillsEnhancementEngine:
    """技能增强引擎 - 动态加载、执行增强逻辑"""

    # 已注册的增强处理器
    _enhancers = {}

    @classmethod
    def register(cls, enhancement_type: str, handler):
        """注册增强处理器"""
        cls._enhancers[enhancement_type] = handler

    @classmethod
    def get_enhancer(cls, enhancement_type: str):
        """获取增强处理器"""
        return cls._enhancers.get(enhancement_type)

    @classmethod
    def run_enhancement(cls, skill: dict, data: any, context: dict = None) -> dict:
        """
        对指定技能执行增强逻辑
        Returns: {"enhanced": data, "meta": {...}}
        """
        try:
            enhancement_config = json.loads(skill.get("enhancement_config", "{}"))
        except json.JSONDecodeError:
            enhancement_config = {}

        enhancement_type = enhancement_config.get("enhancement_type", "")
        enabled = enhancement_config.get("enabled", False)

        if not enabled or not enhancement_type:
            return {"enhanced": data, "meta": {"enhanced": False, "reason": "未启用或无增强类型"}}

        handler = cls.get_enhancer(enhancement_type)
        if not handler:
            return {"enhanced": data, "meta": {"enhanced": False, "reason": f"未注册的增强类型: {enhancement_type}"}}

        return handler(data, enhancement_config, context or {})

    @classmethod
    def run_enhancements_for_employee(cls, employee_id: int, data: any,
                                       context: dict = None) -> dict:
        """
        执行指定员工的所有已绑定技能的增强逻辑
        多个增强按顺序管道化执行
        """
        from app.models.skills import SkillRepository
        skills = SkillRepository.get_skills_by_employee(employee_id)
        if not skills:
            return {"enhanced": data, "meta": {"enhanced": False, "reason": "该员工未绑定技能"}}

        meta = {"applied_skills": [], "enhanced": True}
        for skill in skills:
            result = cls.run_enhancement(skill, data, context)
            data = result["enhanced"]
            if result.get("meta", {}).get("enhanced"):
                meta["applied_skills"].append(skill["name"])
            meta[f"skill_{skill['id']}_detail"] = result.get("meta", {})

        return {"enhanced": data, "meta": meta}

    @classmethod
    def run_enhancements_by_category(cls, category: int, data: any,
                                      context: dict = None) -> dict:
        """按技能分类执行所有启用中的增强逻辑"""
        from app.models.skills import SkillRepository
        import json as _json
        skills, _ = SkillRepository.get_skills(page=1, page_size=1000,
                                               category=category, status=1)
        if not skills:
            return {"enhanced": data, "meta": {"enhanced": False, "reason": "无启用技能"}}

        meta = {"applied_skills": [], "enhanced": True}
        for skill in skills:
            try:
                ec = _json.loads(skill.get("enhancement_config", "{}"))
            except _json.JSONDecodeError:
                ec = {}
            if not ec.get("enabled"):
                continue
            result = cls.run_enhancement(skill, data, context)
            data = result["enhanced"]
            if result.get("meta", {}).get("enhanced"):
                meta["applied_skills"].append(skill["name"])
        return {"enhanced": data, "meta": meta}


# ============== 内置增强处理器 ==============

def data_clean_enhancer(data: any, config: dict, context: dict) -> dict:
    """
    采集数据自动清洗增强
    配置项（enhancement_config JSON）：
    {
      "enabled": true,
      "enhancement_type": "data_clean",
      "strip_html": true,          // 去除 HTML 标签
      "normalize_whitespace": true, // 规范化空白字符
      "filter_keywords": ["广告", "推广"],   // 过滤关键词列表
      "min_length": 10,            // 内容最小长度（字符）
      "deduplicate": true,         // 去重（基于文本相似度）
      "extract_entities": false    // 实体提取（预留）
    }
    """
    result = data
    stats = {"original_len": 0, "cleaned_len": 0, "stripped_html": False,
             "filtered": False, "normalized": False}

    # 处理文本数据
    if isinstance(data, str):
        original = data
        stats["original_len"] = len(original)

        # 1. HTML 标签清除
        if config.get("strip_html", True):
            cleaned = re.sub(r'<[^>]+>', '', original)
            if cleaned != original:
                stats["stripped_html"] = True
            result = cleaned
        else:
            result = original

        # 2. HTML 实体解码
        result = html_module.unescape(result)

        # 3. 空白字符规范化
        if config.get("normalize_whitespace", True):
            # 合并连续空白为单个空格
            cleaned = re.sub(r'\s+', ' ', result)
            # 去除首尾空白
            cleaned = cleaned.strip()
            if cleaned != result:
                stats["normalized"] = True
            result = cleaned

        # 4. 过滤关键词
        filter_keywords = config.get("filter_keywords", [])
        if filter_keywords:
            for kw in filter_keywords:
                if kw and kw in result:
                    stats["filtered"] = True
                    result = f"[已过滤含'{kw}'的内容] {result[:200]}"
                    break

        # 5. 内容长度检查
        min_length = config.get("min_length", 0)
        if min_length > 0 and len(result) < min_length:
            if len(result.strip()) == 0:
                result = "[空内容]"
            else:
                result = f"[短内容({len(result)}字)] {result}"

        stats["cleaned_len"] = len(result)

    # 处理列表数据（如文章列表）
    elif isinstance(data, list):
        cleaned_list = []
        seen = set()
        for item in data:
            if isinstance(item, dict):
                # 递归清洗每个字段
                cleaned_item = {}
                for k, v in item.items():
                    field_result = data_clean_enhancer(v if isinstance(v, str) else str(v),
                                                       config, context)
                    cleaned_item[k] = field_result["enhanced"]
                # 去重
                if config.get("deduplicate", True):
                    fingerprint = json.dumps(cleaned_item, sort_keys=True, ensure_ascii=False)
                    if fingerprint in seen:
                        continue
                    seen.add(fingerprint)
                cleaned_list.append(cleaned_item)
            else:
                cleaned_list.append(item)
        result = cleaned_list
        stats["original_len"] = len(data)
        stats["cleaned_len"] = len(cleaned_list)
        if len(cleaned_list) < len(data):
            stats["deduplicated"] = len(data) - len(cleaned_list)

    return {"enhanced": result, "meta": {"enhanced": True, "type": "data_clean", "stats": stats}}


def context_augment_enhancer(data: any, config: dict, context: dict) -> dict:
    """
    问答上下文检索增强
    配置项：
    {
      "enabled": true,
      "enhancement_type": "context_augment",
      "prepend_context": "你是一个数据分析专家。",  // 前置上下文
      "synonym_dict": {"天气": ["气象", "气温"]},   // 同义词扩展
      "max_history": 5                              // 最大历史轮次
    }
    """
    result = data
    augments = []

    if isinstance(data, str):
        # 1. 添加前置上下文
        prepend = config.get("prepend_context", "")
        if prepend:
            result = prepend + "\n\n" + data
            augments.append("prepend_context")

        # 2. 同义词扩展（在用户输入中替换）
        synonym_dict = config.get("synonym_dict", {})
        if synonym_dict:
            for original, synonyms in synonym_dict.items():
                if original in result:
                    expanded = f"{result} (扩展关键词: {', '.join(synonyms)})"
                    result = expanded
                    augments.append("synonym_expand")
                    break

    return {"enhanced": result, "meta": {"enhanced": True, "type": "context_augment",
                                          "augments": augments}}


def data_visualize_enhancer(data: any, config: dict, context: dict) -> dict:
    """
    可视化预处理增强
    配置项：
    {
      "enabled": true,
      "enhancement_type": "data_visualize",
      "aggregate": true,           // 数据聚合
      "format": "chart_ready",     // 输出格式
      "max_points": 50             // 最大数据点
    }
    """
    result = data
    if isinstance(data, list) and len(data) > config.get("max_points", 50):
        # 采样
        step = max(1, len(data) // config.get("max_points", 50))
        result = [data[i] for i in range(0, len(data), step)][:config.get("max_points", 50)]

    return {"enhanced": result, "meta": {"enhanced": True, "type": "data_visualize"}}


# ============== 注册内置增强处理器 ==============
SkillsEnhancementEngine.register("data_clean", data_clean_enhancer)
SkillsEnhancementEngine.register("context_augment", context_augment_enhancer)
SkillsEnhancementEngine.register("data_visualize", data_visualize_enhancer)


# ============== 内置默认技能种子数据 ==============
DEFAULT_SKILLS = [
    {
        "name": "采集数据自动清洗",
        "category": 1,  # 瞭望采集
        "description": "自动清洗瞭望采集的原始网页数据，去除HTML标签、广告内容、空白干扰，保留有效信息",
        "config_json": json.dumps({"tools": ["html_strip", "whitespace_normalize", "keyword_filter"]}),
        "enhancement_config": json.dumps({
            "enabled": True,
            "enhancement_type": "data_clean",
            "strip_html": True,
            "normalize_whitespace": True,
            "filter_keywords": ["广告", "推广", "Sponsored"],
            "min_length": 10,
            "deduplicate": True,
            "extract_entities": False
        }, ensure_ascii=False)
    },
    {
        "name": "问答上下文增强",
        "category": 2,  # 问数分析
        "description": "在问数对话中自动注入领域知识上下文、同义词扩展，提升大模型回答准确性",
        "config_json": json.dumps({"tools": ["context_inject", "synonym_expand"]}),
        "enhancement_config": json.dumps({
            "enabled": True,
            "enhancement_type": "context_augment",
            "prepend_context": "你是一个专业的智能数据分析助手，请基于数据事实给出准确回答。",
            "synonym_dict": {
                "数据": ["信息", "资料"],
                "分析": ["洞察", "解读"],
                "报表": ["报告", "图表"],
            },
            "max_history": 5
        }, ensure_ascii=False)
    },
    {
        "name": "可视化数据预处理",
        "category": 3,  # 可视化大屏
        "description": "对大屏展示数据进行聚合采样、格式标准化，确保可视化组件渲染效率与数据一致性",
        "config_json": json.dumps({"tools": ["aggregate", "sample", "format"]}),
        "enhancement_config": json.dumps({
            "enabled": True,
            "enhancement_type": "data_visualize",
            "aggregate": True,
            "format": "chart_ready",
            "max_points": 50
        }, ensure_ascii=False)
    },
]


def seed_default_skills():
    """初始化默认技能数据（如果不存在）"""
    from app.models.skills import SkillRepository
    from app.models.db import get_connection
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM skills")
        if cursor.fetchone()[0] == 0:
            for skill_data in DEFAULT_SKILLS:
                SkillRepository.create_skill(
                    name=skill_data["name"],
                    category=skill_data["category"],
                    description=skill_data["description"],
                    config_json=skill_data["config_json"],
                    enhancement_config=skill_data["enhancement_config"]
                )
            return True
    return False
