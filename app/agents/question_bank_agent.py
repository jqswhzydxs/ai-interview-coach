from collections.abc import Iterable

from app.agents.base import BaseAgent
from app.schemas.question import QuestionBank


class QuestionBankAgent(BaseAgent):
    name = "question_bank_agent"
    prompt_version = "question_bank_agent_v0.1"

    def __init__(
        self,
        *args,
        total_count: int = 25,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.total_count = total_count

    async def run(self, input_data: dict) -> dict:
        return await self.run_with_fallback(
            input_data,
            QuestionBank,
            lambda: self._rule_based_question_bank(input_data),
        )

    def _rule_based_question_bank(self, input_data: dict | None = None) -> dict:
        context = self._context(input_data or {})
        self_intro_count = 8
        professional_count = 8
        behavior_count = max(0, self.total_count - self_intro_count - professional_count)
        return {
            "self_intro_questions": [
                self._question(index, "self_intro", context)
                for index in range(self_intro_count)
            ],
            "professional_questions": [
                self._question(index, "professional", context)
                for index in range(professional_count)
            ],
            "behavior_project_questions": [
                self._question(index, "behavior_project", context)
                for index in range(behavior_count)
            ],
            "total_count": self.total_count,
        }

    def _context(self, input_data: dict) -> dict:
        resume = _dict(input_data.get("resume_profile"))
        jd = _dict(input_data.get("jd_profile"))
        match = _dict(input_data.get("match_report"))
        experiences = input_data.get("experience_profiles") or []

        resume_terms = _dedupe(
            [
                *_strings(resume.get("skills")),
                *_strings(resume.get("backend_tags")),
                *(
                    term
                    for project in resume.get("projects") or []
                    if isinstance(project, dict)
                    for term in _strings(project.get("tech_stack"))
                ),
            ]
        )
        jd_terms = _dedupe(
            [
                *_strings(jd.get("tech_keywords")),
                *_strings(jd.get("hard_requirements")),
            ]
        )
        technologies = _dedupe([*resume_terms, *jd_terms])[:8]
        priorities = _dedupe(
            [
                *_strings(match.get("preparation_priorities")),
                *_strings(match.get("missing_capabilities")),
                *_strings(jd.get("interview_focuses")),
            ]
        )[:6]
        experience_focuses = _dedupe(
            item
            for profile in experiences
            if isinstance(profile, dict)
            for key in ("frequent_topics", "frequent_questions")
            for item in _strings(profile.get(key))
        )[:4]
        goal = str(input_data.get("preparation_goal") or "").strip()[:120]
        source_refs = []
        if resume_terms:
            source_refs.append(
                {
                    "source_type": "resume",
                    "summary": f"简历技能：{', '.join(resume_terms[:5])}",
                }
            )
        if jd_terms:
            source_refs.append(
                {
                    "source_type": "jd",
                    "summary": f"岗位要求：{', '.join(jd_terms[:5])}",
                }
            )
        if experience_focuses:
            source_refs.append(
                {
                    "source_type": "experience",
                    "summary": "面经中的高频主题已纳入准备重点",
                }
            )
        if not source_refs:
            source_refs.append(
                {
                    "source_type": "inferred",
                    "summary": "降级生成未获得可识别的结构化技术上下文",
                }
            )
        return {
            "technologies": technologies,
            "jd_terms": jd_terms[:8],
            "priorities": priorities,
            "experience_focuses": experience_focuses,
            "goal": goal,
            "source_refs": source_refs,
        }

    def _question(self, index: int, module: str, context: dict) -> dict:
        module_prefix = {
            "self_intro": "self",
            "professional": "pro",
            "behavior_project": "beh",
        }[module]
        purpose = {
            "self_intro": "评估候选人能否以现有材料清晰说明岗位匹配度",
            "professional": "评估候选人对当前技术上下文的理解和取舍",
            "behavior_project": "评估候选人的协作、复盘和决策能力",
        }[module]
        return {
            "question_id": f"{module_prefix}-{index + 1:02d}",
            "module": module,
            "question_text": self._question_text(module, index, context),
            "purpose": purpose,
            "difficulty": "medium" if index % 3 else "basic",
            "source_type": "mixed" if len(context["source_refs"]) > 1 else context["source_refs"][0]["source_type"],
            "source_refs": context["source_refs"],
            "jd_keywords": context["jd_terms"],
            "answer_framework": "先给结论，再说明背景、行动、结果和反思；只使用真实经历。",
            "star_template": "Situation: 背景；Task: 目标；Action: 行动；Result: 结果。",
            "scoring_anchors": [
                {
                    "name": "relevance",
                    "score": 8,
                    "max_score": 10,
                    "reason": "回答应贴合题目和当前材料，不补造事实",
                }
            ],
            "follow_up_questions": ["哪些内容有材料证据，哪些只是你建议的方案？"],
            "preparation_advice": "选择一个真实例子，明确个人行动、取舍和可验证结果。",
            "sort_order": index + 1,
        }

    def _question_text(self, module: str, index: int, context: dict) -> str:
        technologies = context["technologies"] or ["当前岗位涉及的后端技术"]
        primary = technologies[0]
        secondary = technologies[1] if len(technologies) > 1 else primary
        tertiary = technologies[2] if len(technologies) > 2 else secondary
        priority = (context["priorities"] or ["当前岗位的核心能力"])[0]
        second_priority = (context["priorities"] or ["项目深度"])[-1]
        experience_focus = (context["experience_focuses"] or ["高频面试主题"])[0]
        goal = context["goal"] or "当前面试准备目标"

        templates = {
            "self_intro": [
                f"请概括你与 {primary} 相关的能力，并指出材料中的直接依据。",
                f"请说明你为什么适合这个岗位，并区分已具备能力与仍需准备的 {priority}。",
                f"请选择一段最能体现 {secondary} 能力的真实经历进行介绍；若材料没有该经历，请明确说明。",
                f"请用两分钟串联你的技术成长路径，重点解释 {primary} 与 {secondary} 如何形成互补。",
                f"请从岗位要求出发介绍你的优势，并说明一个与 {second_priority} 有关的能力缺口。",
                f"请介绍一次能体现工程质量意识的经历，说明你如何验证结果而不是只描述实现。",
                f"请面向不了解你背景的面试官解释你的职责边界，避免把团队成果全部归于个人。",
                f"请围绕“{goal}”组织开场介绍，并给出接下来希望被追问的一个主题。",
            ],
            "professional": [
                f"请解释 {primary} 在你的当前技术上下文中承担什么职责，以及它不应承担什么职责。",
                f"如果要用 {secondary} 设计一个后端能力，你会如何拆分接口、数据和失败处理？",
                f"遇到与 {tertiary} 有关的性能或稳定性问题时，你会按什么顺序定位并验证根因？",
                f"请比较 {primary} 与 {secondary} 在当前场景中的取舍，并说明选择标准。",
                f"针对岗位关注的“{priority}”，请给出一个可验证的设计方案和验收指标。",
                f"请说明你会如何为 {primary} 相关代码设计测试边界，覆盖正常、异常和并发场景。",
                f"围绕“{experience_focus}”，请解释常见失败模式、监控信号和恢复策略。",
                f"如果现有方案在流量或数据规模增长后失效，你会如何演进 {secondary} 相关设计并控制风险？",
            ],
            "behavior_project": [
                "请讲一次需求不清晰的经历：你如何澄清目标、记录假设并确认验收标准？",
                "请讲一次技术方案存在分歧的经历：你如何比较证据并推动团队达成决定？",
                "请讲一次交付受阻的经历：你如何暴露风险、调整范围并保持关键承诺？",
                "请讲一次你主动承担责任的经历：你的个人行动边界和最终结果分别是什么？",
                "请讲一次失败或返工的经历：根因是什么，你后来怎样修改流程避免重复发生？",
                "请讲一次跨角色协作的经历：你如何同步约束、处理依赖并验证对方理解？",
                "请讲一次在速度与质量之间做取舍的经历：当时的约束、选择和后果是什么？",
                "请讲一次快速学习陌生领域的经历：你如何验证所学内容能解决真实问题？",
                f"结合“{goal}”，请说明你下一次练习会改进什么、如何衡量是否真的进步。",
            ],
        }
        options = templates[module]
        if index < len(options):
            return options[index]
        return f"请围绕 {primary} 分析一个尚未覆盖的工程约束，并说明验证方法与风险边界。"


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
    return result
