"""
Optional LLM adapter for semantic project-quality evaluation.

This module wraps a language model to produce:
1. A project summary for the candidate record.
2. A quality verdict for the AI category that can refine the deterministic score.

Design principles:
- Hard eligibility checks are never delegated to the LLM.
- The LLM score is treated as a signal, not the source of truth; it is
  bounded by the deterministic ceilings.
- One failed model call must not fail the batch; fallback is transparent.
- API keys come from environment variables (OPENAI_API_KEY or GEMINI_API_KEY).
- The adapter pattern keeps the rest of the codebase independent of the
  specific provider.

If no provider is configured (no API key found), the module returns a
clearly marked deterministic fallback and does not pretend to use an LLM.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# LLM is optional — we import lazily so missing packages don't crash the pipeline
_openai_available = False
_gemini_available = False

try:
    import openai  # type: ignore
    _openai_available = True
except ImportError:
    pass

try:
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        import google.generativeai as genai  # type: ignore
    _gemini_available = True
except ImportError:
    pass


SYSTEM_PROMPT = """You are an expert technical recruiter evaluating resumes for a Python/AI engineering internship.

Given a candidate's project descriptions and skill signals, produce a JSON object with exactly these fields:
{
  "project_summary": "<2-3 sentence summary of the candidate's most relevant projects>",
  "ai_depth_adjustment": <integer between -5 and 5, positive if projects show real depth beyond keywords>,
  "depth_rationale": "<one sentence explaining the adjustment>"
}

Rules:
- project_summary must be factual and based only on the provided text. Do not invent details.
- ai_depth_adjustment should be positive only for genuine implementation depth (custom pipelines, 
  retrieval architecture, multi-agent coordination, evaluation systems, etc.).
- Penalise (negative adjustment) for pure API wrappers, tutorial reproductions, or vague claims.
- depth_rationale must justify the adjustment in concrete terms.
- Return ONLY the JSON object, no markdown fences.
"""


def _call_openai(prompt: str) -> Optional[dict]:
    """Call OpenAI API and return parsed JSON response."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            timeout=30,
        )
        content = response.choices[0].message.content or ""
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned non-JSON: %s", exc)
        return None
    except Exception as exc:
        logger.warning("OpenAI call failed: %s", exc)
        return None


def _call_gemini(prompt: str) -> Optional[dict]:
    """Call Google Gemini API and return parsed JSON response."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"),
            system_instruction=SYSTEM_PROMPT,
        )
        response = model.generate_content(prompt)
        content = response.text or ""
        # Strip markdown fences if present
        if content.strip().startswith("```"):
            content = "\n".join(
                line for line in content.splitlines()
                if not line.strip().startswith("```")
            )
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("Gemini returned non-JSON: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Gemini call failed: %s", exc)
        return None


def _validate_llm_response(data: dict) -> bool:
    """
    Ensure the LLM response contains required fields with correct types.
    Rejects any response that would inject invalid scores.
    """
    if not isinstance(data.get("project_summary"), str):
        return False
    adjustment = data.get("ai_depth_adjustment")
    if not isinstance(adjustment, (int, float)):
        return False
    if not (-5 <= adjustment <= 5):
        return False
    return True


def _build_prompt(project_descriptions: list[str], ai_signals: list[str]) -> str:
    projects_text = "\n\n".join(project_descriptions) if project_descriptions else "No project descriptions extracted."
    signals_text = ", ".join(ai_signals) if ai_signals else "none"
    return (
        f"AI/LLM signals found: {signals_text}\n\n"
        f"Project descriptions:\n{projects_text}"
    )


def evaluate_with_llm(
    project_descriptions: list[str],
    ai_signals: list[str],
    enabled: bool = True,
) -> tuple[str, float, bool]:
    """
    Run LLM evaluation on project descriptions.

    Args:
        project_descriptions: Extracted project description text blocks.
        ai_signals: Detected AI keywords/signals.
        enabled: If False, completely bypasses provider calls and uses fallback.

    Returns:
        (project_summary, ai_depth_adjustment, llm_was_used)

    The adjustment is bounded to [-5, 5] regardless of what the model returns.
    If no LLM is available, disabled, or a call fails, returns a deterministic fallback
    with llm_was_used=False.
    """
    if not enabled:
        logger.debug("LLM evaluation disabled via configuration — using deterministic project summary")
        summary = _deterministic_summary(project_descriptions, ai_signals)
        return summary, 0.0, False

    prompt = _build_prompt(project_descriptions, ai_signals)

    # Try providers in order: OpenAI first, then Gemini
    result: Optional[dict] = None

    if _openai_available and os.environ.get("OPENAI_API_KEY"):
        result = _call_openai(prompt)

    if result is None and _gemini_available and os.environ.get("GEMINI_API_KEY"):
        result = _call_gemini(prompt)

    if result and _validate_llm_response(result):
        summary = result["project_summary"].strip()
        adjustment = float(result["ai_depth_adjustment"])
        rationale = result.get("depth_rationale", "")
        if rationale:
            logger.debug("LLM depth rationale: %s", rationale)
        return summary, adjustment, True

    # Transparent deterministic fallback
    logger.info("LLM unavailable or failed — using deterministic project summary")
    summary = _deterministic_summary(project_descriptions, ai_signals)
    return summary, 0.0, False


def _deterministic_summary(
    project_descriptions: list[str],
    ai_signals: list[str],
) -> str:
    """
    Build a project summary without an LLM by condensing the extracted
    project text and signal list. Clearly non-LLM output.
    """
    if not project_descriptions and not ai_signals:
        return "No project details extracted from resume."

    # Take first 2 project snippets, truncated
    snippets = [p[:200] for p in project_descriptions[:2]]
    signals_note = f"AI/LLM signals detected: {', '.join(ai_signals[:6])}." if ai_signals else ""

    parts = [s for s in snippets if s.strip()]
    summary = " | ".join(parts)
    if signals_note:
        summary = (summary + " " + signals_note).strip()

    return summary or "Insufficient project details in resume."
