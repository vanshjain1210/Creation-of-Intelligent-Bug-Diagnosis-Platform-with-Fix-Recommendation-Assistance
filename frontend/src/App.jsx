import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import UploadCard from './components/UploadCard';
import ResultsPanel from './components/ResultsPanel';
import HistoryPanel from './components/HistoryPanel';
import SettingsPanel from './components/SettingsPanel';
import AnalyticsPanel from './components/AnalyticsPanel';
import HealthPanel from './components/HealthPanel';
import RecommendationPanel from './components/RecommendationPanel';
import ActivityPanel from './components/ActivityPanel';

import { useSystemStatus } from './hooks/useSystemStatus';
import { submitBug, analyzeBug, getAnalysis } from './services/api';
import AnalyzeBugPage from './pages/AnalyzeBugPage';
import HistoryPage from './pages/HistoryPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import DashboardPage from './pages/DashboardPage';
import './App.css';

export default function App() {
  const [activeView, setActiveView] = useState('dashboard');
  const [uiState, setUiState] = useState('idle');
  const [analysis, setAnalysis] = useState(null);
  const [submittedBug, setSubmittedBug] = useState(null);
  const [notification, setNotification] = useState(null);
  const [theme, setTheme] = useState('dark');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Custom states for timeline simulation during execution
  const [timelineIndex, setTimelineIndex] = useState(-1);
  const [activeAgent, setActiveAgent] = useState('');

  const { status, loading, error: statusError } = useSystemStatus();

  const systemStatus = statusError
    ? 'unavailable'
    : loading
    ? 'checking'
    : status.overall || 'checking';

  // Toggle Dark/Light Mode
  useEffect(() => {
    document.body.className = theme === 'dark' ? 'dark-theme' : 'light-theme';
  }, [theme]);

  // File Upload Preview complete
  const handleUploadComplete = async ({ content, file }) => {
    setUiState('uploading');
    try {
      const result = await submitBug({ content, file });
      setSubmittedBug(result.bug);
      setUiState('preview_ready');
      setActiveView('analyze'); // Stay on upload screen to show preview
      setNotification('Bug report parsed successfully. Ready for AI Analysis.');
    } catch (err) {
      setUiState('error');
      setNotification(err.message || 'Parsing failed.');
    }
  };

  // Run the multi-agent analysis timeline
  const handleInitiateAnalysis = async () => {
    if (!submittedBug) return;
    setUiState('processing');
    setActiveView('analysis');
    setTimelineIndex(0);

    const stages = [
      'Extracting files...', 'Data cleaning...', 'Generating embeddings...',
      'Retrieving historical context...', 'Triage Agent processing...',
      'Log Parser Agent scanning...', 'Duplicate Detection matching...',
      'Root Cause Agent calculating...', 'Remediation Agent advising...',
      'Risk Assessment Agent grading...', 'Confidence Agent scoring...',
      'Executive Summary compiling...', 'Finalizing report...'
    ];

    // Simulate thinking steps
    let currentIdx = 0;
    const interval = setInterval(() => {
      if (currentIdx < stages.length - 1) {
        currentIdx++;
        setTimelineIndex(currentIdx);
        setActiveAgent(stages[currentIdx]);
      } else {
        clearInterval(interval);
      }
    }, 120);

    try {
      const analyzeResult = await analyzeBug(submittedBug.id);
      clearInterval(interval);
      // Enrich analysis with bug file metadata for UI display
      const enrichedAnalysis = {
        ...analyzeResult.analysis,
        file_name: submittedBug.file_name || analyzeResult.analysis?.file_name,
        source_file: submittedBug.file_name || 'pasted_text',
        title: submittedBug.title || analyzeResult.analysis?.title,
      };
      setAnalysis(enrichedAnalysis);
      setUiState('completed');
      setTimelineIndex(stages.length);
      
      // Auto redirect to results immediately
      setActiveView('results');
      setNotification('Enterprise multi-agent analysis finished successfully.');
    } catch (err) {
      clearInterval(interval);
      setUiState('error');
      setNotification(err.message || 'Analysis pipeline failed.');
    }
  };

  // Click row from history to view results
  const handleSelectHistory = async (analysisId) => {
    setUiState('loading_history');
    try {
      const result = await getAnalysis(analysisId);
      // API returns the object directly for GET /analysis/:id
      const analysisData = result?.analysis || result;
      setAnalysis(analysisData);
      setUiState('completed');
      setActiveView('results');
      setNotification('Historical analysis record loaded.');
    } catch (err) {
      setUiState('error');
      setNotification('Failed to retrieve historical record: ' + err.message);
    }
  };

  const renderContent = () => {
    switch (activeView) {
      case 'dashboard':
        return (
          <div className="dashboard-grid">
            <div className="dashboard-main-col">
              {/* Statistic Summary Cards */}
              <div className="stats-cards-grid">
                <div className="stat-card">
                  <h4>Total Bugs Analyzed</h4>
                  <p className="stat-number">{status?.total_bugs ?? 6}</p>
                </div>
                <div className="stat-card">
                  <h4>Critical Priority</h4>
                  <p className="stat-number color-critical">2</p>
                </div>
                <div className="stat-card">
                  <h4>Duplicate Matching Rate</h4>
                  <p className="stat-number color-dup">33.3%</p>
                </div>
                <div className="stat-card">
                  <h4>Embedding KB Size</h4>
                  <p className="stat-number">{status?.chroma_documents ?? 6} vectors</p>
                </div>
              </div>

              {/* Status and Action panels */}
              <div className="quick-access-section">
                <div className="card start-analysis-cta">
                  <h3>AI Smart Bug Analyzer</h3>
                  <p>Upload files or logs to scan for errors, verify duplicate matches, and recommend remediations.</p>
                  <button className="btn btn-primary" onClick={() => setActiveView('analyze')}>
                    Open Bug Upload Center
                  </button>
                </div>
              </div>

              <RecommendationPanel />
            </div>

            <div className="dashboard-side-col">
              <HealthPanel status={status} />
              <ActivityPanel />
            </div>
          </div>
        );

      case 'analyze':
        return <AnalyzeBugPage />;

      case 'knowledge':
        return <KnowledgeBasePage />;

      case 'upload':
        return (
          <div className="upload-view-layout">
            <UploadCard onUploadComplete={handleUploadComplete} disabled={uiState === 'uploading'} uiState={uiState} />
            
            {/* Extracted Bug Preview (Pre-analysis verification) */}
            {uiState === 'preview_ready' && submittedBug && (
              <div className="card preview-card-container">
                <div className="preview-header">
                  <h3>Extracted Bug Report Preview</h3>
                  <button className="btn btn-primary" onClick={handleInitiateAnalysis}>
                    Initiate Enterprise AI Analysis
                  </button>
                </div>
                
                <table className="preview-meta-table">
                  <tbody>
                    <tr>
                      <td><strong>Suggested Title</strong></td>
                      <td>{submittedBug.title}</td>
                    </tr>
                    <tr>
                      <td><strong>Source File Name</strong></td>
                      <td><code>{submittedBug.file_name || "Text pasted"}</code></td>
                    </tr>
                  </tbody>
                </table>

                <div className="preview-text-block">
                  <h4>Extracted Text Content</h4>
                  <pre>{submittedBug.raw_content}</pre>
                </div>
              </div>
            )}
          </div>
        );

      case 'analysis':
        return (
          <div className="card analysis-timeline-card">
            <h3>Enterprise Multi-Agent Pipeline Execution</h3>
            <p className="section-subtitle">Real-time trace of agent validation, search, and diagnostics</p>
            
            {/* Progress bar */}
            <div className="timeline-progress-bar-bg">
              <div
                className="timeline-progress-bar-fill"
                style={{ width: `${Math.min(100, Math.max(0, (timelineIndex + 1) * 7.7))}%` }}
              />
            </div>
            <p className="timeline-active-agent">Current Step: <strong>{activeAgent || "Initializing components..."}</strong></p>

            <div className="timeline-stages-vertical">
              {[
                { name: 'File Upload Validation', match: 0 },
                { name: 'Data Normalization', match: 1 },
                { name: 'Vector Index Lookup', match: 3 },
                { name: 'Triage Agent Classification', match: 4 },
                { name: 'Log Parser Scanning', match: 5 },
                { name: 'Duplicate Detection Query', match: 6 },
                { name: 'Root Cause Diagnostics', match: 7 },
                { name: 'Remediation Advisory', match: 8 },
                { name: 'Risk Assessment Profiling', match: 9 },
                { name: 'Confidence scoring & compilations', match: 10 },
                { name: 'Executive Summary build', match: 11 }
              ].map((stage, idx) => {
                let statusClass = 'pending';
                if (timelineIndex > stage.match) statusClass = 'success';
                else if (timelineIndex === stage.match) statusClass = 'running';

                return (
                  <div key={idx} className={`timeline-stage-row ${statusClass}`}>
                    <span className="stage-marker">✓</span>
                    <span className="stage-name">{stage.name}</span>
                    <span className="stage-status-text">{statusClass.toUpperCase()}</span>
                  </div>
                );
              })}
            </div>
          </div>
        );

      case 'results':
        return (
          <ResultsPanel
            analysis={analysis}
            onCopy={() => setNotification('Findings copied to clipboard.')}
            onDownload={() => setNotification('Report download requested.')}
          />
        );

      case 'history':
        return <HistoryPage onSelectAnalysis={handleSelectHistory} />;

      case 'settings':
        return <SettingsPanel />;

      case 'analytics':
        return <AnalyticsPanel />;

      case 'health':
        return <HealthPanel status={status} />;

      default:
        return <div>View not found.</div>;
    }
  };

  return (
    <div className={`app-layout ${theme === 'dark' ? 'dark-theme' : 'light-theme'}`}>
      <Sidebar activeView={activeView} onNavigate={setActiveView} systemStatus={systemStatus} />
      
      <main className="main-content">
        {/* Top Navbar */}
        <header className="top-bar">
          <div className="brand-title">
            <h2>{activeView.toUpperCase()}</h2>
            <span className="sub-title-text">AI-Smart-Bug-Analyzer-And-Fix-Advisor Enterprise Dashboard</span>
          </div>

          <div className="top-actions">
            {/* Search Bar */}
            <input
              type="text"
              placeholder="Search reports globally..."
              className="global-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />

            {/* Dark/Light mode toggle */}
            <button className="theme-toggle-btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
              {theme === 'dark' ? '☀ Light Mode' : '🌙 Dark Mode'}
            </button>

            {/* Profile menu mock */}
            <div className="profile-badge">
              <span>Admin Profile</span>
            </div>
          </div>

          {notification && (
            <div className={`toast ${uiState === 'error' ? 'error' : 'success'}`}>
              <span className="toast-msg-text">{notification}</span>
              <button className="toast-close-btn" onClick={() => setNotification(null)}>×</button>
            </div>
          )}
        </header>

        <div className="content-container">
          {renderContent()}
        </div>
      </main>
    </div>
  );
}
