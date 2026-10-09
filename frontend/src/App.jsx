import React, { useState, useEffect, useMemo } from 'react';
import { 
  Users, 
  CheckCircle2, 
  XCircle, 
  Trophy, 
  Search, 
  ExternalLink, 
  X, 
  AlertTriangle
} from 'lucide-react';

// Crisp, standalone GitHub SVG icon
const GithubIcon = ({ size = 16, className = '' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    style={{ display: 'inline-block', verticalAlign: 'middle' }}
  >
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
    <path d="M9 18c-4.51 2-5-2-7-2" />
  </svg>
);

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filters & State
  const [activeTab, setActiveTab] = useState('eligible'); // 'eligible' | 'rejected' | 'all'
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSkill, setSelectedSkill] = useState('all');
  const [minScore, setMinScore] = useState(0);
  const [sortBy, setSortBy] = useState('rank');
  const [selectedCandidate, setSelectedCandidate] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch('/results.json')
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Failed to load results.json (${res.status} ${res.statusText})`);
        }
        return res.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Fetch error:', err);
        setError('Could not load screening results from /results.json.');
        setLoading(false);
      });
  }, []);

  // Combine candidates list
  const allCandidates = useMemo(() => {
    if (!data) return [];
    const eligible = (data.eligible_candidates || []).map((c) => ({
      ...c,
      isEligibleCandidate: true,
    }));
    const rejected = (data.rejected_candidates || []).map((c) => ({
      ...c,
      isEligibleCandidate: false,
    }));
    return [...eligible, ...rejected];
  }, [data]);

  // Extract unique skills list
  const uniqueSkills = useMemo(() => {
    const skillsSet = new Set();
    allCandidates.forEach((c) => {
      (c.matched_skills || []).forEach((s) => skillsSet.add(s.toLowerCase()));
    });
    return Array.from(skillsSet).sort();
  }, [allCandidates]);

  // Filter & Sort Candidates
  const filteredCandidates = useMemo(() => {
    return allCandidates
      .filter((c) => {
        // Tab filter
        if (activeTab === 'eligible' && !c.isEligibleCandidate) return false;
        if (activeTab === 'rejected' && c.isEligibleCandidate) return false;

        // Min score filter (only for eligible)
        if (c.isEligibleCandidate && (c.scores?.total || 0) < minScore) {
          return false;
        }

        // Skill filter
        if (selectedSkill !== 'all') {
          const hasSkill = (c.matched_skills || []).some(
            (s) => s.toLowerCase() === selectedSkill.toLowerCase()
          );
          if (!hasSkill) return false;
        }

        // Search query
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const name = (c.name || '').toLowerCase();
          const email = (c.email || '').toLowerCase();
          const file = (c.file_name || '').toLowerCase();
          const skills = (c.matched_skills || []).map((s) => s.toLowerCase()).join(' ');
          const summary = (c.project_summary || '').toLowerCase();
          return (
            name.includes(q) ||
            email.includes(q) ||
            file.includes(q) ||
            skills.includes(q) ||
            summary.includes(q)
          );
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'rank') {
          const rankA = a.rank || 999999;
          const rankB = b.rank || 999999;
          if (rankA !== rankB) return rankA - rankB;
          return (b.scores?.total || 0) - (a.scores?.total || 0);
        }
        if (sortBy === 'score_desc') {
          return (b.scores?.total || 0) - (a.scores?.total || 0);
        }
        if (sortBy === 'ai_depth') {
          return (b.scores?.ai_rag_depth || 0) - (a.scores?.ai_rag_depth || 0);
        }
        if (sortBy === 'python_score') {
          return (b.scores?.python_backend || 0) - (a.scores?.python_backend || 0);
        }
        if (sortBy === 'cloud_score') {
          return (b.scores?.cloud_deployment || 0) - (a.scores?.cloud_deployment || 0);
        }
        if (sortBy === 'name') {
          const nameA = a.name || a.file_name || '';
          const nameB = b.name || b.file_name || '';
          return nameA.localeCompare(nameB);
        }
        return 0;
      });
  }, [allCandidates, activeTab, minScore, selectedSkill, searchQuery, sortBy]);

  // Handle modal close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setSelectedCandidate(null);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const stats = data?.stats || {
    total_discovered: allCandidates.length,
    successfully_parsed: allCandidates.length,
    eligible_count: (data?.eligible_candidates || []).length,
    rejected_count: (data?.rejected_candidates || []).length,
    failed_count: 0,
    duplicate_count: 0,
  };

  const topCandidate = (data?.eligible_candidates || [])[0];

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo-badge">AI</div>
          <div className="header-title-wrap">
            <h1>Resume Screening & Ranking</h1>
            <p>
              <span>Batch Evaluation</span>
              <span>•</span>
              <span>{stats.total_discovered} resumes discovered</span>
              <span>•</span>
              <span>{stats.successfully_parsed ?? allCandidates.length} parsed</span>
              {data?.generated_at && (
                <>
                  <span>•</span>
                  <span>{new Date(data.generated_at).toLocaleDateString()}</span>
                </>
              )}
            </p>
          </div>
        </div>
      </header>

      {/* Parsing Alert Banner if failures occurred */}
      {stats.failed_count > 0 && (
        <div style={{
          background: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: 'var(--radius-md)',
          padding: '12px 16px',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          color: '#991b1b',
          fontSize: '13px'
        }}>
          <AlertTriangle size={18} color="#ef4444" style={{ flexShrink: 0 }} />
          <span>
            <strong>Extraction Notice:</strong> {stats.failed_count} out of {stats.total_discovered} file{stats.failed_count > 1 ? 's' : ''} failed extraction or contained unreadable formats. Successfully parsed: {stats.successfully_parsed}.
          </span>
        </div>
      )}

      {/* Overview Stat Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-title">Total Screened</span>
            <Users size={16} className="stat-icon" />
          </div>
          <div className="stat-value">{stats.total_discovered}</div>
          <div className="stat-sub">
            {stats.failed_count > 0 ? (
              <span style={{ color: '#ef4444', fontWeight: 600 }}>
                {stats.failed_count} unreadable / failed file{stats.failed_count > 1 ? 's' : ''}
              </span>
            ) : stats.total_discovered > 0 ? (
              <span>All {stats.successfully_parsed || stats.total_discovered} resumes parsed successfully</span>
            ) : (
              <span>No resumes discovered</span>
            )}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-title">Eligible Candidates</span>
            <CheckCircle2 size={16} color="#10b981" />
          </div>
          <div className="stat-value">{stats.eligible_count}</div>
          <div className="stat-sub">
            {stats.total_discovered > 0
              ? `${Math.round((stats.eligible_count / stats.total_discovered) * 100)}% pass rate`
              : '0%'}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-title">Disqualified</span>
            <XCircle size={16} color="#ef4444" />
          </div>
          <div className="stat-value">{stats.rejected_count}</div>
          <div className="stat-sub">Missing required Python / AI evidence</div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-title">Top Candidate</span>
            <Trophy size={16} color="#f59e0b" />
          </div>
          <div className="stat-value" style={{ fontSize: '20px' }}>
            {topCandidate?.name || topCandidate?.file_name || 'N/A'}
          </div>
          <div className="stat-sub">
            Highest Score: {topCandidate?.scores?.total?.toFixed(1) ?? '—'} / 100
          </div>
        </div>
      </div>

      {/* Toolbar & Filters */}
      <div className="toolbar">
        <div className="toolbar-top">
          {/* Tabs */}
          <div className="tabs-group">
            <button
              className={`tab-btn ${activeTab === 'eligible' ? 'active' : ''}`}
              onClick={() => setActiveTab('eligible')}
            >
              Eligible
              <span className="tab-count">{stats.eligible_count}</span>
            </button>
            <button
              className={`tab-btn ${activeTab === 'rejected' ? 'active' : ''}`}
              onClick={() => setActiveTab('rejected')}
            >
              Rejected
              <span className="tab-count">{stats.rejected_count}</span>
            </button>
            <button
              className={`tab-btn ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              All
              <span className="tab-count">{allCandidates.length}</span>
            </button>
          </div>

          {/* Quick info */}
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Showing <strong>{filteredCandidates.length}</strong> of {allCandidates.length} candidates
          </div>
        </div>

        <div className="toolbar-filters">
          {/* Search */}
          <div className="search-input-wrap">
            <Search size={15} className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="Search by name, email, filename, skill..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Skill Filter */}
          <select
            className="filter-select"
            value={selectedSkill}
            onChange={(e) => setSelectedSkill(e.target.value)}
          >
            <option value="all">All Skills ({uniqueSkills.length})</option>
            {uniqueSkills.map((skill) => (
              <option key={skill} value={skill}>
                {skill.toUpperCase()}
              </option>
            ))}
          </select>

          {/* Min Score Filter (Only applies to eligible) */}
          {activeTab !== 'rejected' && (
            <select
              className="filter-select"
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
            >
              <option value={0}>Min Score: Any</option>
              <option value={50}>Min Score: 50+</option>
              <option value={70}>Min Score: 70+</option>
              <option value={80}>Min Score: 80+</option>
              <option value={85}>Min Score: 85+</option>
              <option value={90}>Min Score: 90+</option>
            </select>
          )}

          {/* Sort By */}
          <select
            className="filter-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="rank">Sort by: Rank</option>
            <option value="score_desc">Sort by: Total Score</option>
            <option value="ai_depth">Sort by: AI & RAG Depth</option>
            <option value="python_score">Sort by: Python Backend</option>
            <option value="cloud_score">Sort by: Cloud Deployment</option>
            <option value="name">Sort by: Name (A-Z)</option>
          </select>

          {(searchQuery || selectedSkill !== 'all' || minScore > 0) && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setSearchQuery('');
                setSelectedSkill('all');
                setMinScore(0);
              }}
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Main Table View */}
      {loading ? (
        <div className="table-container empty-state">
          <h3>Loading candidate results...</h3>
        </div>
      ) : error ? (
        <div className="table-container empty-state">
          <AlertTriangle size={32} color="#f59e0b" style={{ margin: '0 auto 12px' }} />
          <h3>No Results Loaded</h3>
          <p>{error}</p>
        </div>
      ) : filteredCandidates.length === 0 ? (
        <div className="table-container empty-state">
          <h3>No candidates match your criteria</h3>
          <p>Try clearing your search query or loosening score filters.</p>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setSearchQuery('');
              setSelectedSkill('all');
              setMinScore(0);
            }}
          >
            Clear Filters
          </button>
        </div>
      ) : (
        <div className="table-container">
          <table className="candidate-table">
            <thead>
              <tr>
                <th style={{ width: '60px' }}>Rank</th>
                <th>Candidate</th>
                <th style={{ width: '130px' }}>Status</th>
                <th style={{ width: '150px' }}>Total Score</th>
                <th>Category Scores</th>
                <th>Top Matched Skills</th>
                <th style={{ textAlign: 'right', width: '90px' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredCandidates.map((candidate, idx) => {
                const isTop1 = candidate.rank === 1;
                const isTop2 = candidate.rank === 2;
                const isTop3 = candidate.rank === 3;
                const totalScore = candidate.scores?.total || 0;
                const scoreFillClass =
                  totalScore >= 80 ? 'high' : totalScore >= 50 ? 'med' : 'low';

                return (
                  <tr
                    key={candidate.file_name || idx}
                    className="candidate-row"
                    onClick={() => setSelectedCandidate(candidate)}
                  >
                    <td>
                      {candidate.isEligibleCandidate && candidate.rank ? (
                        <span
                          className={`rank-badge ${
                            isTop1
                              ? 'rank-top1'
                              : isTop2
                              ? 'rank-top2'
                              : isTop3
                              ? 'rank-top3'
                              : ''
                          }`}
                        >
                          {candidate.rank}
                        </span>
                      ) : (
                        <span className="rank-badge rank-rejected">—</span>
                      )}
                    </td>

                    <td>
                      <div className="candidate-name-col">
                        <span className="candidate-name">
                          {candidate.name || 'Name unavailable'}
                        </span>
                        <span className="candidate-file">{candidate.file_name}</span>
                        {candidate.email && (
                          <span className="candidate-email">{candidate.email}</span>
                        )}
                      </div>
                    </td>

                    <td>
                      {candidate.isEligibleCandidate ? (
                        <span className="status-pill eligible">
                          <span className="status-dot"></span>
                          Eligible
                        </span>
                      ) : (
                        <span className="status-pill rejected" title={candidate.eligibility?.rejection_reasons?.join('\n')}>
                          <span className="status-dot"></span>
                          Disqualified
                        </span>
                      )}
                    </td>

                    <td>
                      <div className="score-cell">
                        <div className="score-num-wrap">
                          <span className="score-num">{totalScore.toFixed(1)}</span>
                          <span className="score-max">/ 100</span>
                        </div>
                        <div className="score-progress">
                          <div
                            className={`score-fill ${scoreFillClass}`}
                            style={{ width: `${Math.min(totalScore, 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    <td>
                      <div className="score-breakdown-tags">
                        <span className="mini-score" title="AI & RAG Depth (max 40)">
                          AI: {candidate.scores?.ai_rag_depth?.toFixed(0) || 0}
                        </span>
                        <span className="mini-score" title="Python & Backend (max 30)">
                          Py: {candidate.scores?.python_backend?.toFixed(0) || 0}
                        </span>
                        <span className="mini-score" title="Cloud & Deployment (max 15)">
                          Cloud: {candidate.scores?.cloud_deployment?.toFixed(0) || 0}
                        </span>
                        <span className="mini-score" title="GitHub Activity (max 10)">
                          GH: {candidate.scores?.github_activity?.toFixed(0) || 0}
                        </span>
                      </div>
                    </td>

                    <td>
                      <div className="skills-tags">
                        {(candidate.matched_skills || []).slice(0, 4).map((s) => (
                          <span key={s} className="skill-tag">
                            {s}
                          </span>
                        ))}
                        {(candidate.matched_skills || []).length > 4 && (
                          <span className="skill-tag-more">
                            +{(candidate.matched_skills || []).length - 4}
                          </span>
                        )}
                        {(!candidate.matched_skills || candidate.matched_skills.length === 0) && (
                          <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                            None matched
                          </span>
                        )}
                      </div>
                    </td>

                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedCandidate(candidate);
                        }}
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Candidate Details Modal */}
      {selectedCandidate && (
        <div className="modal-overlay" onClick={() => setSelectedCandidate(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-header-info">
                <h2>
                  {selectedCandidate.name || selectedCandidate.file_name}
                  {selectedCandidate.rank && (
                    <span className="rank-badge rank-top1" style={{ width: '26px', height: '26px', fontSize: '12px' }}>
                      #{selectedCandidate.rank}
                    </span>
                  )}
                </h2>
                <div className="modal-header-meta">
                  <span><strong>File:</strong> {selectedCandidate.file_name}</span>
                  {selectedCandidate.email && (
                    <span><strong>Email:</strong> {selectedCandidate.email}</span>
                  )}
                  {selectedCandidate.isEligibleCandidate ? (
                    <span className="status-pill eligible">
                      <span className="status-dot"></span> Eligible
                    </span>
                  ) : (
                    <span className="status-pill rejected">
                      <span className="status-dot"></span> Disqualified
                    </span>
                  )}
                </div>
              </div>

              <button
                className="modal-close-btn"
                onClick={() => setSelectedCandidate(null)}
                aria-label="Close"
              >
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              {/* Rejection Reasons if disqualified */}
              {!selectedCandidate.isEligibleCandidate && (
                <div className="detail-section">
                  <span className="detail-section-title">Disqualification Criteria</span>
                  <div className="callout-box callout-danger">
                    <strong>Candidate did not pass mandatory screening thresholds:</strong>
                    <ul>
                      {(selectedCandidate.eligibility?.rejection_reasons || []).map((reason, i) => (
                        <li key={i}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* Score Breakdown */}
              <div className="detail-section">
                <span className="detail-section-title">
                  Scoring Breakdown — Total: {selectedCandidate.scores?.total?.toFixed(1) || 0} / 100
                </span>
                <div className="scores-detail-grid">
                  <div className="score-detail-box">
                    <span className="score-box-label">AI & RAG Depth</span>
                    <span className="score-box-val">
                      {selectedCandidate.scores?.ai_rag_depth?.toFixed(1) || 0}
                      <span className="score-box-max"> / 40</span>
                    </span>
                  </div>
                  <div className="score-detail-box">
                    <span className="score-box-label">Python & Backend</span>
                    <span className="score-box-val">
                      {selectedCandidate.scores?.python_backend?.toFixed(1) || 0}
                      <span className="score-box-max"> / 30</span>
                    </span>
                  </div>
                  <div className="score-detail-box">
                    <span className="score-box-label">Cloud & Deployment</span>
                    <span className="score-box-val">
                      {selectedCandidate.scores?.cloud_deployment?.toFixed(1) || 0}
                      <span className="score-box-max"> / 15</span>
                    </span>
                  </div>
                  <div className="score-detail-box">
                    <span className="score-box-label">GitHub Activity</span>
                    <span className="score-box-val">
                      {selectedCandidate.scores?.github_activity?.toFixed(1) || 0}
                      <span className="score-box-max"> / 10</span>
                    </span>
                  </div>
                  <div className="score-detail-box">
                    <span className="score-box-label">Engineering Depth</span>
                    <span className="score-box-val">
                      {selectedCandidate.scores?.engineering_depth?.toFixed(1) || 0}
                      <span className="score-box-max"> / 5</span>
                    </span>
                  </div>
                </div>
              </div>

              {/* Extracted Evidence */}
              {(selectedCandidate.eligibility?.ai_evidence?.length > 0 ||
                selectedCandidate.eligibility?.python_evidence?.length > 0) && (
                <div className="detail-section">
                  <span className="detail-section-title">Verified Resume Evidence</span>

                  {selectedCandidate.eligibility?.ai_evidence?.length > 0 && (
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '5px' }}>
                        AI / RAG / Agentic Snippets:
                      </div>
                      <div className="evidence-list">
                        {selectedCandidate.eligibility.ai_evidence.map((snippet, i) => (
                          <div key={i} className="evidence-item">
                            "{snippet}"
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedCandidate.eligibility?.python_evidence?.length > 0 && (
                    <div style={{ marginTop: '10px' }}>
                      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '5px' }}>
                        Python & Backend Snippets:
                      </div>
                      <div className="evidence-list">
                        {selectedCandidate.eligibility.python_evidence.map((snippet, i) => (
                          <div key={i} className="evidence-item">
                            "{snippet}"
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* GitHub Profile */}
              {selectedCandidate.github && (
                <div className="detail-section">
                  <span className="detail-section-title">GitHub Enrichment</span>
                  <div className="github-detail-box">
                    <div className="github-header-row">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <GithubIcon size={16} />
                        {selectedCandidate.github.username ? (
                          <a
                            href={
                              selectedCandidate.github.profile_url ||
                              `https://github.com/${selectedCandidate.github.username}`
                            }
                            target="_blank"
                            rel="noreferrer"
                            className="github-user-link"
                          >
                            @{selectedCandidate.github.username}
                            <ExternalLink size={12} />
                          </a>
                        ) : (
                          <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                            No GitHub handle found in resume
                          </span>
                        )}
                      </div>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 500,
                          padding: '3px 8px',
                          borderRadius: '10px',
                          background:
                            selectedCandidate.github.enrichment_status === 'success'
                              ? '#ecfdf5'
                              : selectedCandidate.github.enrichment_status === 'rate_limited'
                              ? '#fffbeb'
                              : selectedCandidate.github.enrichment_status === 'not_found'
                              ? '#fef2f2'
                              : 'var(--bg-card)',
                          color:
                            selectedCandidate.github.enrichment_status === 'success'
                              ? '#065f46'
                              : selectedCandidate.github.enrichment_status === 'rate_limited'
                              ? '#92400e'
                              : selectedCandidate.github.enrichment_status === 'not_found'
                              ? '#991b1b'
                              : 'var(--text-muted)',
                          border: '1px solid currentColor',
                        }}
                      >
                        {selectedCandidate.github.enrichment_status === 'success'
                          ? 'Verified Profile'
                          : selectedCandidate.github.enrichment_status === 'rate_limited'
                          ? 'Rate Limited'
                          : selectedCandidate.github.enrichment_status === 'not_found'
                          ? 'User Not Found (404)'
                          : selectedCandidate.github.enrichment_status === 'error' || selectedCandidate.github.enrichment_status === 'failed'
                          ? 'API Error'
                          : selectedCandidate.github.enrichment_status === 'no_username'
                          ? 'No Handle'
                          : selectedCandidate.github.enrichment_status || 'N/A'}
                      </span>
                    </div>

                    {selectedCandidate.github.enrichment_summary && (
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.4, margin: '2px 0 4px' }}>
                        {selectedCandidate.github.enrichment_summary}
                      </div>
                    )}

                    {selectedCandidate.github.username && (
                      <>
                        <div className="github-stats-row">
                          <span>
                            Public Repos: <strong>{selectedCandidate.github.public_repos || 0}</strong>
                          </span>
                          <span>
                            Recent Pushes (90d): <strong>{selectedCandidate.github.recent_push_count || 0}</strong>
                          </span>
                          <span>
                            Python Repos: <strong>{selectedCandidate.github.has_python_repos ? 'Yes' : 'No'}</strong>
                          </span>
                          <span>
                            AI Repos: <strong>{selectedCandidate.github.has_ai_repos ? 'Yes' : 'No'}</strong>
                          </span>
                        </div>

                        {selectedCandidate.github.recent_repo_names?.length > 0 && (
                          <div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                              Recent Repositories:
                            </div>
                            <div className="github-repos-list">
                              {selectedCandidate.github.recent_repo_names.map((repo) => (
                                <span key={repo} className="github-repo-pill">
                                  {repo}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* Matched Skills */}
              <div className="detail-section">
                <span className="detail-section-title">
                  Matched Skills ({selectedCandidate.matched_skills?.length || 0})
                </span>
                <div className="skills-tags" style={{ maxWidth: '100%' }}>
                  {(selectedCandidate.matched_skills || []).map((skill) => (
                    <span key={skill} className="skill-tag">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>

              {/* Project Summary */}
              {selectedCandidate.project_summary && (
                <div className="detail-section">
                  <span className="detail-section-title">Project Summary</span>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, background: 'var(--bg-subtle)', padding: '12px 14px', borderRadius: 'var(--radius-sm)' }}>
                    {selectedCandidate.project_summary}
                  </div>
                </div>
              )}

              {/* Strengths & Concerns */}
              {((selectedCandidate.strengths?.length || 0) > 0 ||
                (selectedCandidate.concerns?.length || 0) > 0) && (
                <div className="detail-section" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  {selectedCandidate.strengths?.length > 0 && (
                    <div>
                      <span className="detail-section-title" style={{ color: '#065f46' }}>Strengths</span>
                      <ul className="bullet-list" style={{ marginTop: '6px' }}>
                        {selectedCandidate.strengths.map((item, idx) => (
                          <li key={idx} className="bullet-item positive">
                            <span style={{ color: '#10b981' }}>✓</span> {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {selectedCandidate.concerns?.length > 0 && (
                    <div>
                      <span className="detail-section-title" style={{ color: '#92400e' }}>Observations</span>
                      <ul className="bullet-list" style={{ marginTop: '6px' }}>
                        {selectedCandidate.concerns.map((item, idx) => (
                          <li key={idx} className="bullet-item negative">
                            <span style={{ color: '#f59e0b' }}>•</span> {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setSelectedCandidate(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
