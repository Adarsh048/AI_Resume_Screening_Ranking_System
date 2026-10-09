"""
GitHub enrichment module.

Uses the public GitHub REST API (no authentication required for basic data,
but supports a token via GITHUB_TOKEN env var to raise the rate limit from
60 to 5000 requests/hour).

Scoring (0–10):
  Recent activity (last 90 days, public events): 0–5
  Repository quality (Python/AI repos, maintained repos): 0–5

All network failures and rate limits are caught gracefully.
Results are cached in-memory and rate-limiting state is tracked so subsequent
requests do not repeatedly hit exhausted rate limits.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from src.models import GitHubProfile

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT = 10  # seconds
RECENT_DAYS = 90

# AI/Python related topics and language names
AI_REPO_SIGNALS = frozenset({
    "langchain", "rag", "llm", "ai", "machine-learning", "deep-learning",
    "nlp", "transformer", "gpt", "openai", "huggingface", "embeddings",
    "vector", "chatbot", "agent", "langgraph",
})

# In-process cache keyed by lowercase username
_cache: dict[str, GitHubProfile] = {}

# Timestamp until which GitHub API is considered rate limited
_rate_limited_until: float = 0.0


def reset_github_cache() -> None:
    """Clear in-memory cache and rate-limit tracking (primarily for testing)."""
    global _rate_limited_until
    _cache.clear()
    _rate_limited_until = 0.0


def is_rate_limited() -> bool:
    """Return True if the client is currently in a rate-limited backoff period."""
    return time.time() < _rate_limited_until


def _record_rate_limit(resp: Optional[requests.Response] = None) -> None:
    """Record that GitHub has rate limited us and set the cooldown deadline."""
    global _rate_limited_until
    reset_epoch: Optional[float] = None
    if resp is not None:
        reset_header = resp.headers.get("x-ratelimit-reset")
        if reset_header and reset_header.isdigit():
            reset_epoch = float(reset_header)

    now = time.time()
    if reset_epoch and reset_epoch > now:
        # Cap cooldown in client to max 1 hour or the header
        _rate_limited_until = min(reset_epoch, now + 3600)
    else:
        # Default 60-second backoff if reset header not present
        _rate_limited_until = now + 60.0

    logger.warning("GitHub rate limit active until epoch %.0f (in %.0fs)", _rate_limited_until, _rate_limited_until - now)


def _get_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _safe_get(url: str, params: Optional[dict] = None) -> tuple[str, Optional[Any]]:
    """
    Perform a GET request and return a tuple of (status_kind, data).

    status_kind values:
      - "ok"           : HTTP 200, data is parsed JSON
      - "rate_limited" : HTTP 403 (with rate limit message/header) or HTTP 429, or active backoff
      - "not_found"    : HTTP 404
      - "failed"       : Other HTTP errors, timeouts, or network failures
    """
    if is_rate_limited():
        return "rate_limited", None

    try:
        resp = requests.get(url, headers=_get_headers(), params=params, timeout=REQUEST_TIMEOUT)

        # Check rate limit headers
        remaining = resp.headers.get("x-ratelimit-remaining")
        if remaining == "0":
            _record_rate_limit(resp)
            return "rate_limited", None

        if resp.status_code == 429:
            _record_rate_limit(resp)
            return "rate_limited", None

        if resp.status_code == 403:
            text_lower = resp.text.lower()
            if "rate limit" in text_lower or remaining == "0":
                _record_rate_limit(resp)
                return "rate_limited", None
            logger.warning("GitHub 403 Forbidden for %s: %s", url, resp.text[:200])
            return "failed", None

        if resp.status_code == 404:
            return "not_found", None

        resp.raise_for_status()
        return "ok", resp.json()

    except requests.exceptions.Timeout:
        logger.warning("Timeout fetching %s", url)
        return "failed", None
    except requests.exceptions.RequestException as exc:
        logger.warning("GitHub request error for %s: %s", url, exc)
        return "failed", None
    except Exception as exc:
        logger.warning("Unexpected error fetching %s: %s", url, exc)
        return "failed", None


def _days_since(date_str: str) -> Optional[int]:
    """Return days since an ISO-8601 date string, or None if unparseable."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None


def _score_activity(recent_pushes: int) -> float:
    """
    Score recent activity (0–5).
      0 pushes → 0
      1–3      → 1
      4–10     → 2
      11–25    → 3
      26–60    → 4
      61+      → 5
    """
    if recent_pushes <= 0:
        return 0.0
    if recent_pushes <= 3:
        return 1.0
    if recent_pushes <= 10:
        return 2.0
    if recent_pushes <= 25:
        return 3.0
    if recent_pushes <= 60:
        return 4.0
    return 5.0


def _score_repos(repos: list[dict]) -> tuple[float, bool, bool, list[str]]:
    """
    Score repository quality (0–5).
    Returns (repo_score, has_python_repos, has_ai_repos, recent_repo_names).
    """
    if not repos:
        return 0.0, False, False, []

    has_python = False
    has_ai = False
    maintained_count = 0
    recent_names: list[str] = []

    for repo in repos[:30]:  # examine up to 30 repos
        lang = (repo.get("language") or "").lower()
        if lang == "python":
            has_python = True

        topics = [t.lower() for t in (repo.get("topics") or [])]
        desc = (repo.get("description") or "").lower()
        name = (repo.get("name") or "").lower()
        ai_hit = (
            any(t in AI_REPO_SIGNALS for t in topics)
            or any(s in desc for s in AI_REPO_SIGNALS)
            or any(s in name for s in AI_REPO_SIGNALS)
        )
        if ai_hit:
            has_ai = True

        pushed_at = repo.get("pushed_at") or repo.get("updated_at") or ""
        if pushed_at:
            days = _days_since(pushed_at)
            if days is not None and days <= 180:
                maintained_count += 1
                recent_names.append(repo.get("name", ""))

    score = 0.0
    if maintained_count >= 1:
        score += 1.0
    if maintained_count >= 3:
        score += 1.0
    if maintained_count >= 6:
        score += 1.0
    if has_python:
        score += 1.0
    if has_ai:
        score += 1.0

    return min(score, 5.0), has_python, has_ai, recent_names[:5]


def enrich_github(username: Optional[str]) -> GitHubProfile:
    """
    Fetch public GitHub data for a candidate's username and return a GitHubProfile.

    Handles missing profiles, rate limits, timeouts, and network failures distinctly.
    Returns immediately with enrichment_status="no_username" if username is empty.
    """
    profile = GitHubProfile()

    if not username or not username.strip():
        profile.enrichment_status = "no_username"
        profile.enrichment_summary = "No GitHub username found in resume."
        return profile

    clean_user = username.strip().rstrip("/")
    if clean_user.startswith("https://github.com/"):
        clean_user = clean_user.replace("https://github.com/", "")
    clean_user = clean_user.split("/")[0]

    cache_key = clean_user.lower()
    if cache_key in _cache:
        return _cache[cache_key]

    profile.username = clean_user
    profile.profile_url = f"https://github.com/{clean_user}"

    # Check if we are currently rate-limited before making requests
    if is_rate_limited():
        profile.enrichment_status = "rate_limited"
        profile.enrichment_summary = "GitHub API rate limit active; enrichment skipped."
        profile.score = 0.0
        _cache[cache_key] = profile
        return profile

    # 1. Fetch user profile
    status, user_data = _safe_get(f"{GITHUB_API}/users/{clean_user}")

    if status == "rate_limited":
        profile.enrichment_status = "rate_limited"
        profile.enrichment_summary = "GitHub API rate limit reached. Score set to 0."
        profile.score = 0.0
        _cache[cache_key] = profile
        return profile

    if status == "not_found":
        profile.enrichment_status = "not_found"
        profile.enrichment_summary = f"GitHub profile '{clean_user}' not found (404)."
        profile.score = 0.0
        _cache[cache_key] = profile
        return profile

    if status == "failed" or not isinstance(user_data, dict):
        profile.enrichment_status = "failed"
        profile.enrichment_summary = f"GitHub API error or timeout fetching '{clean_user}'."
        profile.score = 0.0
        _cache[cache_key] = profile
        return profile

    profile.public_repos = int(user_data.get("public_repos", 0))

    # 2. Fetch public events to count recent pushes
    events_status, events_data = _safe_get(
        f"{GITHUB_API}/users/{clean_user}/events/public",
        params={"per_page": 100},
    )
    recent_pushes = 0
    if events_status == "ok" and isinstance(events_data, list):
        for event in events_data:
            if event.get("type") == "PushEvent":
                created_at = event.get("created_at", "")
                days = _days_since(created_at)
                if days is not None and days <= RECENT_DAYS:
                    recent_pushes += 1
    elif events_status == "rate_limited":
        logger.info("Rate limit hit during events fetch for %s", clean_user)

    profile.recent_push_count = recent_pushes

    # 3. Fetch public repositories
    repos_status, repos_data = _safe_get(
        f"{GITHUB_API}/users/{clean_user}/repos",
        params={"sort": "pushed", "per_page": 30},
    )
    repos = repos_data if repos_status == "ok" and isinstance(repos_data, list) else []

    repo_score, has_python, has_ai, recent_names = _score_repos(repos)
    profile.has_python_repos = has_python
    profile.has_ai_repos = has_ai
    profile.recent_repo_names = recent_names

    # 4. Calculate combined GitHub score (capped at 10.0)
    activity_score = _score_activity(recent_pushes)
    profile.score = round(min(activity_score + repo_score, 10.0), 1)

    # 5. Build human-readable summary
    parts = [
        f"{profile.public_repos} public repos",
        f"{recent_pushes} pushes in last {RECENT_DAYS} days",
    ]
    if has_python:
        parts.append("Python repositories found")
    if has_ai:
        parts.append("AI/ML repositories found")
    if recent_names:
        parts.append(f"Active repos: {', '.join(recent_names[:3])}")
    
    if profile.public_repos == 0 and recent_pushes == 0:
        profile.enrichment_summary = "Verified GitHub profile with 0 public repositories and no recent public activity."
    else:
        profile.enrichment_summary = "; ".join(parts) + f". Score: {profile.score}/10."

    profile.enrichment_status = "success"
    _cache[cache_key] = profile
    return profile
