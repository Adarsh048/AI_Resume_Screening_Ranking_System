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
   - A framework mentioned ONLY in an isolated skills list without any project,
     work experience, or implementation context does NOT prove an AI project exists.
   - Custom AI implementations are accepted even if they do not use LangChain or LlamaIndex.

Both filters provide supporting evidence and explicit rejection reasons.
"""

from __future__ import annotations

import re

from src.models import EligibilityResult, ParsedResume

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
    r"openai|anthropic|gemini\s+api|huggingface|transformers|"
    r"autogen|crewai|google\s+adk|semantic\s+kernel|"
    r"pinecone|weaviate|chroma(?:db)?|qdrant|faiss|milvus|"
    r"rag|retrieval.augmented|vector\s+(?:store|search|database|db)|"
    r"embeddings?\s+(?:model|pipeline|generation)|"
    r"tool.calling|function.calling|agentic\s+(?:workflow|system|ai)|"
    r"multi.agent|agent\s+(?:framework|orchestration|workflow)|"
    r"llm.(?:pipeline|chain|integration|agent)|"
    r"fine.tun(?:ing|ed)|prompt.engineer(?:ing|ed))\b",
    re.IGNORECASE,
)

# Broader AI signals & custom AI implementation patterns
AI_CUSTOM_IMPL_RE = re.compile(
    r"\b(neural\s+network|deep\s+learning|convolutional|cnn|rnn|lstm|transformer\s+model|"
    r"natural\s+language\s+processing|nlp\s+(?:project|pipeline|model|system)|"
    r"semantic\s+search|cosine\s+similarity|vector\s+similarity|"
    r"sentiment\s+analysis|text\s+classification|named\s+entity|"
    r"computer\s+vision|object\s+detection|yolo|opencv\s+(?:model|detection)|"
    r"model\s+training|model\s+evaluation|model\s+inference|transfer\s+learning|"
    r"supervised\s+learning|unsupervised\s+learning|reinforcement\s+learning|"
    r"scikit-learn|random\s+forest|gradient\s+boosting|xgboost|"
    r"pytorch|tensorflow|keras|"
    r"large\s+language\s+model|chatbot\s+(?:with|using|built|developed)|"
    r"gpt.(?:3|4|o|based|powered)|claude.(?:based|powered|api)|"
    r"mistral|ollama|llama\s*(?:2|3|\d)|"
    r"ai.powered|ai.(?:agent|system|application|tool))\b",
    re.IGNORECASE,
)


def check_python_evidence(resume: ParsedResume) -> tuple[bool, list[str]]:
    """
    Return (passes, evidence_snippets).

    A genuine Python skill listed once passes.
    Java/JS-only profiles fail unless Python is present.
    """
    text = resume.raw_text
    lower = text.lower()
    evidence: list[str] = []

    # Check presence of python keyword or core python frameworks
    has_python_word = "python" in lower or bool(re.search(r"\bpython\d?\b", lower))
    has_ecosystem = bool(PYTHON_ECOSYSTEM_RE.search(text))

    if not has_python_word and not has_ecosystem:
        return False, []

    # Collect evidence snippets
    for m in re.finditer(r".{0,40}python.{0,40}", text, re.IGNORECASE):
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

    # Determine if genuine Python evidence exists
    # - Listed in parsed skills
    # - In programming languages / skills section
    # - In project descriptions
    # - Associated with ecosystem framework
    # - Or matched primary pattern
    in_skills = "python" in [s.lower() for s in resume.skills] or bool(PYTHON_SKILLS_HEADER_RE.search(text))
    in_projects = any("python" in p.lower() for p in resume.project_descriptions)
    in_primary = bool(PYTHON_PRIMARY_RE.search(text))

    passes = has_python_word or has_ecosystem or in_skills or in_projects or in_primary
    return passes, evidence[:5]


def _is_only_in_skills_list(text: str, match_pattern: re.Pattern) -> bool:
    """
    Return True if all occurrences of match_pattern appear exclusively
    within isolated skills/technologies bullet lines and nowhere in project,
    work experience, or narrative text.
    """
    skills_section_re = re.compile(
        r"(?:technical\s+skills?|core\s+skills?|skills?|technologies)\s*:[^\n]*",
        re.IGNORECASE,
    )
    skills_lines = skills_section_re.findall(text)
    skills_combined = " ".join(skills_lines)

    all_matches = match_pattern.findall(text)
    if not all_matches:
        return False

    matches_in_skills = match_pattern.findall(skills_combined)
    # If the number of matches outside the skills header is 0, it's only in skills
    return len(matches_in_skills) >= len(all_matches)


def check_ai_evidence(resume: ParsedResume) -> tuple[bool, list[str]]:
    """
    Return (passes, evidence_snippets).

    Checks for:
    1. Framework or custom AI implementation pattern.
    2. Evidence that it appears in a project, experience, or implementation context
       (not merely an isolated keyword in a skills list without any project context).
    3. Custom AI implementations (PyTorch, CNN, embeddings, etc.) are accepted.
    """
    text = resume.raw_text
    evidence: list[str] = []

    framework_match = AI_FRAMEWORK_RE.search(text)
    custom_match = AI_CUSTOM_IMPL_RE.search(text)

    if not framework_match and not custom_match:
        return False, []

    # Collect context evidence snippets
    for pattern in (AI_FRAMEWORK_RE, AI_CUSTOM_IMPL_RE):
        for m in pattern.finditer(text):
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 50)
            snippet = text[start:end].strip().replace("\n", " ")
            if snippet not in evidence:
                evidence.append(snippet)
            if len(evidence) >= 6:
                break

    # Guard: A framework mentioned ONLY in a comma-separated skills list with NO
    # project, work experience, or custom AI implementation does not prove an AI project exists.
    has_project_evidence = False
    if resume.project_descriptions:
        project_text = " ".join(resume.project_descriptions)
        if AI_FRAMEWORK_RE.search(project_text) or AI_CUSTOM_IMPL_RE.search(project_text):
            has_project_evidence = True

    # Check if there is narrative or implementation evidence outside an isolated skills line
    only_in_skills = (
        _is_only_in_skills_list(text, AI_FRAMEWORK_RE)
        and not custom_match
        and not has_project_evidence
    )

    if only_in_skills:
        return False, []

    passes = bool(framework_match or custom_match)
    return passes, evidence[:6]


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
        result.rejection_reasons.append(
            "No meaningful AI/LLM/RAG/agentic evidence found. "
            "At least one AI framework, technique, or implementation is required."
        )

    result.is_eligible = py_passes and ai_passes
    return result
