"""Independent offline metadata candidate. It is not wired into any Agent."""

from dataclasses import dataclass
import re
import unicodedata

from app.agents.base import AgentOutputValidationError
from app.agents.question_bank_assembler import QuestionBankAssembler
from app.agents.question_metadata_rules import Topic, topics_for
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraftBank


TECH_PATTERNS = {
    "python": r"python", "fastapi": r"fastapi", "django": r"django", "flask": r"flask",
    "sqlalchemy": r"sqlalchemy", "pytest": r"pytest", "pydantic": r"pydantic",
    "gin": r"gin", "grpc": r"grpc", "java": r"java", "spring": r"spring(?:\s+boot)?",
    "postgresql": r"postgres(?:ql)?", "mysql": r"mysql", "redis": r"redis",
    "mongodb": r"mongodb", "kafka": r"kafka", "rabbitmq": r"rabbitmq",
    "docker": r"docker", "kubernetes": r"kubernetes", "rust": r"rust",
    "axum": r"axum", "sqlite": r"sqlite", "typescript": r"typescript",
    "javascript": r"javascript", "nodejs": r"node(?:\.js|js)", "express": r"express",
    "csharp": r"c#|csharp", "dotnet": r"\.net|dotnet", "aspnet": r"asp\.net",
    "ruby": r"ruby", "rails": r"rails", "elixir": r"elixir", "phoenix": r"phoenix",
}
SENSITIVE = re.compile(
    r"\bsk-[A-Za-z0-9_-]{6,}|\bbearer\s+\S+|authorization\s*[:=]|"
    r"api[_ -]?key\s*[:=]|password\s*[:=]|ignore\s+(?:all\s+)?previous|"
    r"system\s+prompt\s*[:=]|<script", re.I,
)
SECRET_REQUEST = re.compile(
    r"\b(?:reveal|print|output|show)\s+(?:me\s+)?(?:the\s+)?(?:actual\s+|raw\s+)?"
    r"(?:api.?key|authorization\s+(?:header|value)|secret\s+value|system\s+prompt)|"
    r"(?:输出|显示|泄露)(?:实际的|完整的|你的|我的)?(?:密钥|授权头|系统提示)", re.I,
)
STOPWORDS = frozenset("your about with that this from have would could what which when where how using used describe explain backend service project experience specific role technical current question work there been into their them they then than tell through after before during does should because only such more most also code each interview prepare engineering engineer development skills python java go rust".split())
OUTPUT_KEYS = {"self_intro": "self_intro_questions", "professional": "professional_questions", "behavior_project": "behavior_project_questions"}


def mentioned_technologies(value: str) -> set[str]:
    text = unicodedata.normalize("NFKC", value)
    found = {
        key for key, pattern in TECH_PATTERNS.items()
        if re.search(r"(?<![A-Za-z0-9_])(?:" + pattern + r")(?![A-Za-z0-9_])", text, re.I)
    }
    # Lower-case English 'go about' is not a language mention.
    if re.search(r"\b(?:Go|Golang|golang)\b|\bgoroutines?\b|\bgo\s+(?:language|code|service|backend|programming)\b", text):
        found.add("go")
    return found


def _safe_scalar(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        return None
    if SENSITIVE.search(value) or re.search(r"[\x00-\x08\x0b-\x1f]", value):
        return None
    return value.strip()


def unsafe_question(value: str) -> bool:
    if SENSITIVE.search(value):
        return True
    return any(
        not re.search(r"prevent|avoid|never|do\s+not|防止|避免|不要|禁止", value[max(0, m.start() - 30):m.start()], re.I)
        for m in SECRET_REQUEST.finditer(value)
    )


def _tokens(value: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-z][a-z0-9_-]{2,}", value.casefold())
        if word not in STOPWORDS
    }


@dataclass(frozen=True)
class Evidence:
    source_type: str
    path: str
    value: str
    kind: str

    def ref(self) -> dict:
        prefix = {
            "gap": "Matching capability gap; not evidence of completed work",
            "priority": "Matching preparation priority; not a new job requirement",
            "assessment": "Matching assessment; not independent proof of experience",
            "experience": "Interview preparation topic; not a candidate achievement",
        }.get(self.kind, "Explicit structured input")
        return {"source_type": self.source_type, "quote": self.value, "summary": f"{prefix} at {self.path}: {self.value}"}


def collect_evidence(input_data: dict) -> list[Evidence]:
    result = []

    def add(source, path, value, kind):
        cleaned = _safe_scalar(value)
        if cleaned:
            result.append(Evidence(source, path, cleaned, kind))

    def items(source, root, obj, keys, kind):
        if not isinstance(obj, dict):
            return
        for key in keys:
            values = obj.get(key, [])
            if isinstance(values, list):
                for index, value in enumerate(values):
                    add(source, f"{root}.{key}[{index}]", value, kind)

    resume = input_data.get("resume_profile") or {}
    jd = input_data.get("jd_profile") or {}
    match = input_data.get("match_report") or {}
    items("resume", "resume_profile", resume, ("skills", "backend_tags"), "skill")
    projects = resume.get("projects", []) if isinstance(resume, dict) else []
    for index, project in enumerate(projects if isinstance(projects, list) else []):
        if not isinstance(project, dict):
            continue
        add("resume", f"resume_profile.projects[{index}].name", project.get("name"), "project")
        items("resume", f"resume_profile.projects[{index}]", project, ("tech_stack",), "skill")
    items("jd", "jd_profile", jd, ("tech_keywords", "hard_requirements", "interview_focuses"), "requirement")
    if isinstance(jd, dict):
        add("jd", "jd_profile.job_title", jd.get("job_title"), "role")
    for key, kind in (("matched_strengths", "assessment"), ("missing_capabilities", "gap"), ("preparation_priorities", "priority")):
        items("inferred", "match_report", match, (key,), kind)
    experiences = input_data.get("experience_profiles") or []
    for index, experience in enumerate(experiences if isinstance(experiences, list) else []):
        items("experience", f"experience_profiles[{index}]", experience, ("frequent_topics", "frequent_questions"), "experience")
    return result


def question_intent(text: str, module: str) -> str:
    value = text.casefold()
    if module == "self_intro":
        patterns = (
            ("gap", r"gap|weakness|improv|not.*(?:used|done)|unknown|limitation|缺口|边界|尚未|没有"),
            ("learning", r"learn|stay.*(?:current|updat)|keep.*(?:current|updat)|up.to.date|resources|学习|陌生|验证理解"),
            ("career", r"goal|next|growth|future|milestone|未来|下一阶段|效果"),
            ("strength", r"strong|proficien|skill|familiar|achieve|value.*bring|能力|熟悉|优势"),
            ("motivation", r"why|attract|motivat|interested|为什么|希望"),
            ("preference", r"engaging|rewarding|challenging|enjoy|look.*role"),
        )
        return next((name for name, pattern in patterns if re.search(pattern, value)), "background")
    if re.search(r"compare|contrast|difference|\bversus\b|\bvs\b|比较|区分", value):
        return "comparison"
    if re.search(r"how would|suppose|\bif\b|\bgiven\b|would you|你会|如果|假设", value):
        return "design"
    if module == "behavior_project" and re.search(r"\btime\b|situation|project.{0,20}(?:you|listed)|your.{0,20}project|synthetic|in (?:that|this) project|experience|have you|did you|you.*(?:encountered|made|fixed)|经历|一次|回顾", value):
        return "story"
    if re.search(r"debug|diagnos|root cause|排查|定位|诊断", value):
        return "diagnosis"
    if re.search(r"workflow|how do|what.*strateg|how can|如何|怎样", value):
        return "workflow"
    return "concept"


INTENTS = {
    "background": ("an evidence-grounded professional introduction", "State your relevant background, identify documented skills and delimit your personal contribution; then connect it to the stated role.", "Prepare a concise introduction using verified facts; do not turn an unspecified team result into a personal achievement."),
    "motivation": ("motivation and role alignment", "Explain the attraction, connect it to actual role requirements and an honest capability example, and identify what you still want to learn.", "Prepare a specific motivation tied to the supplied role; do not invent employer values or technologies absent from the input."),
    "learning": ("a verifiable learning process", "Describe the learning need, a concrete resource or experiment, its application and a check that showed understanding.", "Recall a genuine learning example and explain how you tested it; listing fashionable tools is not evidence of learning."),
    "career": ("realistic goals and progress checks", "State a near-term goal, the capability gap it addresses, achievable milestones and a way to check progress.", "Prepare a future plan with explicit milestones; label goals as plans rather than completed experience."),
    "gap": ("honest capability boundaries", "Separate documented capability from missing evidence, state the limitation plainly and propose a verifiable practice plan.", "Do not conceal an important gap or manufacture an incident; propose a clearly labeled practice scenario if necessary."),
    "strength": ("skill depth and evidence of personal contribution", "Choose the capability actually asked about, cite its evidence, explain your personal scope and provide a check on the claimed result.", "Choose one substantiated capability and a defensible example; unknown scale or outcomes must remain unknown."),
    "preference": ("a reasoned engineering preference", "State the preference, explain its practical motivation and relate it to a genuine example or a clearly stated learning goal.", "Prepare a reasoned preference; an unmeasured preference is not proof of superior performance."),
    "concept": ("accurate explanation of the requested mechanism", "Define the terms, explain the mechanism and its boundaries, illustrate a minimal example and identify where the explanation stops applying.", "Prepare a small example and a counterexample for the requested mechanism; a past-project story is optional, not a substitute for the explanation."),
    "comparison": ("comparison under common constraints", "Define the alternatives, compare them under the same constraints, explain selection criteria and identify a counterexample or reversal condition.", "Prepare comparable scenarios and trade-offs; do not claim a universally best option or compare unrelated abstractions as interchangeable."),
    "design": ("a proposed design and its failure boundaries", "Restate the stated constraints and unknowns, propose the mechanism, analyze partial failure and specify acceptance checks; label the design hypothetical.", "Prepare a minimal proposed design with explicit assumptions and a failure test; do not present the proposed design as a completed project."),
    "diagnosis": ("diagnosis supported by falsifiable observations", "Establish the symptom, collect discriminating observations, compare hypotheses, test the root cause and verify the fix.", "Prepare evidence that distinguishes causes from symptoms and a regression check; do not invent an outage or a measured improvement."),
    "workflow": ("an explicit and testable engineering workflow", "State the objective and boundaries, explain the ordered steps and ownership, then show how normal and failed outcomes are checked.", "Prepare an ordered workflow and its failure checks; state whether examples are actual work or proposals."),
    "story": ("a substantiated account of decisions and outcomes", "Use the actual situation and task, delimit your own actions, explain the decision and report only observable outcomes and lessons.", "Use a genuine account or explicitly disclose that no such experience is documented; never manufacture project scope, incidents or numerical outcomes."),
}

PERSONAL_CHECKS = {
    "background": ("Organize a concise professional account around the background actually requested, not an exhaustive technology list.", "Identify personal responsibility and distinguish a listed skill or project name from evidence of its implementation or outcome.", "Connect one substantiated capability to the stated role without inventing years, employers or production scale."),
    "motivation": ("Explain the specific attraction asked about and link it to a stated requirement or an honestly expressed preference.", "Support fit with a documented capability or a clearly labeled learning goal, rather than invented company values.", "Distinguish interest in a technology from proof of production proficiency with it."),
    "learning": ("Describe the actual learning need and a concrete resource, experiment or practice sequence.", "Explain how application or a falsifiable check established understanding, rather than merely listing resources.", "State what changed after feedback or a failed experiment; do not invent a course, contribution or measured achievement."),
    "career": ("State a realistic future capability goal and its relationship to the role or documented gap.", "Provide achievable milestones and an observable progress check while clearly labeling the work as planned.", "Explain prioritization and uncertainty without turning future intentions into past achievements."),
    "gap": ("Separate missing documentation from demonstrated inability and identify precisely what remains unverified.", "Disclose the relevant limitation and propose a practice activity with an acceptance check.", "Avoid hiding a role-critical gap or inventing experience to make the explanation sound stronger."),
    "strength": ("Choose the particular capability requested and support its depth with a defensible example or supplied evidence.", "Delimit your individual contribution, the conditions of use and the outcome that can actually be substantiated.", "Explain where that strength applies to the role and where the evidence does not establish proficiency."),
    "preference": ("State the engineering preference actually requested and explain the practical reason for it.", "Separate a personal preference from measured superiority, giving an honest example or a labeled learning interest.", "Identify a constraint under which that preference would change rather than claiming a universally best choice."),
}


class QuestionBankMetadataAssemblerV2:
    """Pure deterministic candidate, explicitly selected only by offline replay."""

    version = "deterministic-metadata-v2"

    def assemble(self, draft: QuestionDraftBank, input_data: dict) -> dict:
        evidence = collect_evidence(input_data)
        QuestionBankAssembler._validate_evidence([item.ref() for item in evidence])
        allowed = set().union(*(mentioned_technologies(item.value) for item in evidence if item.source_type in {"resume", "jd"}))
        groups = (("self_intro", draft.self_intro_questions, 8), ("professional", draft.professional_questions, 8), ("behavior_project", draft.behavior_project_questions, 9))
        texts = [q.question_text for _, questions, _ in groups for q in questions]
        QuestionBankAssembler._validate_counts(groups, len(texts))
        QuestionBankAssembler._validate_text_uniqueness(texts)
        for text in texts:
            if unsafe_question(text):
                raise AgentOutputValidationError("Unsafe content in question draft")
            if mentioned_technologies(text) - allowed:
                raise AgentOutputValidationError("Question contains an unsupported technology")
        assembled = {key: [] for key in OUTPUT_KEYS.values()}
        for module, questions, _ in groups:
            prefix = {"self_intro": "self", "professional": "pro", "behavior_project": "beh"}[module]
            for index, question in enumerate(questions, 1):
                metadata = self._metadata(question.question_text, module, evidence, allowed)
                assembled[OUTPUT_KEYS[module]].append({
                    "question_id": f"{prefix}-{index:02d}", "module": module,
                    "question_text": question.question_text, "sort_order": index, **metadata,
                })
        bank = QuestionBank.model_validate({**assembled, "total_count": 25})
        QuestionBankAssembler._validate_final_bank(bank)
        self.validate_output_boundary(bank, allowed)
        return bank.model_dump(mode="json")

    @staticmethod
    def validate_output_boundary(bank: QuestionBank, allowed: set[str]) -> None:
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for item in value.values():
                    yield from strings(item)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
        for value in strings(bank.model_dump(mode="json")):
            if mentioned_technologies(value) - allowed:
                raise AgentOutputValidationError("Metadata contains an unsupported technology")
            if SENSITIVE.search(value):
                raise AgentOutputValidationError("Unsafe content in assembled metadata")

    def _select_evidence(self, text, intent, topics, evidence, allowed):
        question_terms = _tokens(text)
        question_tech = mentioned_technologies(text)
        topic_keys = {item.key for item in topics}
        ranked = []
        for item in evidence:
            if mentioned_technologies(item.value) - allowed:
                continue
            if item.kind == "project" and item.value.casefold() not in text.casefold():
                continue
            shared_topics = topic_keys & {topic.key for topic in topics_for(item.value)}
            score = 8 * len(question_tech & mentioned_technologies(item.value))
            score += 3 * len(shared_topics) + len(question_terms & _tokens(item.value))
            if item.kind == "project":
                score += 15
            if item.kind == "role" and intent in {"background", "motivation", "career", "strength", "gap"}:
                score += 4
            if item.kind == "gap" and intent == "gap":
                score += 4
            if item.kind == "skill" and intent in {"background", "strength"} and not question_tech:
                score += 2
            if score:
                ranked.append((score, item.path, item))
        selected = []
        seen = set()
        ordered = sorted(ranked, key=lambda x: (-x[0], x[1]))
        # Prefer complementary sources over three duplicate lists of the same skill.
        for require_new_source in (True, False):
            for _, _, item in ordered:
                identity = (item.source_type, item.value, item.kind)
                if identity in seen or (require_new_source and any(s.source_type == item.source_type for s in selected)):
                    continue
                selected.append(item)
                seen.add(identity)
                if len(selected) == 3:
                    return selected
        return selected

    def _metadata(self, text: str, module: str, evidence: list[Evidence], allowed: set[str]) -> dict:
        intent = question_intent(text, module)
        label, framework, advice = INTENTS[intent]
        topics = topics_for(text)
        selected = self._select_evidence(text, intent, topics, evidence, allowed)
        refs = [item.ref() for item in selected] or [{
            "source_type": "inferred", "quote": text,
            "summary": "Question-derived practice only; no relevant documented experience or requirement was found. This is not evidence of an achievement.",
        }]
        types = {item["source_type"] for item in refs}
        scope = "; ".join(topic.label for topic in topics) or "the responsibilities and constraints explicitly stated in the question"
        title = text if len(text) <= 220 else text[:217] + "..."
        negative = bool(re.search(r"without|not\s+us\w*|不使用|不用|禁止", text, re.I))
        constraint = " Preserve the prohibition in the question; do not introduce the prohibited mechanism." if negative else ""
        personal = intent in {"background", "motivation", "learning", "career", "gap", "strength", "preference"}
        if personal:
            checks = list(PERSONAL_CHECKS[intent])
            followups = {
                "background": ["Which part of that example was your own responsibility?", "What supplied evidence supports the capability you chose to emphasize?"],
                "motivation": ["Which stated role requirement explains that interest?", "What capability example or learning goal makes the fit credible?"],
                "learning": ["What small experiment showed that you understood the material?", "What observation corrected an earlier misunderstanding?"],
                "career": ["What observable milestone would show progress on that goal?", "Which capability gap should be checked first?"],
                "gap": ["Which part is documented and which part remains untested?", "What practice check would provide the missing evidence?"],
                "strength": ["What can you substantiate about your personal contribution?", "Where does the demonstrated capability stop applying?"],
                "preference": ["What genuine example explains that preference?", "Which constraint would change your preference?"],
            }[intent]
        else:
            checks = self._technical_checks(topics, intent)
            followups = list(dict.fromkeys(question for topic in topics[:2] for question in topic.followups))[:3]
            if not followups:
                followups = ["Which assumption in this question most affects your reasoning?", "What minimal example would falsify the proposed conclusion?"]
            if topics:
                framework += " Topic checkpoints: " + " ".join(topic.checkpoints[0] for topic in topics)
                advice += " Practice: " + " ".join(topic.checkpoints[2] for topic in topics[:2])
        if intent == "story":
            framework += " A listed skill or project name alone does not document the incident, architecture, actions or result; disclose missing details."
        star = (
            "Situation: [verified context only]; Task: [your actual responsibility]; Action: [what you actually did and why]; Result: [observed outcome or explicitly unknown]; Reflection: [lesson and check]."
            if intent == "story" else
            "Not a required past-experience narrative. Use the question-specific reasoning framework; label examples or proposals hypothetical when not documented."
        )
        anchors = [{
            "name": f"{intent}: {scope.split(';')[0]} — criterion {index + 1}",
            "score": weight, "max_score": weight,
            "reason": f"Rubric allocation, not an observed candidate score. Award up to {weight} only if: {check}" + constraint,
        } for index, (weight, check) in enumerate(zip((4, 3, 3), checks))]
        return {
            "purpose": f"Evaluate {label} for this question: «{title}». Focus: {scope}." + constraint,
            "difficulty": "basic" if personal else "hard" if intent in {"comparison", "design", "diagnosis"} else "medium",
            "source_type": next(iter(types)) if len(types) == 1 else "mixed",
            "source_refs": refs,
            "jd_keywords": list(dict.fromkeys(item.value for item in selected if item.source_type == "jd")),
            "answer_framework": framework + constraint, "star_template": star,
            "scoring_anchors": anchors, "follow_up_questions": followups,
            "preparation_advice": f"For «{title}»: {advice}" + constraint,
        }

    @staticmethod
    def _technical_checks(topics: list[Topic], intent: str) -> list[str]:
        if not topics:
            return [
                "Define the terms and scope actually asked about; explicitly identify missing assumptions.",
                "Explain the decision or mechanism using a minimal example tied to the question.",
                "Provide a check or counterexample and distinguish observed facts from proposals.",
            ]
        if intent == "story":
            return [
                "Delimit your actual responsibility and the evidence for the situation; do not invent scale or outcomes.",
                topics[0].checkpoints[0] + " " + topics[0].checkpoints[1],
                topics[-1].checkpoints[2] + " Report what was actually observed and what remained uncertain.",
            ]
        return [
            topics[0].checkpoints[0] + " " + topics[0].checkpoints[1],
            topics[1].checkpoints[0] + " " + topics[1].checkpoints[1] if len(topics) > 1 else topics[0].checkpoints[2],
            " ".join(topic.checkpoints[2] for topic in topics),
        ]
