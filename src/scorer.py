"""
100-point scoring engine.

Scoring is deterministic and evidence-based. Each category is scored
independently and clamped to its ceiling before summing.

Category weights (matching the assignment):
  AI / Agentic / RAG Project Depth  : 40
  Python & Backend Engineering       : 30
  Cloud / Deployment / Full Stack    : 15
  GitHub Activity                    : 10
  Engineering Depth Signals          :  5

Penalties are applied within each category, not as a global deduction, so
the total remains in [0, 100].
"""

from __future__ import annotations

import re

from src.models import EligibilityResult, GitHubProfile, ParsedResume, ScoreBreakdown

# ---------------------------------------------------------------------------
# AI / Agentic / RAG depth — max 40
# ---------------------------------------------------------------------------

# Tier-1: deep implementation signals worth more points
AI_DEEP_SIGNALS = {
    "langgraph": 8, "langchain": 6, "llamaindex": 6, "llama_index": 6,
    "google adk": 7, "crewai": 6, "autogen": 6, "semantic kernel": 5,
    "rag": 7, "retrieval augmented": 7, "retrieval-augmented": 7,
    "vector store": 5, "vector search": 5, "vectorstore": 5,
    "embeddings": 4, "embedding": 4, "faiss": 5, "pinecone": 5,
    "weaviate": 5, "chroma": 4, "qdrant": 5, "milvus": 4,
    "tool calling": 6, "function calling": 5, "tool use": 5,
    "multi-agent": 7, "agentic workflow": 6, "agent orchestration": 6,
    "state management": 4, "langgraph state": 6,
    "evaluation pipeline": 5, "llm evaluation": 4, "ragas": 5,
}

# Tier-2: framework use / standard signals
AI_STANDARD_SIGNALS = {
    "openai": 3, "anthropic": 3, "gemini": 3, "huggingface": 3,
    "transformers": 3, "llm": 2, "large language model": 2,
    "chatbot": 2, "gpt": 2, "fine-tuning": 4, "fine tuning": 4,
    "prompt engineering": 3, "nlp": 2, "semantic search": 3,
    "document qa": 3, "document retrieval": 3,
    "mistral": 3, "ollama": 3, "llama": 2,
}

# Penalty triggers (shallow patterns)
SHALLOW_PATTERNS = re.compile(
    r"\b(simple\s+chatbot|basic\s+chatbot|wrapper|api\s+wrapper|"
    r"tutorial|hello\s+world|toy\s+project|demo\s+app|"
    r"just\s+calls?\s+(?:the\s+)?(?:openai|gpt|llm)\s+api)\b",
    re.IGNORECASE,
)


def score_ai_depth(resume: ParsedResume) -> tuple[float, list[str]]:
    """
    Score AI/Agentic/RAG depth (max 40).

    Returns (score, strength_notes).
    Penalty: −5 to −15 for shallow wrapper-only projects.
    """
    from src.eligibility import partition_resume_sections

    text = resume.raw_text.lower()
    total = 0.0
    notes: list[str] = []

    skills_lines, non_skills_lines = partition_resume_sections(resume.raw_text)
    project_sources = list(resume.project_descriptions) + non_skills_lines
    project_text = " ".join(project_sources).lower()

    # Deep signals: prioritize evidence in project descriptions over keyword lists
    for signal, weight in AI_DEEP_SIGNALS.items():
        in_proj = signal in project_text
        in_text = signal in text
        if in_proj:
            total += weight
            notes.append(f"Deep signal: {signal} (+{weight})")
        elif in_text:
            # Keyword match outside project descriptions receives reduced credit
            discounted = round(weight * 0.5, 1)
            total += discounted
            notes.append(f"Deep signal (skills only): {signal} (+{discounted})")

    # Standard signals: add but cap contribution so they don't crowd out depth
    standard_score = 0.0
    for signal, weight in AI_STANDARD_SIGNALS.items():
        in_proj = signal in project_text
        in_text = signal in text
        if in_proj:
            standard_score += weight
        elif in_text:
            standard_score += weight * 0.5
    standard_score = min(standard_score, 10.0)  # cap standard signals at 10
    total += standard_score

    # Shallow penalty
    penalty = 0.0
    shallow_matches = SHALLOW_PATTERNS.findall(resume.raw_text)
    if shallow_matches:
        # Check if there are also deep signals to offset
        has_deep = any(sig in text for sig in AI_DEEP_SIGNALS if AI_DEEP_SIGNALS[sig] >= 5)
        if not has_deep:
            penalty = 12.0  # heavy penalty for pure wrappers
            notes.append(f"Penalty: shallow/wrapper signals ({', '.join(set(shallow_matches))}) −{penalty}")
        else:
            penalty = 5.0   # lighter penalty if there are also real implementations
            notes.append(f"Penalty: shallow signal alongside deeper work −{penalty}")
        total -= penalty

    # Projects section bonus: reward candidates who list real implementation details
    project_text = " ".join(resume.project_descriptions).lower()
    implementation_re = re.compile(
        r"\b(implemented|built|designed|developed|integrated|deployed|"
        r"optimized|architected|engineered|created)\b"
    )
    implementation_count = len(implementation_re.findall(project_text))
    if implementation_count >= 3:
        bonus = min(implementation_count * 1.0, 5.0)
        total += bonus
        notes.append(f"Implementation depth bonus +{bonus:.0f}")

    score = min(max(total, 0.0), 40.0)
    return round(score, 1), notes


# ---------------------------------------------------------------------------
# Python & Backend Engineering — max 30
# ---------------------------------------------------------------------------

PYTHON_DEPTH_SIGNALS = {
    "fastapi": 5, "flask": 4, "django": 4, "asyncio": 4, "async": 2,
    "pydantic": 3, "sqlalchemy": 3, "pytest": 3, "celery": 3,
    "websocket": 3, "rest api": 3, "restful": 2, "graphql": 3,
    "postgresql": 3, "postgres": 3, "mysql": 2, "mongodb": 2,
    "redis": 3, "orm": 2, "alembic": 3,
}

PYTHON_BASIC = {"python": 4, "pandas": 2, "numpy": 2, "scipy": 1}


def score_python_backend(resume: ParsedResume, eligibility: EligibilityResult) -> tuple[float, list[str]]:
    """
    Score Python & Backend Engineering (max 30).

    Prioritises evidence in project/experience descriptions over keyword lists.
    """
    text = resume.raw_text.lower()
    project_text = " ".join(resume.project_descriptions).lower()
    total = 0.0
    notes: list[str] = []

    # Project/experience evidence gets 1.5× weight
    for signal, weight in PYTHON_DEPTH_SIGNALS.items():
        in_projects = signal in project_text
        in_full = signal in text
        if in_projects:
            total += weight * 1.5
            notes.append(f"{signal} (in projects, +{weight * 1.5:.1f})")
        elif in_full:
            total += weight
            notes.append(f"{signal} (+{weight})")

    # Basic Python baseline
    for signal, weight in PYTHON_BASIC.items():
        if signal in text:
            total += weight

    # Internship / work evidence bonus
    experience_re = re.compile(
        r"\b(intern(?:ship)?|work(?:ed)?|employ(?:ed|ment)|position|role)\b",
        re.IGNORECASE,
    )
    if experience_re.search(resume.raw_text) and "python" in text:
        total += 3.0
        notes.append("Python internship/work evidence +3")

    score = min(max(total, 0.0), 30.0)
    return round(score, 1), notes


# ---------------------------------------------------------------------------
# Cloud / Deployment / Full Stack — max 15
# ---------------------------------------------------------------------------

CLOUD_DEPTH_SIGNALS = {
    "docker": 4, "kubernetes": 5, "k8s": 5, "terraform": 4,
    "aws": 3, "gcp": 4, "google cloud": 4, "azure": 3,
    "ci/cd": 3, "github actions": 3, "gitlab ci": 3, "jenkins": 2,
    "vercel": 2, "heroku": 2, "render": 1, "netlify": 1,
    "react": 2, "next.js": 2, "nextjs": 2, "vue": 2, "angular": 2,
    "typescript": 2, "node.js": 2, "nodejs": 2,
}


def score_cloud_deployment(resume: ParsedResume) -> tuple[float, list[str]]:
    """Score Cloud / Deployment / Full Stack (max 15)."""
    text = resume.raw_text.lower()
    total = 0.0
    notes: list[str] = []

    for signal, weight in CLOUD_DEPTH_SIGNALS.items():
        if signal in text:
            total += weight
            notes.append(f"{signal} (+{weight})")

    score = min(max(total, 0.0), 15.0)
    return round(score, 1), notes


# ---------------------------------------------------------------------------
# Engineering Depth Signals — max 5
# ---------------------------------------------------------------------------

ENGINEERING_DEPTH = {
    "pytest": 1, "unit test": 1, "integration test": 1, "tdd": 1.5,
    "caching": 1, "rate limit": 1, "logging": 0.5, "observability": 1,
    "concurrency": 1, "threading": 1, "multiprocessing": 1,
    "error handling": 0.5, "retry": 0.5, "circuit breaker": 1.5,
    "microservice": 1, "message queue": 1, "kafka": 1.5, "rabbitmq": 1.5,
    "design pattern": 0.5, "clean architecture": 1,
}


def score_engineering_depth(resume: ParsedResume) -> tuple[float, list[str]]:
    """Score Engineering Depth Signals (max 5)."""
    text = resume.raw_text.lower()
    total = 0.0
    notes: list[str] = []

    for signal, weight in ENGINEERING_DEPTH.items():
        if signal in text:
            total += weight
            notes.append(f"{signal} (+{weight})")

    score = min(max(total, 0.0), 5.0)
    return round(score, 1), notes


# ---------------------------------------------------------------------------
def derive_strengths_and_concerns(
    breakdown: ScoreBreakdown,
    github: Optional[GitHubProfile] = None,
) -> tuple[list[str], list[str]]:
    """
    Derive qualitative strengths and concerns strictly grounded in final category scores.
    Ensures explanations remain consistent after any adjustments or penalties.
    Unavailable GitHub data is not interpreted as evidence of poor engineering.
    """
    strengths: list[str] = []
    concerns: list[str] = []

    ai_score = breakdown.ai_rag_depth
    py_score = breakdown.python_backend
    cloud_score = breakdown.cloud_deployment
    gh_score = breakdown.github_activity
    eng_score = breakdown.engineering_depth

    if ai_score >= 25:
        strengths.append("Strong AI/RAG/agentic project depth")
    elif ai_score >= 15:
        strengths.append("Solid AI implementation evidence")

    if py_score >= 20:
        strengths.append("Strong Python and backend engineering experience")
    elif py_score >= 12:
        strengths.append("Adequate Python and backend skills")

    if cloud_score >= 8:
        strengths.append("Good cloud/deployment experience")

    if gh_score >= 7:
        strengths.append("Active public GitHub with relevant repositories")

    if eng_score >= 3:
        strengths.append("Demonstrates engineering practices (testing, observability, etc.)")

    if ai_score < 10:
        concerns.append("Limited AI/RAG project depth — may be surface-level exposure")

    if py_score < 10:
        concerns.append("Python evidence is thin; limited backend engineering shown")

    # Only flag low GitHub activity if an active profile was verified to have 0 recent pushes,
    # never when GitHub profile is unavailable, missing, or rate-limited.
    if github and github.enrichment_status == "success" and github.public_repos > 0 and gh_score == 0:
        concerns.append("Verified GitHub profile has no recent public activity")

    if breakdown.total < 40:
        concerns.append("Overall score is low — candidate meets minimum eligibility but lacks depth")

    return strengths, concerns


def compute_scores(
    resume: ParsedResume,
    eligibility: EligibilityResult,
    github: GitHubProfile,
) -> tuple[ScoreBreakdown, list[str], list[str]]:
    """
    Compute all five scoring categories and return:
      (ScoreBreakdown, strengths, concerns)

    GitHub score is passed in from the enrichment step (already 0–10).
    """
    ai_score, ai_notes = score_ai_depth(resume)
    py_score, py_notes = score_python_backend(resume, eligibility)
    cloud_score, cloud_notes = score_cloud_deployment(resume)
    eng_score, eng_notes = score_engineering_depth(resume)
    gh_score = min(max(github.score, 0.0), 10.0)

    breakdown = ScoreBreakdown(
        ai_rag_depth=ai_score,
        python_backend=py_score,
        cloud_deployment=cloud_score,
        github_activity=gh_score,
        engineering_depth=eng_score,
    )
    breakdown.clamp()

    strengths, concerns = derive_strengths_and_concerns(breakdown, github)
    return breakdown, strengths, concerns
