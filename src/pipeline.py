"""
End-to-end pipeline orchestrator.

Processing order for each resume:
  1. Parse (extract text + fields)
  2. Duplicate detection (skip duplicates, retain first occurrence)
  3. Eligibility check (deterministic hard filters)
  4. GitHub enrichment (non-blocking, failures are tolerated)
  5. Scoring (all five categories)
  6. LLM project summary (optional; falls back transparently)
  7. Rank eligible candidates by total score (ties broken by file name)

The pipeline is single-threaded to keep the implementation straightforward
and avoid GitHub API rate-limit pressure from concurrent requests.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.eligibility import evaluate_eligibility
from src.github_enrichment import enrich_github
from src.llm_adapter import evaluate_with_llm
from src.models import BatchStats, CandidateResult, EligibilityResult
from src.parser import parse_resume
from src.scorer import compute_scores, derive_strengths_and_concerns

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


def _discover_resumes(input_dir: Path) -> list[Path]:
    """Return all supported resume files in the directory, sorted by name."""
    files = [
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files, key=lambda p: p.name.lower())


def _process_one(path: Path, seen_hashes: set[str], use_llm: bool = True) -> CandidateResult:
    """
    Full processing pipeline for a single resume file.

    Returns a CandidateResult with parse_status set appropriately.
    Never raises; all errors are captured in the result.
    """
    result = CandidateResult(file_name=path.name)

    # --- Step 1: Parse ---
    resume = parse_resume(path)

    if resume.parse_error:
        logger.warning("Parse failed for %s: %s", path.name, resume.parse_error)
        result.parse_status = "failed"
        result.parse_error = resume.parse_error
        result.eligibility.rejection_reasons.append(
            f"Could not parse resume: {resume.parse_error}"
        )
        return result

    if not resume.raw_text.strip():
        result.parse_status = "empty"
        result.parse_error = "Empty document after extraction"
        result.eligibility.rejection_reasons.append("Resume is empty or unreadable.")
        return result

    # --- Step 2: Duplicate detection ---
    if resume.content_hash and resume.content_hash in seen_hashes:
        result.parse_status = "duplicate"
        result.name = resume.name
        result.email = resume.email
        result.eligibility.rejection_reasons.append(
            "Duplicate resume — identical content to a previously processed file."
        )
        return result
    if resume.content_hash:
        seen_hashes.add(resume.content_hash)

    # --- Step 3: Populate identity fields ---
    result.name = resume.name
    result.email = resume.email
    result.matched_skills = resume.skills

    # --- Step 4: Eligibility ---
    eligibility = evaluate_eligibility(resume)
    result.eligibility = eligibility

    if not eligibility.is_eligible:
        logger.info(
            "%s: REJECTED — %s",
            path.name,
            "; ".join(eligibility.rejection_reasons),
        )
        return result

    # --- Step 5: GitHub enrichment ---
    github = enrich_github(resume.github_username)
    result.github = github

    # --- Step 6: Scoring ---
    scores, strengths, concerns = compute_scores(resume, eligibility, github)
    result.scores = scores
    result.strengths = strengths
    result.concerns = concerns

    # --- Step 7: LLM project summary (optional) ---
    project_summary, ai_adjustment, llm_used = evaluate_with_llm(
        resume.project_descriptions,
        resume.ai_mentions,
        enabled=use_llm,
    )
    result.project_summary = project_summary

    # Apply bounded LLM adjustment to AI depth score
    if llm_used and ai_adjustment != 0.0:
        adjusted = scores.ai_rag_depth + ai_adjustment
        scores.ai_rag_depth = min(max(adjusted, 0.0), 40.0)
        scores.clamp()
        # Recalculate strengths and concerns to remain strictly in sync with final score
        result.strengths, result.concerns = derive_strengths_and_concerns(scores, github)
        logger.debug(
            "%s: LLM AI adjustment %+.1f → ai_rag_depth now %.1f",
            path.name,
            ai_adjustment,
            scores.ai_rag_depth,
        )

    result.parse_status = "ok"
    return result


def run_pipeline(
    input_dir: Path,
    output_path: Path,
    use_llm: bool = True,
) -> None:
    """
    Run the complete screening pipeline and write results to output_path.

    Args:
        input_dir:   Directory containing resume files.
        output_path: Path for the results.json output.
        use_llm:     If False, skip LLM calls even if an API key is present.
    """
    logger.info("Starting pipeline — input: %s", input_dir)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    files = _discover_resumes(input_dir)
    stats = BatchStats(total_discovered=len(files))
    logger.info("Discovered %d resume file(s)", stats.total_discovered)

    seen_hashes: set[str] = set()
    results: list[CandidateResult] = []

    for i, path in enumerate(files, start=1):
        logger.info("[%d/%d] Processing %s", i, stats.total_discovered, path.name)
        candidate = _process_one(path, seen_hashes, use_llm=use_llm)
        results.append(candidate)

        # Update stats
        if candidate.parse_status in {"failed", "empty"}:
            stats.failed_count += 1
        elif candidate.parse_status == "duplicate":
            stats.duplicate_count += 1
            stats.rejected_count += 1
        elif candidate.eligibility.is_eligible:
            stats.successfully_parsed += 1
            stats.eligible_count += 1
        else:
            stats.successfully_parsed += 1
            stats.rejected_count += 1

    # --- Rank eligible candidates ---
    eligible = [r for r in results if r.eligibility.is_eligible]
    eligible.sort(key=lambda r: (-r.scores.total, r.file_name))
    for rank, candidate in enumerate(eligible, start=1):
        candidate.rank = rank

    # --- Serialise output ---
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_discovered": stats.total_discovered,
            "successfully_parsed": stats.successfully_parsed,
            "eligible_count": stats.eligible_count,
            "rejected_count": stats.rejected_count,
            "failed_count": stats.failed_count,
            "duplicate_count": stats.duplicate_count,
        },
        "eligible_candidates": [r.to_dict() for r in eligible],
        "rejected_candidates": [
            r.to_dict() for r in results if not r.eligibility.is_eligible
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    logger.info("Results written to %s", output_path)
    _print_summary(eligible, stats)


def _print_summary(eligible: list[CandidateResult], stats: BatchStats) -> None:
    """Print a concise terminal summary after the run."""
    print("\n" + "=" * 60)
    print("  AI Resume Screening — Run Complete")
    print("=" * 60)
    print(f"  Total discovered:  {stats.total_discovered}")
    print(f"  Successfully parsed: {stats.successfully_parsed}")
    print(f"  Eligible:          {stats.eligible_count}")
    print(f"  Rejected:          {stats.rejected_count}")
    print(f"  Failed/Unreadable: {stats.failed_count}")
    print(f"  Duplicates:        {stats.duplicate_count}")
    print()
    print("  Top eligible candidates:")
    print(f"  {'Rank':<6} {'Name':<30} {'Score':>6}")
    print("  " + "-" * 45)
    for c in eligible[:10]:
        name = c.name or c.file_name
        print(f"  {c.rank!s:<6} {name:<30} {c.scores.total:>6.1f}")
    if len(eligible) > 10:
        print(f"  ... and {len(eligible) - 10} more eligible candidate(s)")
    print("=" * 60 + "\n")
