import json
from app.models.db import get_connection


class SkillRepository:
    """技能管理仓库"""

    CATEGORY_MAP = {
        1: "瞭望采集",
        2: "问数分析",
        3: "可视化大屏",
    }

    @staticmethod
    def get_skills(page: int = 1, page_size: int = 20,
                   category: int = None, status: int = None,
                   keyword: str = None, employee_id: int = None):
        """分页查询技能列表，支持多条件筛选"""
        conditions = []
        params = []

        if category is not None:
            conditions.append("s.category=?")
            params.append(category)
        if status is not None:
            conditions.append("s.status=?")
            params.append(status)
        if keyword:
            conditions.append("s.name LIKE ?")
            params.append(f"%{keyword}%")
        if employee_id is not None:
            conditions.append("es.employee_id=?")
            params.append(employee_id)

        where = " AND ".join(conditions) if conditions else "1=1"
        offset = (page - 1) * page_size

        # 如果按 employee_id 筛选，需要 JOIN
        if employee_id is not None:
            base_from = "FROM skills s INNER JOIN employee_skills es ON s.id=es.skill_id"
            group_clause = "GROUP BY s.id"
        else:
            base_from = "FROM skills s"
            group_clause = ""

        with get_connection() as conn:
            cursor = conn.execute(
                f"SELECT COUNT(DISTINCT s.id) {base_from} WHERE {where}",
                params
            )
            total = cursor.fetchone()[0]

            cursor = conn.execute(
                f"""SELECT s.id, s.name, s.category, s.status, s.description,
                           s.config_json, s.enhancement_config,
                           s.created_at, s.updated_at,
                           (SELECT COUNT(*) FROM employee_skills WHERE skill_id=s.id) as employee_count
                    {base_from}
                    WHERE {where}
                    {group_clause}
                    ORDER BY s.updated_at DESC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset]
            )
            rows = cursor.fetchall()
        return [dict(r) for r in rows], total

    @staticmethod
    def get_skill_by_id(skill_id: int) -> dict | None:
        """获取单个技能详情"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM skills WHERE id=?", (skill_id,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_skill_detail(skill_id: int) -> dict | None:
        """获取技能详情（含绑定员工列表）"""
        skill = SkillRepository.get_skill_by_id(skill_id)
        if not skill:
            return None
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT de.id, de.name, de.code_name, de.type, de.status
                   FROM digital_employees de
                   INNER JOIN employee_skills es ON de.id=es.employee_id
                   WHERE es.skill_id=?""",
                (skill_id,)
            )
            skill["employees"] = [dict(r) for r in cursor.fetchall()]
        return skill

    @staticmethod
    def create_skill(name: str, category: int, description: str = "",
                     config_json: str = "{}", enhancement_config: str = "{}") -> int | None:
        """新增技能"""
        try:
            json.loads(config_json)
            json.loads(enhancement_config)
        except json.JSONDecodeError:
            return None
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO skills (name, category, description, config_json, enhancement_config)
                   VALUES (?,?,?,?,?)""",
                (name, category, description, config_json, enhancement_config)
            )
        return cursor.lastrowid

    @staticmethod
    def update_skill(skill_id: int, name: str = None, category: int = None,
                     description: str = None, status: int = None,
                     config_json: str = None, enhancement_config: str = None) -> bool:
        """编辑技能"""
        updates = []
        params = []

        if name is not None:
            updates.append("name=?")
            params.append(name)
        if category is not None:
            updates.append("category=?")
            params.append(category)
        if description is not None:
            updates.append("description=?")
            params.append(description)
        if status is not None:
            updates.append("status=?")
            params.append(status)
        if config_json is not None:
            try:
                json.loads(config_json)
            except json.JSONDecodeError:
                return False
            updates.append("config_json=?")
            params.append(config_json)
        if enhancement_config is not None:
            try:
                json.loads(enhancement_config)
            except json.JSONDecodeError:
                return False
            updates.append("enhancement_config=?")
            params.append(enhancement_config)

        if not updates:
            return True

        updates.append("updated_at=(datetime('now','localtime'))")
        params.append(skill_id)

        with get_connection() as conn:
            conn.execute(
                f"UPDATE skills SET {', '.join(updates)} WHERE id=?",
                params
            )
        return True

    @staticmethod
    def delete_skill(skill_id: int) -> bool:
        """删除技能（仅解绑关联，不级联删除员工）"""
        with get_connection() as conn:
            conn.execute("DELETE FROM employee_skills WHERE skill_id=?", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id=?", (skill_id,))
        return True

    @staticmethod
    def toggle_status(skill_id: int, status: int) -> bool:
        """启用/禁用技能"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE skills SET status=?, updated_at=(datetime('now','localtime')) WHERE id=?",
                (status, skill_id)
            )
        return True

    @staticmethod
    def get_skills_by_employee(employee_id: int) -> list:
        """获取指定员工绑定的技能列表"""
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT s.id, s.name, s.category, s.status, s.description,
                          s.config_json, s.enhancement_config
                   FROM skills s
                   INNER JOIN employee_skills es ON s.id=es.skill_id
                   WHERE es.employee_id=? AND s.status=1
                   ORDER BY s.name""",
                (employee_id,)
            )
            rows = cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def batch_assign_employees(skill_id: int, employee_ids: list) -> bool:
        """批量分配数字员工给技能（先清后插）"""
        if not employee_ids:
            return False
        with get_connection() as conn:
            conn.execute("DELETE FROM employee_skills WHERE skill_id=?", (skill_id,))
            for eid in employee_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO employee_skills (employee_id, skill_id) VALUES (?,?)",
                    (eid, skill_id)
                )
        return True

    @staticmethod
    def get_employee_skill_map() -> dict:
        """获取所有员工→技能映射（供技能增强引擎使用）"""
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT es.employee_id, s.id, s.name, s.category, s.config_json,
                          s.enhancement_config
                   FROM employee_skills es
                   INNER JOIN skills s ON es.skill_id=s.id
                   WHERE s.status=1"""
            )
            rows = cursor.fetchall()
        mapping = {}
        for r in rows:
            r = dict(r)
            eid = r["employee_id"]
            if eid not in mapping:
                mapping[eid] = []
            mapping[eid].append(r)
        return mapping

    @staticmethod
    def get_all_enabled_skills() -> list:
        """获取所有启用中的技能（供技能增强引擎动态加载）"""
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT s.*, GROUP_CONCAT(es.employee_id) as bound_employees
                   FROM skills s
                   LEFT JOIN employee_skills es ON s.id=es.skill_id
                   WHERE s.status=1
                   GROUP BY s.id"""
            )
            rows = cursor.fetchall()
        return [dict(r) for r in rows]
