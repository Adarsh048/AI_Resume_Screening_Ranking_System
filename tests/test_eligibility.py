"""
Tests for the eligibility filter module.

Covers:
- Python evidence present / absent
- AI evidence present / absent
- Both requirements present
- Edge cases: minimal text, no text
"""

from __future__ import annotations

import pytest

from src.eligibility import check_ai_evidence, check_python_evidence, evaluate_eligibility
from src.models import ParsedResume


def make_resume(text: str) -> ParsedResume:
    r = ParsedResume(file_name="test.pdf", raw_text=text)
    return r


# ---------------------------------------------------------------------------
# Python evidence tests
# ---------------------------------------------------------------------------

class TestPythonEvidence:

    def test_python_mentioned_twice_passes(self):
        resume = make_resume("Python developer. Built a Python web scraper.")
        passes, evidence = check_python_evidence(resume)
        assert passes is True
        assert len(evidence) > 0

    def test_python_with_fastapi_passes(self):
        resume = make_resume("Skills: JavaScript, Python. Built APIs using FastAPI.")
        passes, _ = check_python_evidence(resume)
        assert passes is True

    def test_python_with_pandas_passes(self):
        resume = make_resume("Used Python and Pandas for data analysis.")
        passes, _ = check_python_evidence(resume)
        assert passes is True

    def test_no_python_fails(self):
        resume = make_resume("Experienced React developer. Built UIs with JavaScript and TypeScript.")
        passes, evidence = check_python_evidence(resume)
        assert passes is False
        assert evidence == []

    def test_python_genuine_skill_listed_once_passes(self):
        # A genuine Python skill listed once in languages/skills passes
        resume = make_resume("Languages: Java, Python, C++")
        passes, _ = check_python_evidence(resume)
        assert passes is True

    def test_javascript_react_only_without_python_fails(self):
        # JavaScript/React only profiles with zero Python fail
        resume = make_resume("Full stack developer skilled in JavaScript, React.js, Node.js, and Express.")
        passes, _ = check_python_evidence(resume)
        assert passes is False

    def test_python_alongside_javascript_react_passes(self):
        # Candidates using JavaScript and React alongside Python pass
        resume = make_resume("Full stack developer using React frontend and Python FastAPI backend.")
        passes, _ = check_python_evidence(resume)
        assert passes is True

    def test_python_primary_language_pattern(self):
        resume = make_resume("Python developer with 2 years experience building REST APIs.")
        passes, _ = check_python_evidence(resume)
        assert passes is True

    def test_empty_resume_fails(self):
        resume = make_resume("")
        passes, evidence = check_python_evidence(resume)
        assert passes is False
        assert evidence == []


# ---------------------------------------------------------------------------
# AI evidence tests
# ---------------------------------------------------------------------------

class TestAIEvidence:

    def test_langchain_passes(self):
        resume = make_resume("Built a RAG pipeline using LangChain and OpenAI.")
        passes, evidence = check_ai_evidence(resume)
        assert passes is True
        assert len(evidence) > 0

    def test_rag_alone_passes(self):
        resume = make_resume("Implemented a RAG system for document question answering.")
        passes, _ = check_ai_evidence(resume)
        assert passes is True

    def test_vector_search_passes(self):
        resume = make_resume("Deployed vector search using Pinecone for semantic retrieval.")
        passes, _ = check_ai_evidence(resume)
        assert passes is True

    def test_multi_agent_passes(self):
        resume = make_resume("Built a multi-agent workflow using LangGraph for task orchestration.")
        passes, _ = check_ai_evidence(resume)
        assert passes is True

    def test_embeddings_passes(self):
        resume = make_resume("Generated embeddings using HuggingFace and stored in ChromaDB.")
        passes, _ = check_ai_evidence(resume)
        assert passes is True

    def test_no_ai_evidence_fails(self):
        resume = make_resume("Python developer. Built REST APIs with FastAPI and PostgreSQL.")
        passes, evidence = check_ai_evidence(resume)
        assert passes is False
        assert evidence == []

    def test_javascript_react_only_no_ai_fails(self):
        resume = make_resume("React developer. Built SPAs using JavaScript. Experienced with Node.js.")
        passes, _ = check_ai_evidence(resume)
        assert passes is False

    def test_broad_ai_signal_chatbot_passes(self):
        resume = make_resume("Built a chatbot using GPT-4 for customer service automation.")
        passes, _ = check_ai_evidence(resume)
        assert passes is True

    def test_ai_framework_only_in_skills_list_without_project_fails(self):
        # A framework mentioned only in skills list with no project or narrative does not prove AI project
        text = "Technical Skills: Python, LangChain, React\nProjects: Built a simple blog web application with Django."
        resume = make_resume(text)
        resume.project_descriptions = ["Built a simple blog web application with Django."]
        passes, _ = check_ai_evidence(resume)
        assert passes is False

    def test_custom_ai_implementation_without_framework_passes(self):
        # Custom AI implementation (deep learning CNN) passes without famous LLM frameworks
        text = (
            "Projects: Computer Vision Classifier\n"
            "Trained a deep learning convolutional neural network in PyTorch with loss optimization "
            "and evaluation metrics for object detection."
        )
        resume = make_resume(text)
        resume.project_descriptions = [text]
        passes, _ = check_ai_evidence(resume)
        assert passes is True


# ---------------------------------------------------------------------------
# Combined eligibility tests
# ---------------------------------------------------------------------------

class TestEvaluateEligibility:

    def test_both_pass_eligible(self):
        resume = make_resume(
            "Python developer. Built a RAG pipeline with LangChain, FastAPI backend, "
            "PostgreSQL for storage. Deployed on GCP with Docker."
        )
        result = evaluate_eligibility(resume)
        assert result.is_eligible is True
        assert result.has_python is True
        assert result.has_ai_evidence is True
        assert result.rejection_reasons == []

    def test_python_only_rejected(self):
        resume = make_resume(
            "Python developer. FastAPI REST API with PostgreSQL and Redis. "
            "Deployed using Docker on AWS. Pytest test suite."
        )
        result = evaluate_eligibility(resume)
        assert result.is_eligible is False
        assert result.has_python is True
        assert result.has_ai_evidence is False
        assert len(result.rejection_reasons) == 1
        assert "AI" in result.rejection_reasons[0]

    def test_ai_only_no_python_rejected(self):
        resume = make_resume(
            "Built a RAG system using LangChain. JavaScript developer. "
            "React frontend with Next.js. OpenAI API integration."
        )
        result = evaluate_eligibility(resume)
        # Has AI, but no sufficient Python evidence
        assert result.has_ai_evidence is True
        assert result.is_eligible is False
        assert any("Python" in r for r in result.rejection_reasons)

    def test_neither_rejected(self):
        resume = make_resume("Java developer. Spring Boot REST APIs. MySQL database. Maven build.")
        result = evaluate_eligibility(resume)
        assert result.is_eligible is False
        assert len(result.rejection_reasons) == 2

    def test_empty_resume_rejected(self):
        resume = make_resume("")
        result = evaluate_eligibility(resume)
        assert result.is_eligible is False

    def test_rejection_reasons_are_strings(self):
        resume = make_resume("Java developer")
        result = evaluate_eligibility(resume)
        assert all(isinstance(r, str) for r in result.rejection_reasons)

    def test_evidence_lists_populated_when_eligible(self):
        resume = make_resume(
            "Python backend engineer. Built RAG pipeline with LangChain embeddings. "
            "Python asyncio for concurrency. FastAPI endpoints."
        )
        result = evaluate_eligibility(resume)
        assert result.is_eligible is True
        assert len(result.python_evidence) > 0
        assert len(result.ai_evidence) > 0
