"""
Tests for the scoring engine.

Covers:
- Category ceiling enforcement
- Score totals stay in [0, 100]
- Project-quality penalties applied correctly
- Missing GitHub data does not disqualify
- Score breakdown consistency
"""

from __future__ import annotations

import pytest

from src.models import EligibilityResult, GitHubProfile, ParsedResume, ScoreBreakdown
from src.scorer import (
    compute_scores,
    score_ai_depth,
    score_cloud_deployment,
    score_engineering_depth,
    score_python_backend,
)


def make_resume(text: str, projects: list[str] | None = None) -> ParsedResume:
    r = ParsedResume(file_name="test.pdf", raw_text=text)
    r.project_descriptions = projects or []
    return r


def make_eligibility(has_python: bool = True, has_ai: bool = True) -> EligibilityResult:
    e = EligibilityResult()
    e.is_eligible = has_python and has_ai
    e.has_python = has_python
    e.has_ai_evidence = has_ai
    return e


def make_github(score: float = 0.0) -> GitHubProfile:
    g = GitHubProfile()
    g.score = score
    g.enrichment_status = "success" if score > 0 else "no_profile"
    return g


# ---------------------------------------------------------------------------
# ScoreBreakdown model tests
# ---------------------------------------------------------------------------

class TestScoreBreakdown:

    def test_total_sums_all_categories(self):
        bd = ScoreBreakdown(
            ai_rag_depth=20.0,
            python_backend=15.0,
            cloud_deployment=10.0,
            github_activity=5.0,
            engineering_depth=3.0,
        )
        assert bd.total == pytest.approx(53.0)

    def test_clamp_caps_each_category(self):
        bd = ScoreBreakdown(
            ai_rag_depth=99.0,
            python_backend=99.0,
            cloud_deployment=99.0,
            github_activity=99.0,
            engineering_depth=99.0,
        )
        bd.clamp()
        assert bd.ai_rag_depth == 40.0
        assert bd.python_backend == 30.0
        assert bd.cloud_deployment == 15.0
        assert bd.github_activity == 10.0
        assert bd.engineering_depth == 5.0
        assert bd.total == 100.0

    def test_clamp_floors_at_zero(self):
        bd = ScoreBreakdown(ai_rag_depth=-10.0, python_backend=-5.0)
        bd.clamp()
        assert bd.ai_rag_depth == 0.0
        assert bd.python_backend == 0.0

    def test_total_never_exceeds_100(self):
        bd = ScoreBreakdown(
            ai_rag_depth=40.0,
            python_backend=30.0,
            cloud_deployment=15.0,
            github_activity=10.0,
            engineering_depth=5.0,
        )
        assert bd.total <= 100.0


# ---------------------------------------------------------------------------
# AI depth scoring
# ---------------------------------------------------------------------------

class TestAIDepthScoring:

    def test_langgraph_scores_high(self):
        resume = make_resume("Built agentic workflows with LangGraph and tool calling.")
        score, notes = score_ai_depth(resume)
        assert score > 10.0
        assert score <= 40.0

    def test_rag_pipeline_scores(self):
        resume = make_resume(
            "Implemented a RAG pipeline with vector search using Pinecone. "
            "Used embeddings from HuggingFace. Built retrieval-augmented Q&A."
        )
        score, _ = score_ai_depth(resume)
        assert score > 15.0

    def test_shallow_wrapper_penalised(self):
        resume = make_resume("Built a simple chatbot wrapper around the OpenAI API. Tutorial project.")
        score, notes = score_ai_depth(resume)
        # Should have penalty applied, reducing score
        penalty_note = any("penalty" in n.lower() for n in notes)
        assert penalty_note or score < 10.0

    def test_empty_text_scores_zero(self):
        resume = make_resume("")
        score, _ = score_ai_depth(resume)
        assert score == 0.0

    def test_score_never_exceeds_40(self):
        # Pile in every AI keyword — should still cap at 40
        text = " ".join([
            "langgraph langchain llamaindex rag vector search embeddings",
            "pinecone faiss chroma qdrant openai anthropic gemini huggingface",
            "multi-agent tool calling agentic workflow evaluation pipeline ragas",
            "fine-tuning fine tuning prompt engineering semantic search",
        ])
        resume = make_resume(text)
        score, _ = score_ai_depth(resume)
        assert score <= 40.0

    def test_implementation_bonus_applied(self):
        projects = [
            "Implemented a RAG pipeline. Developed embeddings generation. Built retrieval system. "
            "Integrated vector store. Deployed agent."
        ]
        resume = make_resume("RAG embeddings langchain implemented", projects=projects)
        score_with_projects, _ = score_ai_depth(resume)
        resume_no_proj = make_resume("RAG embeddings langchain implemented")
        score_without, _ = score_ai_depth(resume_no_proj)
        # Should be equal or higher with projects
        assert score_with_projects >= score_without


# ---------------------------------------------------------------------------
# Python & Backend scoring
# ---------------------------------------------------------------------------

class TestPythonBackendScoring:

    def test_fastapi_postgres_scores(self):
        resume = make_resume("Built FastAPI backend with PostgreSQL and SQLAlchemy ORM.")
        score, _ = score_python_backend(resume, make_eligibility())
        assert score > 10.0

    def test_project_evidence_weighted_higher(self):
        project_text = "Built a FastAPI service with PostgreSQL. Implemented Redis caching."
        resume_with = make_resume("FastAPI PostgreSQL Redis Python", projects=[project_text])
        resume_without = make_resume("FastAPI PostgreSQL Redis Python")
        e = make_eligibility()
        score_with, _ = score_python_backend(resume_with, e)
        score_without, _ = score_python_backend(resume_without, e)
        assert score_with >= score_without

    def test_no_python_signals_scores_low(self):
        resume = make_resume("React developer. JavaScript. HTML. CSS. Node.js.")
        score, _ = score_python_backend(resume, make_eligibility(has_python=False))
        assert score < 5.0

    def test_score_never_exceeds_30(self):
        text = "python fastapi flask django asyncio pydantic sqlalchemy pytest celery postgresql redis"
        resume = make_resume(text)
        score, _ = score_python_backend(resume, make_eligibility())
        assert score <= 30.0


# ---------------------------------------------------------------------------
# Cloud / Deployment scoring
# ---------------------------------------------------------------------------

class TestCloudDeploymentScoring:

    def test_docker_gcp_scores(self):
        resume = make_resume("Containerised app with Docker, deployed on GCP with Kubernetes.")
        score, _ = score_cloud_deployment(resume)
        assert score > 5.0

    def test_no_cloud_signals_scores_zero(self):
        resume = make_resume("Built a Python CLI tool. Used SQLite locally.")
        score, _ = score_cloud_deployment(resume)
        assert score == 0.0

    def test_score_never_exceeds_15(self):
        text = "docker kubernetes aws gcp azure terraform ci/cd github actions react nextjs typescript"
        resume = make_resume(text)
        score, _ = score_cloud_deployment(resume)
        assert score <= 15.0


# ---------------------------------------------------------------------------
# Engineering depth scoring
# ---------------------------------------------------------------------------

class TestEngineeringDepthScoring:

    def test_testing_observability_scores(self):
        resume = make_resume("Pytest test suite. Rate limiting with Redis. Logging and observability.")
        score, _ = score_engineering_depth(resume)
        assert score > 0.0

    def test_score_never_exceeds_5(self):
        text = "pytest unit test tdd caching rate limit logging observability concurrency kafka rabbitmq"
        resume = make_resume(text)
        score, _ = score_engineering_depth(resume)
        assert score <= 5.0


# ---------------------------------------------------------------------------
# Combined compute_scores
# ---------------------------------------------------------------------------

class TestComputeScores:

    def test_missing_github_does_not_disqualify(self):
        resume = make_resume(
            "Python developer. LangChain RAG pipeline. FastAPI backend. PostgreSQL."
        )
        github = GitHubProfile()
        github.score = 0.0
        github.enrichment_status = "no_profile"
        scores, strengths, concerns = compute_scores(resume, make_eligibility(), github)
        assert scores.github_activity == 0.0
        assert scores.total > 0.0  # still scored on other categories

    def test_total_stays_in_range(self):
        resume = make_resume(
            "Python developer. LangGraph multi-agent RAG pipeline. FastAPI. "
            "Docker GCP. Pytest. Redis caching."
        )
        github = make_github(score=8.0)
        scores, _, _ = compute_scores(resume, make_eligibility(), github)
        assert 0.0 <= scores.total <= 100.0

    def test_github_score_capped_at_10(self):
        resume = make_resume("Python developer with AI projects.")
        github = make_github(score=15.0)  # inflated — should be clamped
        scores, _, _ = compute_scores(resume, make_eligibility(), github)
        assert scores.github_activity <= 10.0

    def test_strengths_and_concerns_are_lists_of_strings(self):
        resume = make_resume("Python. LangChain. RAG. FastAPI.")
        github = make_github(score=5.0)
        _, strengths, concerns = compute_scores(resume, make_eligibility(), github)
        assert all(isinstance(s, str) for s in strengths)
        assert all(isinstance(c, str) for c in concerns)

    def test_high_scorer_gets_strengths(self):
        resume = make_resume(
            "Python backend engineer. LangGraph multi-agent framework. RAG pipeline with Pinecone. "
            "FastAPI. PostgreSQL. Docker. GCP. Pytest suite. Redis caching. Kafka."
        )
        github = make_github(score=9.0)
        scores, strengths, concerns = compute_scores(resume, make_eligibility(), github)
        assert len(strengths) > 0
        assert scores.total > 50.0

    def test_missing_github_does_not_add_negative_concern(self):
        resume = make_resume("Python developer with AI and FastAPI experience.")
        github = GitHubProfile()
        github.enrichment_status = "no_username"
        github.score = 0.0
        _, _, concerns = compute_scores(resume, make_eligibility(), github)
        assert not any("github" in c.lower() for c in concerns)

    def test_ranking_sort_order_and_deterministic_tie_breaker(self):
        from src.models import CandidateResult

        c1 = CandidateResult(file_name="candidate_b.pdf")
        c1.scores.ai_rag_depth = 20.0
        c1.eligibility.is_eligible = True

        c2 = CandidateResult(file_name="candidate_a.pdf")
        c2.scores.ai_rag_depth = 20.0  # Identical score to c1
        c2.eligibility.is_eligible = True

        c3 = CandidateResult(file_name="candidate_c.pdf")
        c3.scores.ai_rag_depth = 30.0  # Higher score
        c3.eligibility.is_eligible = True

        candidates = [c1, c2, c3]
        candidates.sort(key=lambda r: (-r.scores.total, r.file_name))

        # Highest score first (c3)
        assert candidates[0].file_name == "candidate_c.pdf"
        # For tied scores (c1, c2), sorted alphabetically by file name (c2 then c1)
        assert candidates[1].file_name == "candidate_a.pdf"
        assert candidates[2].file_name == "candidate_b.pdf"

    def test_ineligible_candidates_remain_unranked(self):
        from src.models import CandidateResult

        eligible_candidate = CandidateResult(file_name="eligible.pdf")
        eligible_candidate.scores.ai_rag_depth = 25.0
        eligible_candidate.eligibility.is_eligible = True

        ineligible_candidate = CandidateResult(file_name="ineligible.pdf")
        ineligible_candidate.scores.ai_rag_depth = 0.0
        ineligible_candidate.eligibility.is_eligible = False

        results = [eligible_candidate, ineligible_candidate]
        eligible_only = [c for c in results if c.eligibility.is_eligible]
        eligible_only.sort(key=lambda r: (-r.scores.total, r.file_name))
        for rank, c in enumerate(eligible_only, start=1):
            c.rank = rank

        assert eligible_candidate.rank == 1
        assert ineligible_candidate.rank is None

    def test_score_caps_and_boundary_conditions(self):
        # Create an exaggerated resume with every possible keyword repeated multiple times
        huge_text = (
            "Python fastapi flask django asyncio pydantic sqlalchemy pytest celery postgresql redis orm "
            "langgraph langchain llamaindex rag vector store embeddings pinecone weaviate chroma tool calling "
            "docker kubernetes terraform aws gcp azure ci/cd github actions react typescript node.js "
            "unit test caching rate limit logging observability circuit breaker microservice kafka " * 5
        )
        resume = make_resume(huge_text, projects=[huge_text])
        github = make_github(score=15.0)  # Over-the-limit raw github score
        scores, _, _ = compute_scores(resume, make_eligibility(), github)

        # Confirm strict category caps
        assert scores.ai_rag_depth <= 40.0
        assert scores.python_backend <= 30.0
        assert scores.cloud_deployment <= 15.0
        assert scores.github_activity <= 10.0
        assert scores.engineering_depth <= 5.0
        assert scores.total <= 100.0
        assert scores.total == round(
            scores.ai_rag_depth + scores.python_backend + scores.cloud_deployment + scores.github_activity + scores.engineering_depth,
            2
        )

    def test_unsupported_ai_claims_in_skills_only_receive_discounted_credit(self):
        # Resume A lists AI signals only under SKILLS
        text_a = """
        SKILLS
        LangGraph, LangChain, RAG, Pinecone, Embeddings
        """
        resume_a = make_resume(text_a, projects=[])

        # Resume B lists the same AI signals in PROJECT descriptions
        text_b = """
        PROJECTS
        AI Search Engine:
        Built LangGraph workflow with LangChain and RAG using Pinecone and Embeddings.
        """
        resume_b = make_resume(text_b, projects=["Built LangGraph workflow with LangChain and RAG using Pinecone and Embeddings."])

        score_a, _ = score_ai_depth(resume_a)
        score_b, _ = score_ai_depth(resume_b)

        # Projects section evidence receives full credit, skills list alone receives discounted credit
        assert score_b > score_a

    def test_llm_adjustment_bounds_and_strength_consistency(self):
        from src.scorer import derive_strengths_and_concerns

        breakdown = ScoreBreakdown(
            ai_rag_depth=38.0,
            python_backend=25.0,
            cloud_deployment=10.0,
            github_activity=5.0,
            engineering_depth=3.0,
        )
        # Apply +5 adjustment (simulating LLM output)
        breakdown.ai_rag_depth = min(max(breakdown.ai_rag_depth + 5.0, 0.0), 40.0)
        breakdown.clamp()

        assert breakdown.ai_rag_depth == 40.0
        assert breakdown.total <= 100.0

        strengths, concerns = derive_strengths_and_concerns(breakdown)
        assert any("Strong AI" in s for s in strengths)
        assert not any("Limited AI" in c for c in concerns)

