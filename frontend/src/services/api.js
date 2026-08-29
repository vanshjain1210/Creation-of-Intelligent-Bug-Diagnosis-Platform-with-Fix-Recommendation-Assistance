const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || `Request failed: ${response.status}`);
  }
  return data;
}

export async function getHealth() {
  return request('/health');
}

export async function getStatus() {
  return request('/status');
}

export async function submitBug({ content, title, file }) {
  const formData = new FormData();
  if (file) {
    formData.append('file', file);
  }
  if (content) {
    formData.append('content', content);
  }
  if (title) {
    formData.append('title', title);
  }
  return request('/submit-bug', { method: 'POST', body: formData });
}

export async function analyzeBug(bugId) {
  return request('/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bug_id: bugId, use_mmr: true }),
  });
}

export async function getHistory() {
  return request('/history');
}

export async function getSettings() {
  return request('/settings');
}

export async function getAnalysis(analysisId) {
  return request(`/analysis/${analysisId}`);
}

export async function getBug(bugId) {
  return request(`/bug/${bugId}`);
}

export async function testConnection() {
  return request('/test');
}

export async function phase1Analyze(payload) {
  return request('/phase1/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function phase2Analyze({ title, description, error_logs, stack_trace, file }) {
  const formData = new FormData();
  formData.append('title', title || '');
  formData.append('description', description || '');
  formData.append('error_logs', error_logs || '');
  formData.append('stack_trace', stack_trace || '');
  if (file) {
    formData.append('file', file);
  }
  return request('/phase2/analyze', { method: 'POST', body: formData });
}

export async function phase3Analyze({ title, description, error_logs, stack_trace, file }) {
  const formData = new FormData();
  formData.append('title', title || '');
  formData.append('description', description || '');
  formData.append('error_logs', error_logs || '');
  formData.append('stack_trace', stack_trace || '');
  if (file) formData.append('file', file);
  return request('/phase3/analyze', { method: 'POST', body: formData });
}

export async function listKnowledgeBase({ search = '', limit = 100 } = {}) {
  const qs = new URLSearchParams({ search, limit: String(limit) });
  return request('/knowledge-base/faiss?' + qs.toString());
}

export async function addKnowledgeEntry(payload) {
  return request('/knowledge-base/faiss', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function seedKnowledgeBase() {
  return request('/knowledge-base/faiss/seed', { method: 'POST' });
}

export async function phase4Analyze({ title, description, error_logs, stack_trace, file }) {
  const formData = new FormData();
  formData.append('title', title || '');
  formData.append('description', description || '');
  formData.append('error_logs', error_logs || '');
  formData.append('stack_trace', stack_trace || '');
  if (file) formData.append('file', file);
  return request('/phase4/analyze', { method: 'POST', body: formData });
}

