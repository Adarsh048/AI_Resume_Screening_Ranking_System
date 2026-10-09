# AI Resume Screening & Ranking — Web Dashboard

A clean, responsive, and minimalist React UI for exploring and analyzing resume screening and candidate ranking results.

## Features
- **Overview Stat Cards**: Total screened, eligible pass rate %, disqualified count, and top candidate highlights.
- **Status Tabs**: Fast switching between Eligible candidates (ranked #1..N), Disqualified candidates, and All.
- **Search & Filters**: Instant search by candidate name, filename, email, or detected skill keywords.
- **Score Breakdown**: Visual score bars and category breakdowns (AI & RAG Depth, Python & Backend, Cloud & Deployment, GitHub Activity).
- **Candidate Inspection Modal**: Inspect verified resume evidence snippets, GitHub public repository signals, strengths, concerns, and disqualification reasons.

## Getting Started

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Start Local Development Server
```bash
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser.

### 3. Production Build
```bash
npm run build
```
The optimized bundle will be created in `dist/`.
