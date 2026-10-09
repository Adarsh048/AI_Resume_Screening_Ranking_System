"""
Tests for GitHub enrichment, rate-limit detection, error recovery, and caching.
All external network calls are mocked deterministically.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.github_enrichment import enrich_github, is_rate_limited, reset_github_cache


@pytest.fixture(autouse=True)
def clean_github_state():
    reset_github_cache()
    yield
    reset_github_cache()


class TestGitHubEnrichment:

    def test_no_username_returns_distinct_status(self):
        profile = enrich_github(None)
        assert profile.enrichment_status == "no_username"
        assert profile.score == 0.0

        profile_empty = enrich_github("   ")
        assert profile_empty.enrichment_status == "no_username"
        assert profile_empty.score == 0.0

    def test_successful_profile_and_repos_scored(self):
        user_resp = MagicMock()
        user_resp.status_code = 200
        user_resp.headers = {"x-ratelimit-remaining": "50"}
        user_resp.json.return_value = {"public_repos": 5}

        events_resp = MagicMock()
        events_resp.status_code = 200
        events_resp.headers = {"x-ratelimit-remaining": "49"}
        events_resp.json.return_value = [
            {"type": "PushEvent", "created_at": "2026-09-01T12:00:00Z"},
            {"type": "PushEvent", "created_at": "2026-09-02T12:00:00Z"},
        ]

        repos_resp = MagicMock()
        repos_resp.status_code = 200
        repos_resp.headers = {"x-ratelimit-remaining": "48"}
        repos_resp.json.return_value = [
            {"name": "rag-agent", "language": "Python", "topics": ["langchain", "rag"], "updated_at": "2026-09-01T00:00:00Z"},
        ]

        with patch("requests.get", side_effect=[user_resp, events_resp, repos_resp]):
            profile = enrich_github("testdev")

            assert profile.enrichment_status == "success"
            assert profile.username == "testdev"
            assert profile.public_repos == 5
            assert profile.has_python_repos is True
            assert profile.has_ai_repos is True
            assert profile.score > 0.0
            assert profile.score <= 10.0

    def test_missing_profile_404_returns_not_found_status(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {"x-ratelimit-remaining": "55"}

        with patch("requests.get", return_value=mock_resp):
            profile = enrich_github("nonexistentuser1234567")
            assert profile.enrichment_status == "not_found"
            assert profile.score == 0.0
            assert "404" in profile.enrichment_summary

    def test_rate_limit_403_detected_and_stops_redundant_requests(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "API rate limit exceeded for 127.0.0.1"
        mock_resp.headers = {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "2000000000"}

        with patch("requests.get", return_value=mock_resp) as mock_get:
            profile1 = enrich_github("candidateA")
            assert profile1.enrichment_status == "rate_limited"
            assert profile1.score == 0.0

            # Next candidate should hit active rate-limiting backoff without making new HTTP calls
            calls_before = mock_get.call_count
            profile2 = enrich_github("candidateB")
            assert profile2.enrichment_status == "rate_limited"
            assert profile2.score == 0.0
            # Ensure no additional HTTP request was fired because rate-limit was already recorded
            assert mock_get.call_count == calls_before

    def test_rate_limit_429_detected(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"x-ratelimit-remaining": "0"}

        with patch("requests.get", return_value=mock_resp):
            profile = enrich_github("candidate_429")
            assert profile.enrichment_status == "rate_limited"
            assert profile.score == 0.0

    def test_network_timeout_or_500_error_returns_failed_status(self):
        with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out")):
            profile = enrich_github("timeout_user")
            assert profile.enrichment_status == "failed"
            assert profile.score == 0.0
            assert "timeout" in profile.enrichment_summary.lower() or "error" in profile.enrichment_summary.lower()

    def test_verified_profile_with_zero_activity(self):
        user_resp = MagicMock()
        user_resp.status_code = 200
        user_resp.headers = {"x-ratelimit-remaining": "50"}
        user_resp.json.return_value = {"public_repos": 0}

        events_resp = MagicMock()
        events_resp.status_code = 200
        events_resp.headers = {"x-ratelimit-remaining": "49"}
        events_resp.json.return_value = []

        repos_resp = MagicMock()
        repos_resp.status_code = 200
        repos_resp.headers = {"x-ratelimit-remaining": "48"}
        repos_resp.json.return_value = []

        with patch("requests.get", side_effect=[user_resp, events_resp, repos_resp]):
            profile = enrich_github("empty_user")
            assert profile.enrichment_status == "success"
            assert profile.score == 0.0
            assert "0 public repositories" in profile.enrichment_summary

    def test_caching_for_repeated_username(self):
        user_resp = MagicMock()
        user_resp.status_code = 200
        user_resp.headers = {"x-ratelimit-remaining": "50"}
        user_resp.json.return_value = {"public_repos": 2}

        events_resp = MagicMock()
        events_resp.status_code = 200
        events_resp.headers = {"x-ratelimit-remaining": "49"}
        events_resp.json.return_value = []

        repos_resp = MagicMock()
        repos_resp.status_code = 200
        repos_resp.headers = {"x-ratelimit-remaining": "48"}
        repos_resp.json.return_value = []

        with patch("requests.get", side_effect=[user_resp, events_resp, repos_resp]) as mock_get:
            p1 = enrich_github("dev_repeat")
            p2 = enrich_github("dev_repeat")
            assert p1 is p2
            # Requests made only for the first call
            assert mock_get.call_count == 3
