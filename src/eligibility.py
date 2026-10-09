"""
Hard eligibility filter — deterministic, no LLM dependency.

Rules (both must pass):
1. Python evidence: Genuine Python experience as a skill, project technology,
   work technology, or implementation language.
   - A genuine Python skill listed once is accepted (no arbitrary count thresholds).
   - JavaScript-, Java-, or React-only profiles without Python are rejected.
   - Candidates using JavaScript, Java, or React ALONGSIDE Python and AI remain eligible.
2. AI/Agentic evidence: At least one meaningful AI, LLM, RAG, agentic, or equivalent
   custom AI implementation (e.g. neural networks, embeddings, model fine-tuning).
   - Keywords such as PyTorch, TensorFlow, Keras, RAG, or AI-powered appearing
     solely in an isolated or multiline skills list do NOT satisfy eligibility.
   - Actual project/work experience evidence is evaluated from project descriptions,
     implementation details, responsibilities, and measurable outcomes.
   - Custom AI implementations (e.g., PyTorch models, CNNs, embeddings) in projects
     or work experience are accepted even if they do not use LangChain or LlamaIndex.

Both filters provide supporting evidence and explicit rejection reasons.
"""

from __future__ import annotations

import re
from typing import Optional

from src.models import EligibilityResult, ParsedResume

# ---------------------------------------------------------------------------
# Section heading and line classification patterns
# ---------------------------------------------------------------------------

SECTION_HEADING_PATTERNS: dict[str, re.Pattern] = {
    "skills": re.compile(
        r"^[\s\W_]*(?:technical\s+|core\s+|key\s+|professional\s+|it\s+|computer\s+|programming\s+|relevant\s+)?"
        r"(?:skills|technologies|tools|competencies|proficiencies|tech\s+stack)"
        r"(?:\s*(?:&|and|\||\/)\s*(?:tools|technologies|frameworks|libraries|skills|competencies))?"
        r"(?:\s*summary)?[\s\W_]*:?$",
        re.IGNORECASE,
    ),
    "projects": re.compile(
        r"^[\s\W_]*(?:academic\s+|personal\s+|key\s+|selected\s+|recent\s+|capstone\s+|software\s+|technical\s+)?"
        r"(?:projects|portfolio|project\s+work)[\s\W_]*:?$",
        re.IGNORECASE,
    ),
    "experience": re.compile(
        r"^[\s\W_]*(?:work\s+|professional\s+|employment\s+|relevant\s+|industry\s+|practical\s+)?"
        r"(?:experience|employment|internships?|work\s+history|career\s+history)[\s\W_]*:?$",
        re.IGNORECASE,
    ),
    "education": re.compile(
        r"^[\s\W_]*(?:education|academic\s+background|qualifications|academics)[\s\W_]*:?$",
        re.IGNORECASE,
    ),
    "certifications": re.compile(
        r"^[\s\W_]*(?:certifications?|certificates?|licenses?|training|courses)[\s\W_]*:?$",
        re.IGNORECASE,
    ),
    "summary": re.compile(
        r"^[\s\W_]*(?:summary|professional\s+summary|profile|profile\s+summary|about\s+me|career\s+objective|objective)[\s\W_]*:?$",
        re.IGNORECASE,
    ),
    "other": re.compile(
        r"^[\s\W_]*(?:achievements?|awards?|honors?|publications?|extracurriculars?|activities|interests|hobbies|languages\s+known|personal\s+details|contact|declaration)[\s\W_]*:?$",
        re.IGNORECASE,
    ),
}

INLINE_SKILLS_PREFIX_RE = re.compile(
    r"^\s*(?:[\W_]*\s*)?(?:technical\s+|core\s+|key\s+|programming\s+)?"
    r"(?:skills?|technologies|languages?|frameworks?(?:\s*&|\s*and|\s*\/\s*libraries)?|libraries|"
    r"developer\s+tools|tools|databases?|cloud|ai\s*[\/\&]\s*ml|machine\s+learning|deep\s+learning)\s*:\s*.+",
    re.IGNORECASE,
)

# Implementation action indicators distinguishing project narrative from skills lists
IMPLEMENTATION_ACTION_RE = re.compile(
    r"\b(built|developed|trained|implemented|designed|created|fine-tuned|finetuned|"
    r"deployed|engineered|architected|automated|integrated|optimized|evaluated|"
    r"utilizing|utilized|leveraged|leveraging|constructed|researched|tested|applied|"
    r"pipeline|workflow|model|system|application|chatbot|bot|assistant|classifier|"
    r"dataset|accuracy|latency|f1-score|inference|detection|prediction|orchestration)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Python evidence patterns
# ---------------------------------------------------------------------------

PYTHON_ECOSYSTEM_RE = re.compile(
    r"\b(fastapi|flask|django|pandas|numpy|scipy|pydantic|sqlalchemy|"
    r"pytest|asyncio|celery|scrapy|tensorflow|pytorch|keras|scikit.learn|"
    r"matplotlib|seaborn|streamlit|gradio)\b",
    re.IGNORECASE,
)

PYTHON_PRIMARY_RE = re.compile(
    r"\b(python\s+developer|python\s+engineer|python\s+programming|"
    r"written\s+in\s+python|built\s+with\s+python|using\s+python|"
    r"python\s+backend|python\s+script|python\s+based|"
    r"python\s+\d\.\d|python3|py\.?\s*project)\b",
    re.IGNORECASE,
)

PYTHON_SKILLS_HEADER_RE = re.compile(
    r"\b(languages?|programming\s+languages?|technical\s+skills?|core\s+skills?|technologies)\s*:[^\n]*\bpython\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# AI/Agentic evidence patterns
# ---------------------------------------------------------------------------

AI_FRAMEWORK_RE = re.compile(
    r"\b(langchain|langgraph|llamaindex|llama.index|llama_index|"
    r"openai|anthropic|gemini|google\s+gemini|huggingface|transformers|"
    r"autogen|crewai|google\s+adk|semantic\s+kernel|"
    r"pinecone|weaviate|chroma(?:db)?|qdrant|faiss|milvus|"
    r"rag|retrieval.augmented|vector\s+(?:store|search|database|db)|"
    r"embeddings?\s+(?:model|pipeline|generation)?|"
    r"tool.calling|function.calling|agentic\s+(?:workflow|system|ai)?|"
    r"multi.agent|agent\s+(?:framework|orchestration|workflow|system|qa|prompt)|"
    r"llm[s]?|large\s+language\s+models?|"
    r"fine.tun(?:ing|ed)|prompt.engineer(?:ing|ed))\b",
    re.IGNORECASE,
)

# Broader AI signals & custom AI implementation patterns
AI_CUSTOM_IMPL_RE = re.compile(
    r"\b(neural\s+network|deep\s+learning|convolutional|cnn|rnn|lstm|transformer\s+model|"
    r"natural\s+language\s+processing|nlp\s+(?:project|pipeline|model|system)?|"
    r"semantic\s+search|cosine\s+similarity|vector\s+similarity|"
    r"sentiment\s+analysis|text\s+classification|named\s+entity|"
    r"computer\s+vision|object\s+detection|yolo|opencv\s+(?:model|detection)?|"
    r"semantic\s+segmentation|image\s+segmentation|"
    r"model\s+training|model\s+evaluation|model\s+inference|transfer\s+learning|"
    r"supervised\s+learning|unsupervised\s+learning|reinforcement\s+learning|"
    r"scikit-learn|random\s+forest|gradient\s+boosting|xgboost|"
    r"pytorch|tensorflow|keras|"
    r"chatbot\s+(?:with|using|built|developed)?|"
    r"gpt.(?:3|4|o|based|powered)|claude.(?:based|powered|api)?|"
    r"mistral|ollama|llama\s*(?:2|3|\d)?|"
    r"ai.powered|ai.(?:agent|system|application|tool))\b",
    re.IGNORECASE,
)

PROJECT_HEADER_INDICATORS_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|"
    r"20\d\d|present|intern(?:ship)?|developer|engineer|github\.com|demo|project|live)\b",
    re.IGNORECASE,
)


def _is_skills_list_line(line: str) -> bool:
    """Return True if line is formatted as a comma/delimiter-separated skills list."""
    if INLINE_SKILLS_PREFIX_RE.match(line):
        return True
    if PROJECT_HEADER_INDICATORS_RE.search(line):
        return False
    delimiters = line.count(",") + line.count("|") + line.count("•") + line.count("·") + line.count("/")
    words = line.split()
    if delimiters >= 2 and len(words) <= 25:
        if not IMPLEMENTATION_ACTION_RE.search(line):
            return True
    return False


def partition_resume_sections(text: str) -> tuple[list[str], list[str]]:
    """
    Partition raw resume text into (skills_lines, non_skills_lines).

    Handles multiline skills sections, different headings, bullet points,
    and category prefixes reliably.
    """
    skills_lines: list[str] = []
    non_skills_lines: list[str] = []
    current_section = "header"

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Check for section heading
        matched_section: Optional[str] = None
        for sec_name, pattern in SECTION_HEADING_PATTERNS.items():
            if pattern.match(stripped) and len(stripped) < 60:
                matched_section = sec_name
                break

        if matched_section:
            current_section = matched_section
            continue

        if current_section == "skills" or _is_skills_list_line(stripped):
            skills_lines.append(stripped)
        else:
            non_skills_lines.append(stripped)

    return skills_lines, non_skills_lines


def check_python_evidence(resume: ParsedResume) -> tuple[bool, list[str]]:
    """
    Return (passes, evidence_snippets).

    A genuine Python skill listed once passes.
    Java/JS-only profiles fail unless Python is present.
    """
    text = resume.raw_text
    lower = text.lower()
    evidence: list[str] = []

    has_python_word = "python" in lower or bool(re.search(r"\bpython\d?\b", lower))
    has_ecosystem = bool(PYTHON_ECOSYSTEM_RE.search(text))

    if not has_python_word and not has_ecosystem:
        return False, []

    for m in re.finditer(r".{0,40}\bpython\b.{0,40}", text, re.IGNORECASE):
        snippet = m.group(0).strip().replace("\n", " ")
        if snippet not in evidence:
            evidence.append(snippet)
        if len(evidence) >= 5:
            break

    if len(evidence) < 5:
        for m in PYTHON_ECOSYSTEM_RE.finditer(text):
            snippet = m.group(0).strip().replace("\n", " ")
            if snippet not in evidence:
                evidence.append(snippet)
            if len(evidence) >= 5:
                break

    in_skills = "python" in [s.lower() for s in resume.skills] or bool(PYTHON_SKILLS_HEADER_RE.search(text))
    in_projects = any("python" in p.lower() for p in resume.project_descriptions)
    in_primary = bool(PYTHON_PRIMARY_RE.search(text))

    passes = has_python_word or has_ecosystem or in_skills or in_projects or in_primary
    return passes, evidence[:5]


def check_ai_evidence(resume: ParsedResume) -> tuple[bool, list[str]]:
    """
    Return (passes, evidence_snippets).

    Rules:
    1. Framework or custom AI implementation pattern must exist in resume.
    2. Keywords such as PyTorch, TensorFlow, Keras, RAG, or AI-powered appearing
       solely in skills lists without any project, experience, or implementation context
       fail eligibility.
    3. Custom AI implementations (CNN, deep learning, PyTorch models, embeddings)
       in projects or work experience are accepted.
    """
    text = resume.raw_text
    evidence: list[str] = []

    framework_match = AI_FRAMEWORK_RE.search(text)
    custom_match = AI_CUSTOM_IMPL_RE.search(text)

    if not framework_match and not custom_match:
        return False, []

    # Partition resume into skills lines vs non-skills lines (projects, experience, summary)
    skills_lines, non_skills_lines = partition_resume_sections(text)

    # Combine all potential project / work experience texts
    project_sources = list(resume.project_descriptions) + non_skills_lines

    # Check for AI evidence in project / work experience / narrative contexts
    has_project_evidence = False
    for block in project_sources:
        fm = AI_FRAMEWORK_RE.search(block)
        cm = AI_CUSTOM_IMPL_RE.search(block)
        if fm or cm:
            # Verify the block isn't merely an isolated comma-separated skill line
            if not _is_skills_list_line(block):
                has_project_evidence = True
                match = fm or cm
                start = max(0, match.start() - 30)
                end = min(len(block), match.end() + 60)
                snippet = block[start:end].strip().replace("\n", " ")
                if snippet not in evidence:
                    evidence.append(snippet)

    # Check if AI terms only appear in skills lists
    if not has_project_evidence:
        # All AI mentions were confined to skills list sections
        return False, []

    return True, evidence[:6]


def evaluate_eligibility(resume: ParsedResume) -> EligibilityResult:
    """
    Run both hard filters and return an EligibilityResult.

    This function is the single source of truth for eligibility.
    It is deterministic, evidence-based, and outside the LLM decision process.
    """
    result = EligibilityResult()

    py_passes, py_evidence = check_python_evidence(resume)
    ai_passes, ai_evidence = check_ai_evidence(resume)

    result.has_python = py_passes
    result.has_ai_evidence = ai_passes
    result.python_evidence = py_evidence
    result.ai_evidence = ai_evidence

    if not py_passes:
        result.rejection_reasons.append(
            "No sufficient Python evidence found. "
            "Python must appear as a skill, project language, or implementation technology."
        )
    if not ai_passes:
        text = resume.raw_text
        has_any_ai_mention = bool(AI_FRAMEWORK_RE.search(text) or AI_CUSTOM_IMPL_RE.search(text))
        if has_any_ai_mention:
            result.rejection_reasons.append(
                "No meaningful AI/LLM/RAG/agentic project or work experience found. "
                "AI frameworks/keywords were only listed in skills, with no implementation evidence in projects or experience."
            )
        else:
            result.rejection_reasons.append(
                "No meaningful AI/LLM/RAG/agentic evidence found. "
                "At least one AI framework, technique, or implementation is required."
            )

    result.is_eligible = py_passes and ai_passes
    return result
