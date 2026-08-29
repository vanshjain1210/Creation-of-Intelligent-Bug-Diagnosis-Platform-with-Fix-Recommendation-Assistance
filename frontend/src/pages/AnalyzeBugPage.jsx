import React, { useRef, useState } from 'react';
import { phase4Analyze, testConnection } from '../services/api';

const PIPELINE_STEPS = [
  'Ingest',
  'Log Analysis',
  'Triage',
  'Persist',
  'FAISS Retrieval',
  'Recurrence Check',
  'Root Cause',
  'Fix Ranking',
  'Risk Score',
];
const ALLOWED_EXT = ['.txt', '.log', '.json'];

/**
 * Phase 3 Analyze Bug page.
 * Adds FAISS similar-bug retrieval and recurrence analysis on top of Phase 2.
 */
export default function AnalyzeBugPage() {
  const [form, setForm] = useState({
    title: '',
    description: '',
    error_logs: '',
    stack_trace: '',
  });
  const [file, setFile] = useState(null);
  const [connection, setConnection] = useState({ state: 'idle', data: null, error: null });
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [activeStep, setActiveStep] = useState(-1);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  const onChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const onFileChange = (e) => {
    const f = e.target.files?.[0];
    if (!f) {
      setFile(null);
      return;
    }
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXT.includes(ext)) {
      setError(`Unsupported file type "${ext}". Allowed: ${ALLOWED_EXT.join(', ')}`);
      setFile(null);
      return;
    }
    setError(null);
    setFile(f);
  };

  const handleTestConnection = async () => {
    setConnection({ state: 'checking', data: null, error: null });
    try {
      const data = await testConnection();
      setConnection({ state: 'ok', data, error: null });
    } catch (err) {
      setConnection({ state: 'error', data: null, error: err.message });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!form.title.trim()) {
      setError('Title is required.');
      return;
    }
    if (!form.description.trim() && !form.error_logs.trim() && !form.stack_trace.trim() && !file) {
      setError('Provide a description, error logs, stack trace, or upload a file.');
      return;
    }

    setSubmitting(true);
    setActiveStep(0);
    const timers = [
      setTimeout(() => setActiveStep(1), 250),
      setTimeout(() => setActiveStep(2), 600),
      setTimeout(() => setActiveStep(3), 1000),
      setTimeout(() => setActiveStep(4), 1400),
      setTimeout(() => setActiveStep(5), 1800),
    ];

    try {
      const data = await phase4Analyze({
        title: form.title.trim(),
        description: form.description,
        error_logs: form.error_logs,
        stack_trace: form.stack_trace,
        file,
      });
      timers.forEach(clearTimeout);
      setActiveStep(PIPELINE_STEPS.length);
      setResult(data);
    } catch (err) {
      timers.forEach(clearTimeout);
      setError(err.message || 'Phase 3 analysis failed.');
      setActiveStep(-1);
    } finally {
      setSubmitting(false);
    }
  };

  const triage = result?.triage;
  const logs = result?.log_intelligence;
  const pipeline = result?.pipeline || [];
  const similar = result?.similar_bugs || [];
  const recurrence = result?.recurrence;

  return (
    <div className="phase2-analyze-page">
      <div className="card">
        <h3>Analyze Bug</h3>
        <p className="section-subtitle">
          Phase 4 — log parse + AI triage + FAISS similar bugs + recurrence detection.
        </p>

        <div className="phase1-connection-row">
          <button type="button" className="btn btn-secondary" onClick={handleTestConnection}>
            Test API Connection
          </button>
          {connection.state === 'checking' && <span className="phase1-badge">Checking…</span>}
          {connection.state === 'ok' && (
            <span className="phase1-badge ok">Connected — {connection.data?.message}</span>
          )}
          {connection.state === 'error' && (
            <span className="phase1-badge err">Failed — {connection.error}</span>
          )}
        </div>

        <form className="phase1-form" onSubmit={handleSubmit}>
          <label>
            Title <span className="req">*</span>
            <input
              name="title"
              value={form.title}
              onChange={onChange}
              placeholder="e.g. NullPointerException in CheckoutService"
              required
            />
          </label>

          <label>
            Description
            <textarea
              name="description"
              value={form.description}
              onChange={onChange}
              rows={3}
              placeholder="What happened? Steps to reproduce…"
            />
          </label>

          <label>
            Error Logs
            <textarea
              name="error_logs"
              value={form.error_logs}
              onChange={onChange}
              rows={5}
              placeholder="Paste raw error logs here"
              className="mono"
            />
          </label>

          <label>
            Stack Trace
            <textarea
              name="stack_trace"
              value={form.stack_trace}
              onChange={onChange}
              rows={5}
              placeholder="Paste stack trace here"
              className="mono"
            />
          </label>

          <label>
            Upload file (.txt / .log / .json)
            <input ref={fileRef} type="file" accept=".txt,.log,.json" onChange={onFileChange} />
            {file && <span className="phase1-badge">{file.name}</span>}
          </label>

          {error && <p className="phase1-error">{error}</p>}

          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? 'Running Phase 4 Pipeline…' : 'Run Full Diagnosis'}
          </button>
        </form>
      </div>

      {(submitting || result) && (
        <div className="card">
          <h3>Agent Pipeline Progress</h3>
          <div className="phase2-pipeline">
            {(pipeline.length
              ? pipeline
              : PIPELINE_STEPS.map((name) => ({ name, status: 'pending', message: '' }))
            ).map((stage, idx) => {
              let status = stage.status;
              if (!result && submitting) {
                if (idx < activeStep) status = 'completed';
                else if (idx === activeStep) status = 'running';
                else status = 'pending';
              }
              return (
                <div key={stage.name || idx} className={`phase2-stage ${status}`}>
                  <span className="phase2-stage-dot" />
                  <div>
                    <strong>{stage.name}</strong>
                    <p>{stage.message || status}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {result && triage && (
        <div className="card">
          <h3>AI Triage</h3>
          <p className="section-subtitle">{result.overall_summary}</p>
          <div className="phase2-triage-grid">
            <div className="phase2-metric">
              <span>Severity</span>
              <strong className={`sev-${(triage.severity || '').toLowerCase()}`}>{triage.severity}</strong>
            </div>
            <div className="phase2-metric">
              <span>Priority</span>
              <strong>{triage.priority}</strong>
            </div>
            <div className="phase2-metric">
              <span>Category</span>
              <strong>{triage.category}</strong>
            </div>
            <div className="phase2-metric">
              <span>Confidence</span>
              <strong>{Math.round((triage.confidence || 0) * 100)}%</strong>
            </div>
          </div>
          {triage.reasoning && (
            <div className="phase2-reason">
              <h4>Why this triage?</h4>
              <p>{triage.reasoning}</p>
            </div>
          )}
        </div>
      )}

      {result && logs && (
        <div className="card">
          <h3>Parsed Log Intelligence</h3>
          <div className="phase2-log-grid">
            <div><span>Exception</span><strong>{logs.exception_type}</strong></div>
            <div><span>Language</span><strong>{logs.language}</strong></div>
            <div><span>File</span><strong>{logs.file_name}</strong></div>
            <div><span>Method</span><strong>{logs.method_name}</strong></div>
            <div><span>Line</span><strong>{logs.line_number ?? '—'}</strong></div>
            <div><span>Failure location</span><strong>{logs.failure_location}</strong></div>
          </div>
        </div>
      )}

      {result && (
        <div className="card">
          <h3>Similar Bugs (FAISS)</h3>
          <p className="section-subtitle">
            Backend: {result.rag_backend} · Knowledge base size: {result.knowledge_base_size}
          </p>
          {similar.length === 0 ? (
            <p className="section-subtitle">No similar historical bugs found.</p>
          ) : (
            <div className="phase3-similar-list">
              {similar.map((bug) => (
                <div key={bug.bug_id} className={`phase3-similar-item ${bug.is_likely_duplicate ? 'dup' : ''}`}>
                  <div className="phase3-similar-head">
                    <strong>
                      {bug.bug_id.startsWith('kb-') ? bug.bug_id : `Bug ${bug.bug_id.slice(0, 8)}`} —{' '}
                      {bug.similarity_percent}% similar
                    </strong>
                    {bug.is_likely_duplicate && <span className="phase1-badge err">Likely duplicate</span>}
                  </div>
                  <p>{bug.title}</p>
                  <p className="section-subtitle">
                    {bug.component || 'n/a'} · {bug.exception_type || 'n/a'}
                  </p>
                  {bug.root_cause && <p><em>Root cause:</em> {bug.root_cause}</p>}
                  {bug.resolution && <p><em>Resolution:</em> {bug.resolution}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {result && recurrence && (
        <div className="card">
          <h3>Recurrence Analysis</h3>
          <div className="phase2-triage-grid">
            <div className="phase2-metric">
              <span>Recurring?</span>
              <strong className={recurrence.is_recurring ? 'sev-high' : 'sev-low'}>
                {recurrence.is_recurring ? 'Yes' : 'No'}
              </strong>
            </div>
            <div className="phase2-metric">
              <span>Occurrences</span>
              <strong>{recurrence.occurrence_count}</strong>
            </div>
            <div className="phase2-metric">
              <span>Similar matches</span>
              <strong>{recurrence.similar_match_count}</strong>
            </div>
            <div className="phase2-metric">
              <span>Confidence</span>
              <strong>{Math.round((recurrence.confidence || 0) * 100)}%</strong>
            </div>
          </div>
          <p className="phase2-reason">{recurrence.pattern_summary}</p>
          {recurrence.recurring_components?.length > 0 && (
            <p className="phase2-tags">Components: {recurrence.recurring_components.join(', ')}</p>
          )}
          {recurrence.recurring_exceptions?.length > 0 && (
            <p className="phase2-tags">Exceptions: {recurrence.recurring_exceptions.join(', ')}</p>
          )}
        </div>
      )}

      
      {result?.root_cause && (
        <div className="card">
          <h3>Root Cause Analysis</h3>
          <div className="phase2-triage-grid">
            <div className="phase2-metric"><span>Confidence</span><strong>{Math.round((result.root_cause.confidence || 0) * 100)}%</strong></div>
            <div className="phase2-metric"><span>Category</span><strong>{result.root_cause.category}</strong></div>
            <div className="phase2-metric"><span>Failure location</span><strong>{result.root_cause.failure_location}</strong></div>
          </div>
          <div className="phase2-reason"><h4>Probable cause</h4><p>{result.root_cause.probable_cause}</p></div>
          {result.root_cause.explanation && <p className="section-subtitle">{result.root_cause.explanation}</p>}
          {result.root_cause.evidence?.length > 0 && (
            <ul>{result.root_cause.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
          )}
        </div>
      )}

      {result?.ranked_fixes?.length > 0 && (
        <div className="card">
          <h3>Ranked Fix Recommendations</h3>
          <div className="phase3-similar-list">
            {result.ranked_fixes.map((fix) => (
              <div key={fix.rank} className="phase3-similar-item">
                <div className="phase3-similar-head">
                  <strong>#{fix.rank} {fix.title}</strong>
                  <span className="phase1-badge">{Math.round((fix.confidence || 0) * 100)}% · {fix.difficulty} · {fix.estimated_time}</span>
                </div>
                <ol>{(fix.steps || []).map((s, i) => <li key={i}>{s}</li>)}</ol>
                {fix.code_suggestion && <pre className="phase1-json">{fix.code_suggestion}</pre>}
                {fix.prevention?.length > 0 && <p><em>Prevention:</em> {fix.prevention.join('; ')}</p>}
                {fix.testing?.length > 0 && <p><em>Testing:</em> {fix.testing.join('; ')}</p>}
                {fix.risks?.length > 0 && <p><em>Risks:</em> {fix.risks.join('; ')}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {result?.risk && (
        <div className="card">
          <h3>Bug Risk Score</h3>
          <div className="phase2-triage-grid">
            <div className="phase2-metric"><span>Score</span><strong>{result.risk.score}/100</strong></div>
            <div className="phase2-metric"><span>Level</span><strong>{result.risk.level}</strong></div>
          </div>
          <p className="section-subtitle">{result.risk.summary}</p>
          <ul>{(result.risk.factors || []).map((f, i) => <li key={i}>{f}</li>)}</ul>
        </div>
      )}

{result && (
        <div className="card">
          <p className="section-subtitle">
            Bug ID: <code>{result.bug_id}</code> · Analysis ID: <code>{result.analysis_id}</code>
          </p>
          <p className="phase1-badge">{result.next_phase}</p>
        </div>
      )}
    </div>
  );
}
