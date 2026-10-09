# AI Resume Screening & Ranking System

An end-to-end resume screening, ranking, and visualization system for Python and AI engineering roles. It parses candidate resumes (PDF, DOCX, TXT), enforces deterministic hard eligibility filters, scores candidates across five engineering dimensions, enriches profiles with public GitHub activity using intelligent rate-limit tracking, optionally incorporates LLM project evaluation with a deterministic fallback, and presents results both as structured JSON and through an interactive React dashboard.

Built for the Kasparro SDE Intern Coding Assignment.

---

## Key Features

- **Multi-Format Resume Parsing**: Primary text extraction using `pdfplumber` with automatic fallback to `pypdf`, native `python-docx` for Word documents, and UTF-8 TXT decoding.
- **Robust Candidate Name Extraction**: Multi-pass heuristic distinguishing candidate names from headings, contact details, emails, job titles, institutions, and tools, while normalizing uppercase names and supporting initials.
- **Deterministic Hard Eligibility Filters**: Independent of LLM output. Enforces genuine Python experience (accepted across skills, projects, and work experience without arbitrary mention count limits) and verified AI/LLM/RAG/agentic implementations. Guards against isolated skills-list keyword stuffing while supporting custom AI architectures (e.g. PyTorch CNNs, embeddings, custom models).
- **100-Point Weighted Scoring Engine**:
  - AI / Agentic / RAG Project Depth: **40 pts**
  - Python & Backend Engineering: **30 pts**
  - Cloud / Deployment / Full Stack: **15 pts**
  - GitHub Activity: **10 pts**
  - Engineering Depth Signals: **5 pts**
- **Project-Quality Deductions**: Calibrated penalties (-5 to -15 pts) for shallow API wrappers and tutorial reproductions without implementation ownership.
- **Intelligent GitHub Enrichment**: Public GitHub REST API integration with in-memory username caching, active rate-limit tracking (`x-ratelimit-remaining`, `x-ratelimit-reset`, HTTP 403/429), and distinct status reporting (`success`, `not_found`, `rate_limited`, `failed`, `no_username`). Unavailable data is never treated as evidence of poor engineering.
- **Optional LLM Integration & Transparent Fallback**: Supports OpenAI (`gpt-4o-mini`) and Google Gemini (`gemini-1.5-flash`). Propagates `--no-llm` explicitly to ensure zero external provider calls when disabled. Gracefully falls back to deterministic project summaries if calls fail or keys are omitted.
- **Deterministic Ranking**: Eligible candidates ranked by total score descending, with ties broken deterministically by file name ascending.
- **React Web Dashboard**: Clean, responsive frontend built with React and Vanilla CSS (Vite) offering real-time search, skill filtering, candidate inspection modals, and CSV export.

---

## Architecture & Project Structure

```
AI_Resume_Screening_Ranking_System/
├── main.py                   # CLI entry point (argparse, logging, pipeline trigger)
├── src/
│   ├── __init__.py
│   ├── models.py             # Typed dataclasses (ParsedResume, CandidateResult, etc.)
│   ├── parser.py             # PDF/DOCX/TXT extraction, signal extraction & name parser
│   ├── eligibility.py        # Deterministic hard filters (Python + AI evidence)
│   ├── scorer.py             # 100-point scoring engine, penalties & explanation generator
│   ├── github_enrichment.py  # GitHub REST API client, rate-limit cooldown, caching
│   ├── llm_adapter.py        # Optional OpenAI/Gemini adapter & deterministic summary
│   └── pipeline.py           # End-to-end orchestrator & ranking pipeline
├── tests/
│   ├── __init__.py
│   ├── test_eligibility.py   # Eligibility rule tests & edge cases
│   ├── test_parser.py        # Name extraction, format parsing, signal matching
│   ├── test_scoring.py       # Score bounds, penalties, tie-breaking & explanations
│   ├── test_github.py        # Mocked GitHub API tests (404, 403, 429, timeouts, caching)
│   └── test_llm.py           # LLM adapter, fallback & CLI flag propagation tests
├── frontend/                 # React web dashboard
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── public/
│   │   └── results.json      # Linked screening results for local viewing
│   └── src/
│       ├── App.jsx           # Dashboard UI component with modals & CSV export
│       ├── main.jsx
│       └── index.css         # Clean, modern Vanilla CSS styling
├── resumes/                  # Dataset of 50 candidate PDF resumes
├── output/
│   └── results.json          # Generated batch screening results
├── requirements.txt          # Python dependencies
├── .env.example              # Template for API keys
└── .gitignore
```

---

## Installation & Setup

### Prerequisites
- **Python**: 3.10+ (tested on Python 3.13)
- **Node.js**: v18+ (tested on Node v24 for the React frontend)

### 1. Backend Setup
```bash
# Clone the repository
git clone https://github.com/your-username/AI_Resume_Screening_Ranking_System.git
cd AI_Resume_Screening_Ranking_System

# Create and activate a virtual environment
python -m venv .venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Frontend Setup
```bash
cd frontend
npm install
cd ..
```

---

## Environment Configuration

Copy `.env.example` to `.env` to configure optional API credentials:

```bash
cp .env.example .env
```

Available environment variables:
- `GITHUB_TOKEN`: *(Optional)* GitHub personal access token (raises rate limit from 60 to 5,000 req/hr).
- `OPENAI_API_KEY`: *(Optional)* Enables OpenAI LLM semantic evaluation.
- `OPENAI_MODEL`: Model name (default: `gpt-4o-mini`).
- `GEMINI_API_KEY`: *(Optional)* Enables Google Gemini evaluation.
- `GEMINI_MODEL`: Model name (default: `gemini-1.5-flash`).

*Note: All core screening and ranking features work out-of-the-box without any API keys.*

---

## Execution Instructions

### 1. Running the CLI Pipeline

**Standard run (deterministic fallback if no keys configured):**
```bash
python main.py --input ./resumes --output ./output/results.json
```

**Explicitly disable LLM calls (`--no-llm` flag):**
```bash
python main.py --input ./resumes --output ./output/results.json --no-llm
```

**Enable verbose DEBUG-level logging:**
```bash
python main.py --input ./resumes --output ./output/results.json --verbose
```

### 2. Running the React Dashboard

To launch the local web interface:
```bash
cd frontend
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser.

To create an optimized production build of the frontend:
```bash
cd frontend
npm run build
```

---

## Eligibility Rules

A candidate is marked eligible **only** when they satisfy both conditions:

1. **Python Evidence**:
   - Python appears as an explicit skill, programming language, in project descriptions, or alongside Python ecosystem tools (`FastAPI`, `Flask`, `Django`, `Pandas`, `NumPy`, `PyTorch`, etc.).
   - A genuine Python skill listed once is accepted without arbitrary count thresholds.
   - Candidates with JavaScript/Java/React-only stacks without Python are rejected.
   - Multi-stack candidates (e.g. React frontend + Python FastAPI backend) remain eligible.
2. **AI / Agentic Implementation Evidence**:
   - At least one meaningful AI, LLM, RAG, agentic, or custom machine learning implementation.
   - **Keyword-stuffing guard**: A framework listed *only* inside an isolated comma-separated skills list with no project or narrative evidence does not qualify.
   - **Custom AI support**: Custom neural networks, PyTorch classifiers, embeddings, or semantic search pipelines qualify even without commercial frameworks like LangChain.

---

## Scoring Methodology

Total score is bounded strictly between **0 and 100**:

| Category | Max Points | Evaluation Focus |
|---|:---:|---|
| **AI / RAG / Agentic Depth** | 40 | Multi-agent orchestration, LangGraph state, vector retrieval, evaluation pipelines, fine-tuning. Includes -5 to -12 penalty for shallow wrappers. |
| **Python & Backend** | 30 | FastAPI, Flask, AsyncIO, relational databases (PostgreSQL), Redis caching, ORMs, work/internship experience. |
| **Cloud & Deployment** | 15 | Docker containerization, Kubernetes, CI/CD pipelines, AWS/GCP, full-stack frameworks (React/Next.js/TypeScript). |
| **GitHub Activity** | 10 | Recent 90-day public pushes (up to 5 pts) and maintained repositories with Python/AI signals (up to 5 pts). |
| **Engineering Depth** | 5 | Pytest testing practices, concurrency, rate limiting, logging, observability, and clean architecture. |

**Tie-Breaking Rule**:
Eligible candidates are sorted by `total_score` descending. When scores are identical, ties are broken deterministically by `file_name` ascending.

---

## GitHub Enrichment & Rate-Limit Handling

- All requests to GitHub public REST endpoints (`/users/{username}`, `/events/public`, `/repos`) are wrapped in safe HTTP handlers.
- **Rate Limit Tracking**: Inspects `x-ratelimit-remaining` and `x-ratelimit-reset`. When HTTP 403 (rate limit) or HTTP 429 is received, a cooldown deadline is recorded. Subsequent candidates immediately receive `rate_limited` status without making redundant failing network requests or blocking the batch.
- **Distinct Statuses**:
  - `success`: Profile fetched, repos evaluated.
  - `not_found`: Profile does not exist (HTTP 404).
  - `rate_limited`: Rate limit reached; score defaulted to 0.0 without penalizing the candidate.
  - `failed`: Network timeout or connection failure.
  - `no_username`: No GitHub profile link present on the resume.
- GitHub score is an **optional positive signal** (capped at 10 pts) and is never required for eligibility.

---

## LLM Integration & Fallback

- When enabled and configured with an API key, the LLM evaluates extracted project text and can apply a bounded adjustment (`-5` to `+5`) to the AI depth category.
- When `--no-llm` is provided, all LLM calls are completely bypassed.
- If provider calls fail or encounter timeouts, the system transparently logs an informational message and returns a deterministic project summary without halting batch execution.
- Strengths and concerns are automatically recalculated after any score adjustment to ensure full qualitative consistency.

---

## Testing

The project includes an automated test suite with **96 tests** across 5 modules:

```bash
# Run the complete test suite
python -m pytest -v
```

### Test Coverage Highlights:
- `test_eligibility.py`: Single-mention Python acceptance, Java/JS-only rejection, multi-language stacks, custom AI architectures, and skills-only keyword stuffing guard.
- `test_parser.py`: Multi-layout name extraction, uppercase normalization, initials, labels/headings rejection, email & GitHub extraction, deduplication hash.
- `test_scoring.py`: Category ceilings, total score limits [0, 100], wrapper penalties, ranking sort order, deterministic tie-breaking, and explanation consistency.
- `test_github.py`: Mocked HTTP responses for 200 OK, 404 Not Found, 403 Rate Limit, 429 Too Many Requests, timeouts, caching, and active cooldown backoff.
- `test_llm.py`: CLI `--no-llm` flag parsing, provider bypass, missing API keys fallback, and provider error recovery.

---

## Design Decisions

1. **Deterministic Eligibility Over LLM Filtering**: Hard qualification thresholds are 100% deterministic rule-based checks. This ensures complete auditability, zero hallucinations, and zero API cost for filtering out unqualified resumes.
2. **Single-Pass Cooldown for External APIs**: Tracking rate-limit state in memory prevents catastrophic execution slowdowns when screening large batches on unauthenticated GitHub rate limits (60 req/hr).
3. **Bounded Adjustments**: Any LLM-derived adjustment is strictly bounded to `[-5, +5]` and capped within the 40-point category maximum, preventing prompt injections or model variance from distorting candidate rank.

---

## Known Limitations

- **Complex Multi-Column PDF Reflow**: While `pdfplumber` performs well on standard resume layouts, complex non-standard multi-column layouts with floating text blocks may require OCR for perfect line sequencing.
- **GitHub Unauthenticated Rate Limit**: Without a `GITHUB_TOKEN`, public GitHub API limits allow ~60 calls per hour (roughly 20 candidates). Supplying a free personal access token raises this to 5,000 req/hr.
- **Single-Threaded Processing**: The pipeline processes files sequentially to respect external API rate limits; for larger datasets (e.g. 10,000 resumes), an asynchronous job queue (e.g. Celery / Redis) would be recommended.

---

## If I Had More Time

- **Asynchronous Enrichment Queue**: Implement an async worker architecture with exponential backoff for concurrent resume parsing and parallel API enrichment.
- **Resume PDF Highlighting in Frontend**: Add an in-browser PDF viewer that highlights extracted evidence snippets directly within the original resume document.
- **Custom Screening Weights UI**: Allow recruiters to adjust category weights (e.g. weighting Cloud higher for DevOps-heavy roles) directly from the dashboard.
