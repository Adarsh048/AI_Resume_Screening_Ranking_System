"""
Resume parser: text extraction from PDF/DOCX/TXT and structured field extraction.

Strategy:
- Use pdfplumber as primary PDF extractor (better layout handling than PyPDF2).
- Fall back to pypdf if pdfplumber fails.
- DOCX via python-docx, TXT directly.
- Regex-based extraction for name, email, GitHub URL, and technology signals.
- SHA-256 of raw text for duplicate detection.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from src.models import ParsedResume

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword lists used for signal extraction
# ---------------------------------------------------------------------------

PYTHON_KEYWORDS: list[str] = [
    "python", "fastapi", "flask", "django", "asyncio", "pydantic",
    "sqlalchemy", "pytest", "pandas", "numpy", "scipy",
]

AI_KEYWORDS: list[str] = [
    "langchain", "langgraph", "llamaindex", "llama_index", "openai",
    "anthropic", "gemini", "huggingface", "transformers",
    "rag", "retrieval augmented", "retrieval-augmented",
    "vector search", "vector store", "vectorstore",
    "embedding", "embeddings", "pinecone", "weaviate", "chroma", "qdrant", "faiss",
    "agent", "agentic", "multi-agent", "tool calling", "tool use",
    "llm", "large language model", "gpt", "claude", "mistral", "ollama",
    "google adk", "crewai", "autogen", "semantic kernel",
    "prompt engineering", "fine-tuning", "fine tuning",
    "nlp", "natural language processing",
]

BACKEND_KEYWORDS: list[str] = [
    "fastapi", "flask", "django", "rest api", "restful", "graphql",
    "postgresql", "postgres", "mysql", "mongodb", "redis",
    "asyncio", "async", "celery", "kafka", "rabbitmq",
    "sqlalchemy", "prisma", "orm", "websocket",
]

CLOUD_KEYWORDS: list[str] = [
    "aws", "gcp", "google cloud", "azure",
    "docker", "kubernetes", "k8s", "terraform", "ansible",
    "ci/cd", "github actions", "gitlab ci", "jenkins",
    "vercel", "netlify", "heroku", "render",
    "react", "next.js", "nextjs", "vue", "angular",
    "typescript", "javascript", "node.js", "nodejs",
]

ENGINEERING_KEYWORDS: list[str] = [
    "pytest", "unit test", "integration test", "tdd", "test coverage",
    "caching", "redis cache", "rate limiting", "rate limit",
    "logging", "observability", "monitoring", "prometheus", "grafana",
    "concurrency", "threading", "multiprocessing",
    "error handling", "retry logic", "circuit breaker",
    "design pattern", "clean architecture", "microservice",
    "queue", "message queue", "event driven",
]

# Regex to find a GitHub profile URL or username mention
GITHUB_URL_PATTERN = re.compile(
    r"(?:https?://)?github\.com/([A-Za-z0-9](?:[A-Za-z0-9\-]{0,37}[A-Za-z0-9])?)",
    re.IGNORECASE,
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# Heuristic: first line that looks like a name (2–4 capitalised words, no digits)
NAME_PATTERN = re.compile(
    r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})$"
)


# ---------------------------------------------------------------------------
# PDF extraction helpers
# ---------------------------------------------------------------------------

def _extract_pdf_pdfplumber(path: Path) -> str:
    """Primary PDF extraction using pdfplumber."""
    import pdfplumber  # type: ignore

    pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)


def _extract_pdf_pypdf(path: Path) -> str:
    """Fallback PDF extraction using pypdf."""
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(str(path))
    texts: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text)
    return "\n".join(texts)


def _extract_docx(path: Path) -> str:
    """Extract text from a DOCX file."""
    from docx import Document  # type: ignore

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Signal extraction helpers
# ---------------------------------------------------------------------------

def _find_signals(text: str, keywords: list[str]) -> list[str]:
    """Return matched keywords found in text (case-insensitive, deduplicated)."""
    lower = text.lower()
    found = []
    seen: set[str] = set()
    for kw in keywords:
        if kw.lower() in lower and kw.lower() not in seen:
            found.append(kw)
            seen.add(kw.lower())
    return found


NAME_STOP_PHRASES = frozenset({
    "curriculum vitae", "resume", "cv", "summary", "profile", "professional summary",
    "resume summary", "profile summary", "career aspiration", "career objective",
    "profile objective", "objectives", "education", "experience", "work experience",
    "projects", "technical skills", "skills summary", "skills", "certifications",
    "software engineer", "software developer", "full stack developer", "full-stack developer",
    "backend developer", "frontend developer", "frontend engineer", "data analyst",
    "data scientist", "ai engineer", "intern", "associate", "engineering student",
    "present", "visual studio code", "current location", "applexus technologies",
    "swami vivekananda university", "webtrex software services hyderabad",
    "vijayawada nalanda junior college", "testing playwright", "bachelor of technology",
    "computer science", "relevant coursework", "academic projects", "contact",
    "contact information", "email", "phone", "address", "languages", "programming languages",
})


def _clean_candidate_line(line: str) -> str:
    line = re.sub(r"\(cid:\d+\)", " ", line)
    line = re.sub(r"[\u200b\x00\ufeff]", " ", line)
    for sep in ("|", "•", "·", "\t", "  "):
        if sep in line:
            parts = line.split(sep)
            if parts[0].strip():
                line = parts[0].strip()
                break
    line = re.sub(r"(\+91|\b\d{10}\b|\b\d{5}\b).*", "", line).strip()
    return line.strip(" -–—:,*#|")


def _is_valid_name_token(token: str) -> bool:
    clean = token.strip(".,()[]{}").replace("-", "").replace("'", "").replace(".", "")
    return clean.isalpha() and len(clean) > 0


def _extract_name(text: str) -> Optional[str]:
    """
    Robust name extraction:
    - Scans the first 10 non-empty lines of the resume.
    - Filters out section headings, labels (e.g. 'Resume', 'Education'),
      job titles, contact details, emails, URLs, and phone numbers.
    - Handles Title Case, ALL CAPS, middle initials, and prefix/suffix dots.
    - Returns None if no verified candidate name can be determined reliably.
      Does not invent names or use filenames.
    """
    raw_lines = text.splitlines()[:15]
    cleaned_lines = [_clean_candidate_line(l) for l in raw_lines]
    cleaned_lines = [l for l in cleaned_lines if l]

    candidate_name: Optional[str] = None

    for i, line in enumerate(cleaned_lines[:8]):
        lower = line.lower()

        # Reject lines containing stop phrases
        if any(stop in lower for stop in NAME_STOP_PHRASES):
            continue

        # Reject lines containing emails, URLs, or contact anchors
        if "@" in line or any(k in lower for k in ("http", "www", ".com", ".in", ".me", ".dev", ".tech", "linkedin", "github", "leetcode", "portfolio", "phone", "mobile")):
            continue

        # Reject lines with digits
        if any(ch.isdigit() for ch in line):
            continue

        words = line.split()
        if not (1 <= len(words) <= 5):
            continue

        if not all(_is_valid_name_token(w) for w in words):
            continue

        if len(line) < 3 or len(line) > 40:
            continue

        # If line has just a single first name (e.g. "Prathamesh") and a subsequent line
        # has a single surname (e.g. "Patil" before contact info), combine them
        if len(words) == 1 and i + 2 < len(cleaned_lines):
            next_line = cleaned_lines[i + 2] if i + 2 < len(cleaned_lines) else ""
            next_words = next_line.split()
            if len(next_words) == 1 and _is_valid_name_token(next_words[0]) and next_line.lower() not in NAME_STOP_PHRASES:
                words.append(next_words[0])
                line = f"{line} {next_line}"

        # Normalize ALL CAPS to professional Title Case
        if line.isupper():
            candidate_name = " ".join(w.capitalize() if len(w) > 2 else w for w in words)
        else:
            candidate_name = line
        break

    return candidate_name


def _extract_email(text: str) -> Optional[str]:
    match = EMAIL_PATTERN.search(text)
    return match.group(0) if match else None


def _extract_github(text: str) -> tuple[Optional[str], Optional[str]]:
    """Return (full_url, username) or (None, None)."""
    match = GITHUB_URL_PATTERN.search(text)
    if not match:
        return None, None
    username = match.group(1)
    return f"https://github.com/{username}", username


def _extract_projects(text: str) -> list[str]:
    """
    Return a list of project description snippets.

    We look for lines that follow common section headers (Projects, Experience,
    Work) and collect up to 800 characters per block, to give the scorer useful
    context without shipping the entire resume text.
    """
    project_section_re = re.compile(
        r"(project|experience|internship|work experience|portfolio)",
        re.IGNORECASE,
    )
    lines = text.splitlines()
    snippets: list[str] = []
    inside = False
    buffer: list[str] = []

    for line in lines:
        stripped = line.strip()
        if project_section_re.search(stripped) and len(stripped) < 60:
            if buffer:
                snippets.append(" ".join(buffer)[:800])
                buffer = []
            inside = True
            continue
        if inside:
            if stripped:
                buffer.append(stripped)
            elif buffer:
                # blank line ends a block
                snippets.append(" ".join(buffer)[:800])
                buffer = []
                if len(snippets) >= 8:
                    break

    if buffer:
        snippets.append(" ".join(buffer)[:800])

    return snippets[:8]  # at most 8 snippets


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_resume(path: Path) -> ParsedResume:
    """
    Parse a single resume file and return a ParsedResume.

    Errors during extraction are captured; the returned object will have
    parse_error set so the pipeline can continue with the remaining files.
    """
    resume = ParsedResume(file_name=path.name)
    ext = path.suffix.lower()

    # --- text extraction ---
    try:
        if ext == ".pdf":
            try:
                raw = _extract_pdf_pdfplumber(path)
            except Exception as primary_err:
                logger.warning(
                    "%s: pdfplumber failed (%s), trying pypdf", path.name, primary_err
                )
                raw = _extract_pdf_pypdf(path)
        elif ext in {".docx", ".doc"}:
            raw = _extract_docx(path)
        elif ext == ".txt":
            raw = _extract_txt(path)
        else:
            resume.parse_error = f"Unsupported file type: {ext}"
            return resume

        if not raw or not raw.strip():
            resume.parse_error = "Empty or unreadable document"
            return resume

        resume.raw_text = raw
        resume.content_hash = _content_hash(raw)

    except Exception as exc:
        logger.error("Failed to extract text from %s: %s", path.name, exc)
        resume.parse_error = str(exc)
        return resume

    # --- structured extraction ---
    try:
        resume.name = _extract_name(raw)
        resume.email = _extract_email(raw)
        resume.github_url, resume.github_username = _extract_github(raw)

        resume.python_mentions = _find_signals(raw, PYTHON_KEYWORDS)
        resume.ai_mentions = _find_signals(raw, AI_KEYWORDS)
        resume.backend_mentions = _find_signals(raw, BACKEND_KEYWORDS)
        resume.cloud_mentions = _find_signals(raw, CLOUD_KEYWORDS)
        resume.engineering_signals = _find_signals(raw, ENGINEERING_KEYWORDS)

        # consolidated, deduplicated skill list
        all_signals = set(
            resume.python_mentions
            + resume.ai_mentions
            + resume.backend_mentions
            + resume.cloud_mentions
            + resume.engineering_signals
        )
        resume.skills = sorted(all_signals)

        resume.project_descriptions = _extract_projects(raw)

    except Exception as exc:
        # Extraction errors are non-fatal; we keep whatever we managed to pull
        logger.warning("Partial extraction error for %s: %s", path.name, exc)

    return resume
