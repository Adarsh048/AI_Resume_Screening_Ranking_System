# AI Resume Screening & Ranking System

An automated resume screening, scoring, and ranking pipeline built to evaluate candidates for Python and AI engineering roles. 

The system processes resumes in batch (PDF, DOCX, TXT), extracts text and metadata, verifies hard eligibility rules (distinguishing between real implementation experience and mere keyword stuffing), enriches candidate profiles with public GitHub activity, scores candidates across a 100-point rubric, and presents the results in an interactive React dashboard.

---

## What It Will Do

When you feed resumes into this system, here is what happens step by step:

1. **Ingestion & Duplicate Detection**:
   - Reads `.pdf`, `.docx`, and `.txt` files from the input directory.
   - Calculates a SHA-256 hash of the extracted text so identical resumes are immediately identified and flagged.
   - Extracts candidate identity: full name, email address, and GitHub handle.

2. **Hard Eligibility Filtering (Strict Qualification Rules)**:
   - **Python Check**: Verifies that the candidate actually knows and uses Python (in projects, work experience, or core skills). Candidates with only Java, JavaScript, or C++ and no Python are disqualified.
   - **AI / ML / Agentic Experience Check**: Verifies that the candidate has real project or work experience in AI, LLMs, RAG, multi-agent frameworks, computer vision, or machine learning.
   - **Guards Against Keyword Stuffing**: Candidates who simply list keywords like `PyTorch`, `TensorFlow`, `Keras`, `RAG`, or `AI-powered` in a bulleted skills section without any corresponding project or work experience are **disqualified**. The system requires action verbs (e.g. *built, trained, fine-tuned, implemented, deployed*) and technical context (e.g. *model, pipeline, embeddings, latency, accuracy*).
   - **Custom AI Support**: Recognizes genuine custom machine learning and deep learning work (such as CNNs, PyTorch classifiers, embeddings, or OpenCV pipelines), even if the candidate did not use third-party frameworks like LangChain or LlamaIndex.

3. **Public GitHub Enrichment**:
   - Queries GitHub's public REST API for the candidate's username.
   - Checks total public repositories, commits/pushes in the last 90 days, and repositories matching Python and AI topics.
   - **Rate-Limit Safe**: Monitors response headers (`x-ratelimit-remaining`, `x-ratelimit-reset`) and HTTP 403/429 codes. If unauthenticated rate limits (60 requests/hour) are reached, the system pauses further requests and tags profiles as `rate_limited` rather than failing the batch.
   - **Fair Evaluation**: A missing GitHub handle or API rate limit is marked as `no_username` or `rate_limited` and is **never** used to disqualify a candidate or count as a negative engineering mark.

4. **100-Point Rubric Scoring**:
   - Evaluates each eligible candidate across five categories:
     - **AI / Agentic / RAG Depth (40 pts)**: Multi-agent systems, LangGraph, vector search, embeddings, RAG architectures, custom training. Real project experience gets full credit; skills-only mentions receive heavily discounted credit. Shallow API wrapper projects receive a penalty (-5 to -12 pts).
     - **Python & Backend Engineering (30 pts)**: FastAPI, Flask, Django, AsyncIO, databases (PostgreSQL, SQLite), Redis caching, and ORMs. Project evidence is weighted higher (1.5×) than raw keyword lists.
     - **Cloud & Deployment (15 pts)**: Docker, Kubernetes, CI/CD pipelines, AWS/GCP, full-stack frameworks (React, Next.js, TypeScript).
     - **GitHub Activity (10 pts)**: Public repositories, recent pushes in the past 90 days, and active Python/AI repositories.
     - **Engineering Depth (5 pts)**: Automated testing (pytest), concurrency, error handling, rate limiting, and logging.
   - Automatically generates human-readable bullet points detailing candidate strengths and observations.

5. **Optional LLM Semantic Review**:
   - Supports OpenAI (`gpt-4o-mini`) or Google Gemini (`gemini-1.5-flash`) to generate concise project summaries and apply a fine-tuning adjustment between `-5` and `+5` points to the AI depth category.
   - Strictly bounded: The LLM cannot change eligibility, cannot bypass category caps, and cannot adjust total scores outside the permitted range.
   - When run with `--no-llm` (or when no API keys are present), the system runs 100% deterministically and extracts project summaries directly from the resume text.

6. **Deterministic Ranking & Automatic Data Sync**:
   - Ranks eligible candidates strictly in descending order of total score. Ties are broken deterministically by filename ascending.
   - Ineligible candidates remain unranked in a dedicated rejected section.
   - Automatically writes results to `output/results.json` and syncs them to `frontend/public/results.json`, so the React dashboard updates immediately.

7. **Interactive React Web Dashboard**:
   - Recruiter-focused web interface to browse results.
   - Allows filtering by eligibility status (`Eligible`, `Rejected`, `All`), searching by candidate name, email, or skill, filtering by minimum score, and sorting by any category.
   - Detailed modal view for each candidate displaying category breakdowns, exact text evidence snippets, GitHub status, strengths, and concerns.

---

## What All I Used (Tech Stack & Tools)

### Backend & Core Logic
- **Python 3.13 / 3.10+**: Core programming language for data extraction, parsing, scoring, and CLI tooling.
- **pdfplumber (v0.11+)**: Primary PDF text extraction library. Selected because it extracts text with precise character layout and handles multi-column resume formats much more reliably than standard text dumpers.
- **pypdf (v4.0+)**: Secondary PDF extraction library used as an automatic fallback if a malformed PDF causes `pdfplumber` to fail.
- **python-docx (v1.1+)**: Used to parse Microsoft Word `.docx` resumes by reading paragraph blocks and table cells.
- **requests (v2.31+)**: Handles HTTP communication with GitHub's REST API (`/users`, `/events/public`, `/repos`).
- **python-dotenv (v1.0+)**: Reads local environment variables from `.env` without hardcoding sensitive API tokens.

### Python Standard Library (Built-ins Used Heavily)
- **`dataclasses`**: Strongly typed data models (`ParsedResume`, `EligibilityResult`, `GitHubProfile`, `ScoreBreakdown`, `CandidateResult`) ensuring consistent object contracts across the pipeline.
- **`re`**: Regular expressions used for section header detection, email extraction, GitHub handle parsing, and word-boundary keyword matching (`\b<keyword>\b`).
- **`hashlib`**: SHA-256 content hashing to flag duplicate resumes.
- **`argparse`**: Clean command-line interface with flags (`--input`, `--output`, `--no-llm`, `--verbose`).
- **`pathlib` & `logging`**: Cross-platform path handling and structured pipeline logging.
- **`json`**: Structured data serialization and deserialization.

### Testing & QA
- **pytest (v8.0+)**: Automated testing framework. The project includes 116 unit and integration tests across 5 test suites.
- **unittest.mock**: Used to mock GitHub API responses (success, 404, 403, 429, timeouts) and LLM providers. This ensures the entire test suite runs offline in under 2 seconds without requiring internet access or paid API credits.

### Optional LLM Providers
- **openai (v1.30+)**: Optional integration for OpenAI Chat Completions (`gpt-4o-mini`).
- **google-generativeai (v0.7+)**: Optional integration for Google Gemini (`gemini-1.5-flash`).

### Frontend Dashboard
- **React 19**: Modern component architecture for state management and rendering.
- **Vite 8**: Development server and production build bundler.
- **Vanilla CSS**: Custom styling with CSS custom properties (variables), responsive flexbox/grid layouts, clean card components, and modal dialogues. No heavy utility frameworks or extra build layers.
- **lucide-react**: Clean, lightweight SVG icons for navigation, badges, and candidate cards.

---

## The First Steps I Done (Chronological Development Walkthrough)

Here is the step-by-step progression of how I planned, designed, and built this project from the ground up:

### Step 1: Analyzing the Requirements & Setting Up the Environment
- Read the assignment requirements carefully: the system had to process 50 real resumes, filter candidates strictly on Python and AI/agentic experience, enrich with GitHub, score on a 100-point rubric, support optional LLM summaries, and provide a React interface.
- Created the project folder structure:
  - `src/` for backend modules.
  - `tests/` for automated test suites.
  - `resumes/` to store the 50 candidate PDF files.
  - `output/` for output JSON files.
  - `frontend/` for the React dashboard.
- Initialized a Python virtual environment (`python -m venv .venv`), set up `requirements.txt`, and configured `.gitignore` to keep out `__pycache__`, virtual environments, node modules, build artifacts, and secret keys.

### Step 2: Designing Data Contracts First (`src/models.py`)
Rather than passing loose dictionaries between functions, I defined typed dataclasses first so every component had clear input and output contracts:
- `ParsedResume`: Carries raw text, detected name, email, GitHub handle, matched skills, project descriptions, SHA-256 hash, and parse errors.
- `EligibilityResult`: Carries boolean flags (`is_eligible`, `has_python`, `has_ai_evidence`), reason for decision, and extracted evidence snippets.
- `GitHubProfile`: Carries public repo counts, recent 90-day push count, AI/Python repo flags, enrichment status, and calculated score (0 to 10).
- `ScoreBreakdown`: Holds category scores with strict ceilings and floors, plus the total score.
- `CandidateResult`: The final object combining parsed metadata, eligibility status, scores, ranking, qualitative strengths, and concerns.

### Step 3: Building the Resume Parser (`src/parser.py`)
- **Multi-Format Extraction**: Used `pdfplumber` as the primary extractor for PDF files. Wrapped it in an exception handler that falls back to `pypdf` if a document has encoding issues. Added `python-docx` for `.docx` files and standard UTF-8 reading for `.txt`.
- **Handling Legacy `.doc` Files**: Encountered binary `.doc` files during testing. Since `python-docx` only supports modern XML `.docx`, I added an explicit check that flags legacy `.doc` files with a clear error message instead of letting the script crash.
- **Candidate Name Extraction**: Resumes have diverse formats. I wrote a heuristic that inspects the top lines of the document, filters out noise (e.g. `"Resume"`, `"Curriculum Vitae"`, `"Education"`, phone numbers, email addresses, and URLs), and normalizes all-caps names to Title Case.
- **Fixing the Substring Keyword Collision Bug**: An early challenge was keyword matching false positives. A simple substring search for `"rag"` was matching inside `"Kharagpur"` (a university name), and `"gemini"` was matching inside `"Capgemini"`. I fixed this across the entire parser by compiling regex patterns with strict word boundaries: `re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE)`.
- **Section Parsing**: Extracted project and experience sections separately from skills lists so downstream scoring modules could distinguish between hands-on projects and simple bullet lists.

### Step 4: Solving the Core Challenge — Section-Aware Eligibility (`src/eligibility.py`)
The most critical requirement was ensuring candidates are not marked eligible simply because they listed `PyTorch`, `TensorFlow`, `Keras`, `RAG`, or `AI-powered` in a bulleted skills section.
- **Section Partitioning**: Built `partition_resume_sections()` to slice raw resumes into distinct section blocks (`skills_lines` vs. `non_skills_lines`).
- **Implementation Evidence Detection**: Inspected project and experience lines for real implementation markers:
  - Action verbs: `built`, `developed`, `trained`, `implemented`, `designed`, `created`, `fine-tuned`, `deployed`, `engineered`.
  - Artifacts & Metrics: `model`, `pipeline`, `workflow`, `system`, `dataset`, `accuracy`, `latency`, `inference`, `embeddings`.
- **False Positive Elimination**: If a candidate only has AI keywords in their skills list with no backing project or work experience, they are disqualified with an explicit reason:
  `"No meaningful AI/LLM/RAG/agentic project or work experience found. AI frameworks/keywords were only listed in skills, with no implementation evidence in projects or experience."`
- **Allowing Custom AI**: Ensured custom deep learning and machine learning projects (e.g. CNNs, PyTorch classifiers, computer vision pipelines) pass eligibility even if the candidate did not use newer wrapper frameworks like LangChain or LlamaIndex.

### Step 5: Implementing Rate-Limited GitHub Enrichment (`src/github_enrichment.py`)
- Extracted GitHub usernames from profile URLs or handle mentions in resumes.
- Queried GitHub API endpoints (`/users/{username}`, `/events/public`, `/repos`) to count public repos, recent pushes in the past 90 days, and repositories matching Python or AI/ML topics.
- **Rate Limit Protection**: GitHub limits unauthenticated requests to 60 per hour. I implemented rate-limit header tracking (`x-ratelimit-remaining`, `x-ratelimit-reset`). When limits are hit, the module stops firing network requests and marks subsequent candidates with `rate_limited` status.
- **Status Classification**: Cleanly differentiated statuses: `success`, `rate_limited`, `not_found`, `error`, and `no_username`. A missing GitHub profile is never used to disqualify a candidate.

### Step 6: Building the 100-Point Scoring Engine (`src/scorer.py`)
- Implemented category scoring matching the assignment rubric (AI depth 40, Python 30, Cloud 15, GitHub 10, Engineering 5).
- Weighted project descriptions higher (1.5×) than skills list mentions for Python and backend capabilities.
- Applied penalties (-5 to -12 points) for shallow projects (e.g. basic tutorial clones or simple wrapper scripts).
- Generated qualitative explanations:
  - Highlighted candidate strengths when category scores crossed positive thresholds.
  - Flagged constructive observations when candidates lacked production-ready patterns.
  - Ensured missing GitHub data is never flagged as an engineering deficiency.

### Step 7: Adding the Optional LLM Semantic Review (`src/llm_adapter.py`)
- Created an adapter supporting both OpenAI (`gpt-4o-mini`) and Google Gemini (`gemini-1.5-flash`).
- Validated LLM output strictly: requires valid JSON with a project summary and a score adjustment clamped strictly between `-5` and `+5`.
- Implemented an offline deterministic fallback function that extracts readable summaries from project text when LLMs are disabled (`--no-llm`) or when API keys are not provided.

### Step 8: Orchestrating the Pipeline & Syncing Data (`src/pipeline.py` & `main.py`)
- Built the batch processing loop in `src/pipeline.py`.
- Tracked batch statistics: total discovered, successfully parsed, eligible count, rejected count, duplicate count, and errors.
- Ranked eligible candidates strictly by total score descending, using file name ascending as a deterministic tie-breaker. Kept ineligible candidates in a separate unranked section.
- Added automatic synchronization: running `main.py` writes to `output/results.json` and automatically mirrors the file to `frontend/public/results.json`, ensuring the UI is always up to date.

### Step 9: Creating the React Dashboard (`frontend/src/App.jsx`)
- Initialized a React 19 app with Vite.
- Designed a clean, accessible layout using Vanilla CSS without heavy utility libraries.
- Dynamically rendered batch statistics directly from `results.json` without hardcoding any values.
- Built interactive controls:
  - Tab navigation: `Eligible`, `Rejected`, and `All Candidates`.
  - Live search across candidate names, emails, files, and matched skills.
  - Dropdown filters for skills and minimum total score.
  - Multi-column sorting (by Rank, Total Score, AI Depth, Python Score, Cloud Score, or Name).
  - Detailed modal view displaying category score bars, extracted Python & AI evidence snippets, GitHub activity status, strengths, and concerns.

### Step 10: Writing Comprehensive Tests (`tests/`)
- Created 116 tests across 5 test files:
  - `test_eligibility.py` (33 tests): Skills-only false positive rejection, multi-line skills parsing, custom AI support, regression tests.
  - `test_parser.py` (33 tests): Name extraction heuristics, regex word boundaries, format handling, legacy `.doc` error messages, hashing.
  - `test_scoring.py` (30 tests): Category caps, tie breaking, wrapper penalties, qualitative note generation.
  - `test_github.py` (11 tests): Mocked GitHub API responses (success, 404, 403, 429, timeouts, caching).
  - `test_llm.py` (9 tests): CLI flags, offline fallback, adjustment bounds validation, malformed response handling.

---

## Project Structure

```
AI_Resume_Screening_Ranking_System/
├── main.py                     # CLI entry point
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
├── .env.example                # Template for optional API keys
├── .gitignore                  # Ignores caches, node_modules, build dirs, and secrets
├── src/
│   ├── __init__.py
│   ├── models.py               # Dataclasses (ParsedResume, ScoreBreakdown, CandidateResult)
│   ├── parser.py               # Text extraction (PDF, DOCX, TXT), name & signal extraction
│   ├── eligibility.py          # Section-aware Python & AI eligibility filters
│   ├── scorer.py               # 100-point rubric, wrapper penalties & qualitative notes
│   ├── github_enrichment.py    # GitHub REST client, rate-limit cooldown & profile scoring
│   ├── llm_adapter.py          # OpenAI / Gemini adapter & deterministic summary fallback
│   └── pipeline.py             # Batch pipeline runner, ranking & automatic frontend sync
├── tests/
│   ├── __init__.py
│   ├── test_eligibility.py     # 33 tests: eligibility, skills-only false positives
│   ├── test_parser.py          # 33 tests: name extraction, word boundaries, file formats
│   ├── test_scoring.py         # 30 tests: category caps, ranking stability, penalties
│   ├── test_github.py          # 11 tests: mocked GitHub API (404, 403, 429, timeouts)
│   └── test_llm.py             # 9 tests: LLM bounds, offline fallback, error handling
├── resumes/                    # 50 sample candidate PDF resumes
├── output/
│   └── results.json            # Generated screening results
└── frontend/                   # React web application
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── public/
    │   └── results.json        # Synchronized results file loaded by the dashboard
    └── src/
        ├── App.jsx             # Main interactive dashboard component
        ├── main.jsx            # React root mount
        └── index.css           # Vanilla CSS design system
```

---

## Installation & Setup

### Prerequisites
- **Python**: 3.10 or higher (tested on Python 3.13)
- **Node.js**: v18 or higher (tested on Node v24)
- **Git**

### 1. Set Up the Backend

```bash
# Clone the repository
git clone https://github.com/your-username/AI_Resume_Screening_Ranking_System.git
cd AI_Resume_Screening_Ranking_System

# Create and activate a Python virtual environment
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

### 2. Set Up the Frontend

```bash
cd frontend
npm install
cd ..
```

---

## Environment Configuration (Optional)

The system works 100% offline out of the box without requiring any API keys. If you want to enable higher GitHub rate limits or LLM-based summaries, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Available environment variables:
- `GITHUB_TOKEN`: *(Optional)* GitHub personal access token (raises API limit from 60 to 5,000 req/hr).
- `OPENAI_API_KEY`: *(Optional)* Enables OpenAI evaluation (`gpt-4o-mini`).
- `GEMINI_API_KEY`: *(Optional)* Enables Google Gemini evaluation (`gemini-1.5-flash`).

---

## How to Run

### 1. Run the Screening Pipeline (CLI)

Run the screening pipeline over the resume folder using deterministic evaluation (recommended):

```bash
python main.py --input ./resumes --output ./output/results.json --no-llm
```

CLI Options:
- `--input <dir>`: Directory containing resumes (default: `./resumes`).
- `--output <file>`: Output path for the JSON results (default: `./output/results.json`).
- `--no-llm`: Bypasses external LLM API calls and uses deterministic summaries.
- `--verbose`: Enables detailed DEBUG logs.

*Note: Running `main.py` automatically updates both `output/results.json` and `frontend/public/results.json`.*

### 2. Run the Test Suite

Run the full pytest suite (all 116 tests run completely offline and use mocked network calls):

```bash
python -m pytest -v
```

### 3. Launch the React Web Dashboard

Start the frontend development server:

```bash
cd frontend
npm run dev
```

Open your browser at **[http://localhost:5173](http://localhost:5173)** to explore the screening results.

To create an optimized production build:

```bash
cd frontend
npm run build
```

---

## Scoring Rubric Breakdown

Candidates are evaluated across five distinct categories up to a maximum of **100 points**:

| Category | Max Score | What is Evaluated |
|---|:---:|---|
| **AI / Agentic / RAG Project Depth** | **40 pts** | Multi-agent orchestration, LangGraph, vector search, RAG pipelines, fine-tuning, embeddings, custom ML models. Real project experience receives full credit; skills-only mentions receive discounted credit. Wrapper penalties (-5 to -12 pts) apply to shallow tutorial clones. |
| **Python & Backend Engineering** | **30 pts** | FastAPI, Flask, Django, AsyncIO, databases (PostgreSQL, SQLite), Redis caching, ORMs, and practical backend work (1.5× weight for project evidence). |
| **Cloud & Deployment** | **15 pts** | Docker containerization, Kubernetes, CI/CD pipelines, AWS/GCP, full-stack tools (React, Next.js, TypeScript). |
| **GitHub Activity** | **10 pts** | Public repository quality, recent pushes in the last 90 days, and maintained Python/AI repositories. |
| **Engineering Depth** | **5 pts** | Automated testing (pytest), concurrency, error handling, rate limiting, logging, and code structure. |

---

## Practical Notes & Engineering Considerations

1. **Handling Non-Standard PDF Layouts**: `pdfplumber` does an excellent job with standard resume columns, but resumes with complex graphic design elements or irregular text boxes can occasionally cause words to be grouped out of standard order. The fallback to `pypdf` provides resilience against corrupt streams.
2. **GitHub API Unauthenticated Quotas**: GitHub enforces a limit of 60 unauthenticated requests per hour per IP. For larger resume batches, providing a free `GITHUB_TOKEN` in `.env` increases this limit to 5,000 requests per hour. The built-in cooldown prevents wasted network requests once the limit is reached.
3. **Deterministic vs. LLM Trade-Off**: While LLMs can provide natural language summaries, deterministic scoring ensures complete reproducibility and instant execution with zero external API dependencies or costs. Both modes are fully supported.
