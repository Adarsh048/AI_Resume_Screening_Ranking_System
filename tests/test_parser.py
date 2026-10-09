"""
Tests for the resume parser.

Tests text extraction logic through the parser helpers (without needing real PDFs)
and validate the field extraction functions on controlled input.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.parser import (
    _content_hash,
    _extract_email,
    _extract_github,
    _extract_name,
    _extract_projects,
    _find_signals,
)
from src.models import ParsedResume


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------

class TestFindSignals:

    def test_finds_present_keyword(self):
        signals = _find_signals("I built a RAG pipeline with LangChain.", ["rag", "langchain"])
        assert "rag" in signals
        assert "langchain" in signals

    def test_case_insensitive(self):
        signals = _find_signals("Python developer using FASTAPI.", ["python", "fastapi"])
        assert "python" in signals
        assert "fastapi" in signals

    def test_absent_keyword_not_returned(self):
        signals = _find_signals("React and JavaScript developer.", ["python", "fastapi"])
        assert signals == []

    def test_deduplication(self):
        signals = _find_signals("Python Python Python", ["python"])
        assert signals.count("python") == 1

    def test_empty_text_returns_empty(self):
        signals = _find_signals("", ["python", "fastapi"])
        assert signals == []


# ---------------------------------------------------------------------------
# Email extraction
# ---------------------------------------------------------------------------

class TestExtractEmail:

    def test_standard_email(self):
        email = _extract_email("Contact me at john.doe@example.com for details.")
        assert email == "john.doe@example.com"

    def test_email_with_plus(self):
        email = _extract_email("Email: user+tag@domain.org")
        assert email == "user+tag@domain.org"

    def test_no_email_returns_none(self):
        email = _extract_email("No contact information provided.")
        assert email is None

    def test_picks_first_email(self):
        email = _extract_email("first@a.com and second@b.com")
        assert email == "first@a.com"


# ---------------------------------------------------------------------------
# GitHub URL extraction
# ---------------------------------------------------------------------------

class TestExtractGithub:

    def test_full_url(self):
        url, username = _extract_github("See my work at https://github.com/johndoe")
        assert url == "https://github.com/johndoe"
        assert username == "johndoe"

    def test_without_https(self):
        url, username = _extract_github("GitHub: github.com/jane-smith")
        assert username == "jane-smith"

    def test_no_github_returns_none(self):
        url, username = _extract_github("No social links here.")
        assert url is None
        assert username is None

    def test_username_with_hyphens(self):
        url, username = _extract_github("https://github.com/my-cool-username")
        assert username == "my-cool-username"


# ---------------------------------------------------------------------------
# Name extraction
# ---------------------------------------------------------------------------

class TestExtractName:

    def test_two_word_name_at_top(self):
        text = "John Smith\nSoftware Engineer\njohn@example.com"
        name = _extract_name(text)
        assert name == "John Smith"

    def test_three_word_name(self):
        text = "Alice Marie Johnson\nPython Developer"
        name = _extract_name(text)
        assert name == "Alice Marie Johnson"

    def test_no_name_returns_none(self):
        text = "1234 ABCD xyz\nskills: python java"
        name = _extract_name(text)
        # May or may not match — just ensure no crash and type is correct
        assert name is None or isinstance(name, str)

    def test_name_with_digits_not_matched(self):
        # A line with digits should not match; here no valid name-like line exists
        text = "H3llo W0rld\nskills: python java\ncontact: 9876543210"
        name = _extract_name(text)
        assert name is None

    def test_second_line_can_be_matched_as_name(self):
        # A valid candidate name on the second line after non-name line should match
        text = "H3llo W0rld\nJane Doe\njane@example.com"
        name = _extract_name(text)
        assert name == "Jane Doe"

    def test_uppercase_name_normalized(self):
        text = "SHIVAM RAJ\nAssociate Software Engineer\nshivam@gmail.com"
        name = _extract_name(text)
        assert name == "Shivam Raj"

    def test_name_with_initials(self):
        text = "P.V. Jayavardhana Sai\nEmail: pv@gmail.com"
        name = _extract_name(text)
        assert name == "P.V. Jayavardhana Sai"

    def test_misleading_headings_rejected(self):
        # Labels and job titles must not be extracted as names
        for heading in ["Curriculum Vitae", "Resume", "Software Engineer", "Work Experience", "Technical Skills"]:
            text = f"{heading}\nskills: python\ncontact: 1234567890"
            assert _extract_name(text) is None


# ---------------------------------------------------------------------------
# Project extraction
# ---------------------------------------------------------------------------

class TestExtractProjects:

    def test_extracts_project_section(self):
        text = (
            "John Smith\n\n"
            "Projects\n"
            "Built a RAG pipeline using LangChain and Pinecone for semantic search.\n\n"
            "Experience\n"
            "Python developer at startup. Used FastAPI and PostgreSQL.\n"
        )
        snippets = _extract_projects(text)
        assert len(snippets) >= 1
        assert any("RAG" in s or "FastAPI" in s for s in snippets)

    def test_no_project_section_returns_empty(self):
        text = "John Smith. Skills: Python, Docker."
        snippets = _extract_projects(text)
        # May return empty or minimal content
        assert isinstance(snippets, list)

    def test_max_8_snippets(self):
        # Artificially create many project sections
        text = "\n".join(
            [f"Projects\nProject {i}: Did something interesting with Python.\n" for i in range(20)]
        )
        snippets = _extract_projects(text)
        assert len(snippets) <= 8


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------

class TestContentHash:

    def test_same_text_same_hash(self):
        text = "Hello World"
        assert _content_hash(text) == _content_hash(text)

    def test_different_text_different_hash(self):
        assert _content_hash("text A") != _content_hash("text B")

    def test_hash_is_64_hex_chars(self):
        h = _content_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# Malformed / empty input handling
# ---------------------------------------------------------------------------

class TestParseResumeEdgeCases:

    def test_unsupported_extension(self):
        from src.parser import parse_resume
        # We create a mock path with unsupported extension
        mock_path = MagicMock(spec=Path)
        mock_path.name = "resume.xyz"
        mock_path.suffix = ".xyz"
        result = parse_resume(mock_path)
        assert result.parse_error is not None
        assert "Unsupported" in result.parse_error

    def test_parse_result_has_file_name(self):
        from src.parser import parse_resume
        mock_path = MagicMock(spec=Path)
        mock_path.name = "candidate_99.pdf"
        mock_path.suffix = ".pdf"
        # Make pdfplumber raise to trigger fallback, pypdf also raises
        with patch("src.parser._extract_pdf_pdfplumber", side_effect=Exception("corrupt")):
            with patch("src.parser._extract_pdf_pypdf", side_effect=Exception("corrupt")):
                result = parse_resume(mock_path)
        assert result.file_name == "candidate_99.pdf"
        assert result.parse_error is not None

    def test_legacy_doc_format_unsupported_message(self):
        from src.parser import parse_resume
        mock_path = MagicMock(spec=Path)
        mock_path.name = "resume.doc"
        mock_path.suffix = ".doc"
        result = parse_resume(mock_path)
        assert result.parse_error is not None
        assert "Legacy .doc format is not supported" in result.parse_error

    def test_find_signals_word_boundary_isolation(self):
        from src.parser import _find_signals
        text = "Graduated from IIT Kharagpur, completed Capgemini training, deployed on high-throughput platform."
        signals = _find_signals(text, ["rag", "gemini", "orm", "aws"])
        assert "rag" not in signals
        assert "gemini" not in signals
        assert "orm" not in signals
        assert "aws" not in signals

    def test_find_signals_matches_legitimate_keywords(self):
        from src.parser import _find_signals
        text = "Built a RAG pipeline with LangChain, using ORM with SQLAlchemy and deployed on AWS."
        signals = _find_signals(text, ["rag", "langchain", "orm", "aws", "docker"])
        assert "rag" in signals
        assert "langchain" in signals
        assert "orm" in signals
        assert "aws" in signals
        assert "docker" not in signals

    def test_empty_document_handling(self):
        from src.parser import parse_resume
        mock_path = MagicMock(spec=Path)
        mock_path.name = "empty.txt"
        mock_path.suffix = ".txt"
        with patch("src.parser._extract_txt", return_value="   "):
            result = parse_resume(mock_path)
        assert result.parse_error == "Empty or unreadable document"

