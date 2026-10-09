"""
Tests for LLM adapter, fallback behavior, and CLI configuration propagation.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from main import build_parser
from src.llm_adapter import evaluate_with_llm


class TestLLMConfiguration:

    def test_cli_parser_no_llm_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--no-llm"])
        assert args.no_llm is True

    def test_cli_parser_default_uses_llm(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.no_llm is False

    def test_evaluate_with_llm_disabled_never_calls_providers(self):
        with patch("src.llm_adapter._call_openai") as mock_openai, \
             patch("src.llm_adapter._call_gemini") as mock_gemini:
            summary, adjustment, llm_used = evaluate_with_llm(
                project_descriptions=["Built an AI agent system with LangGraph."],
                ai_signals=["langgraph", "rag"],
                enabled=False,
            )

            assert llm_used is False
            assert adjustment == 0.0
            assert isinstance(summary, str)
            assert len(summary) > 0
            # Providers must never be invoked when enabled is False
            mock_openai.assert_not_called()
            mock_gemini.assert_not_called()

    def test_fallback_when_no_api_keys(self):
        # Even with enabled=True, missing API keys falls back cleanly without crashing
        with patch.dict(os.environ, {}, clear=True):
            summary, adjustment, llm_used = evaluate_with_llm(
                project_descriptions=["Built an AI RAG pipeline."],
                ai_signals=["rag"],
                enabled=True,
            )
            assert llm_used is False
            assert adjustment == 0.0
            assert "AI/LLM signals detected" in summary or "RAG" in summary

    def test_fallback_when_provider_fails(self):
        # A failed LLM provider call returns fallback without crashing
        with patch("src.llm_adapter._call_openai", side_effect=RuntimeError("API Network Timeout")):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake-test-key"}):
                summary, adjustment, llm_used = evaluate_with_llm(
                    project_descriptions=["LangGraph agent copilot."],
                    ai_signals=["langgraph"],
                    enabled=True,
                )
                assert llm_used is False
                assert adjustment == 0.0
                assert isinstance(summary, str)

    def test_valid_llm_response_applies_adjustment(self):
        mock_response = {
            "project_summary": "High-depth multi-agent system with verified evaluation.",
            "ai_depth_adjustment": 3.0,
            "depth_rationale": "Shows real multi-agent coordination.",
        }
        with patch("src.llm_adapter._openai_available", True), \
             patch("src.llm_adapter._call_openai", return_value=mock_response):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake-test-key"}):
                summary, adjustment, llm_used = evaluate_with_llm(
                    project_descriptions=["Complex multi-agent pipeline."],
                    ai_signals=["multi-agent"],
                    enabled=True,
                )
                assert llm_used is True
                assert adjustment == 3.0
                assert summary == mock_response["project_summary"]

    def test_gemini_provider_path(self):
        mock_response = {
            "project_summary": "Gemini-evaluated RAG architecture.",
            "ai_depth_adjustment": 2.0,
            "depth_rationale": "Solid retrieval architecture.",
        }
        with patch("src.llm_adapter._gemini_available", True), \
             patch("src.llm_adapter._call_gemini", return_value=mock_response):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-gemini-key"}, clear=True):
                summary, adjustment, llm_used = evaluate_with_llm(
                    project_descriptions=["RAG architecture with vector search."],
                    ai_signals=["rag"],
                    enabled=True,
                )
                assert llm_used is True
                assert adjustment == 2.0
                assert summary == mock_response["project_summary"]

    def test_adjustment_outside_allowed_range_rejected(self):
        # Out-of-bounds adjustment (e.g. +10) must be rejected by validator
        invalid_response = {
            "project_summary": "Attempted arbitrary score inflation.",
            "ai_depth_adjustment": 10.0,
            "depth_rationale": "Over maximum allowed bonus.",
        }
        with patch("src.llm_adapter._openai_available", True), \
             patch("src.llm_adapter._call_openai", return_value=invalid_response):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake-test-key"}):
                summary, adjustment, llm_used = evaluate_with_llm(
                    project_descriptions=["Some project."],
                    ai_signals=["ai"],
                    enabled=True,
                )
                assert llm_used is False
                assert adjustment == 0.0

    def test_malformed_llm_response_handled_gracefully(self):
        # Missing required fields
        malformed_response = {"wrong_field": 123}
        with patch("src.llm_adapter._openai_available", True), \
             patch("src.llm_adapter._call_openai", return_value=malformed_response):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake-test-key"}):
                summary, adjustment, llm_used = evaluate_with_llm(
                    project_descriptions=["Some project."],
                    ai_signals=["ai"],
                    enabled=True,
                )
                assert llm_used is False
                assert adjustment == 0.0

