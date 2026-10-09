"""
Data models for the resume screening pipeline.

All scoring categories, eligibility results, and final candidate records are
typed here so that every module uses the same structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScoreBreakdown:
    """Per-category scores matching the 100-point rubric."""

    ai_rag_depth: float = 0.0          # max 40
    python_backend: float = 0.0        # max 30
    cloud_deployment: float = 0.0      # max 15
    github_activity: float = 0.0       # max 10
    engineering_depth: float = 0.0     # max  5

    @property
    def total(self) -> float:
        return round(
            self.ai_rag_depth
            + self.python_backend
            + self.cloud_deployment
            + self.github_activity
            + self.engineering_depth,
            2,
        )

    def clamp(self) -> None:
        """Ensure each category stays within its ceiling."""
        self.ai_rag_depth = min(max(self.ai_rag_depth, 0.0), 40.0)
        self.python_backend = min(max(self.python_backend, 0.0), 30.0)
        self.cloud_deployment = min(max(self.cloud_deployment, 0.0), 15.0)
        self.github_activity = min(max(self.github_activity, 0.0), 10.0)
        self.engineering_depth = min(max(self.engineering_depth, 0.0), 5.0)


@dataclass
class EligibilityResult:
    """Hard-filter outcome for a single candidate."""

    is_eligible: bool = False
    has_python: bool = False
    has_ai_evidence: bool = False
    python_evidence: list[str] = field(default_factory=list)
    ai_evidence: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass
class GitHubProfile:
    """Public GitHub data collected during enrichment."""

    username: Optional[str] = None
    profile_url: Optional[str] = None
    # raw signals
    public_repos: int = 0
    recent_push_count: int = 0          # pushes in last 90 days
    has_python_repos: bool = False
    has_ai_repos: bool = False
    recent_repo_names: list[str] = field(default_factory=list)
    # enrichment metadata
    enrichment_status: str = "not_attempted"   # not_attempted | success | failed | rate_limited | no_profile
    enrichment_summary: str = ""
    score: float = 0.0                  # 0–10


@dataclass
class ParsedResume:
    """All information extracted from a single resume file."""

    file_name: str = ""
    raw_text: str = ""
    parse_error: Optional[str] = None

    # identity
    name: Optional[str] = None
    email: Optional[str] = None
    github_url: Optional[str] = None
    github_username: Optional[str] = None

    # skills and technologies
    skills: list[str] = field(default_factory=list)
    python_mentions: list[str] = field(default_factory=list)
    ai_mentions: list[str] = field(default_factory=list)
    backend_mentions: list[str] = field(default_factory=list)
    cloud_mentions: list[str] = field(default_factory=list)
    engineering_signals: list[str] = field(default_factory=list)

    # project evidence
    project_descriptions: list[str] = field(default_factory=list)

    # hash for duplicate detection
    content_hash: Optional[str] = None


@dataclass
class CandidateResult:
    """Final record for one candidate, eligible or not."""

    file_name: str = ""
    rank: Optional[int] = None          # only set for eligible candidates

    name: Optional[str] = None
    email: Optional[str] = None

    eligibility: EligibilityResult = field(default_factory=EligibilityResult)
    scores: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    github: GitHubProfile = field(default_factory=GitHubProfile)

    matched_skills: list[str] = field(default_factory=list)
    project_summary: str = ""
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)

    # per-file processing status
    parse_status: str = "ok"            # ok | failed | empty | duplicate
    parse_error: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary for JSON output."""
        return {
            "file_name": self.file_name,
            "rank": self.rank,
            "name": self.name,
            "email": self.email,
            "eligibility": {
                "is_eligible": self.eligibility.is_eligible,
                "has_python": self.eligibility.has_python,
                "has_ai_evidence": self.eligibility.has_ai_evidence,
                "python_evidence": self.eligibility.python_evidence,
                "ai_evidence": self.eligibility.ai_evidence,
                "rejection_reasons": self.eligibility.rejection_reasons,
            },
            "scores": {
                "total": self.scores.total,
                "ai_rag_depth": self.scores.ai_rag_depth,
                "python_backend": self.scores.python_backend,
                "cloud_deployment": self.scores.cloud_deployment,
                "github_activity": self.scores.github_activity,
                "engineering_depth": self.scores.engineering_depth,
            },
            "github": {
                "username": self.github.username,
                "profile_url": self.github.profile_url,
                "public_repos": self.github.public_repos,
                "recent_push_count": self.github.recent_push_count,
                "has_python_repos": self.github.has_python_repos,
                "has_ai_repos": self.github.has_ai_repos,
                "recent_repo_names": self.github.recent_repo_names,
                "enrichment_status": self.github.enrichment_status,
                "enrichment_summary": self.github.enrichment_summary,
                "score": self.github.score,
            },
            "matched_skills": self.matched_skills,
            "project_summary": self.project_summary,
            "strengths": self.strengths,
            "concerns": self.concerns,
            "parse_status": self.parse_status,
            "parse_error": self.parse_error,
        }


@dataclass
class BatchStats:
    """Aggregate statistics over the complete run."""

    total_discovered: int = 0
    successfully_parsed: int = 0
    eligible_count: int = 0
    rejected_count: int = 0
    failed_count: int = 0
    duplicate_count: int = 0
