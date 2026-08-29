import React, { useEffect, useState } from 'react';
import { addKnowledgeEntry, listKnowledgeBase, seedKnowledgeBase } from '../services/api';

/**
 * Phase 3 Knowledge Base page — FAISS-indexed historical bugs.
 */
export default function KnowledgeBasePage() {
  const [items, setItems] = useState([]);
  const [backend, setBackend] = useState('');
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [form, setForm] = useState({
    title: '',
    description: '',
    component: '',
    exception_type: '',
    root_cause: '',
    resolution: '',
  });

  const load = async (q = search) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listKnowledgeBase({ search: q, limit: 100 });
      setItems(data.items || []);
      setBackend(data.backend || '');
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message || 'Failed to load knowledge base.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSeed = async () => {
    setMessage(null);
    try {
      const data = await seedKnowledgeBase();
      setMessage(
        `Seeded ${data.seeded_added ?? 0} entries. Total: ${data.total_documents}. Backend: ${data.backend}`
      );
      await load(search);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    setMessage(null);
    setError(null);
    if (!form.title.trim()) {
      setError('Title is required.');
      return;
    }
    try {
      const data = await addKnowledgeEntry(form);
      setMessage(data.message || 'Entry added.');
      setForm({
        title: '',
        description: '',
        component: '',
        exception_type: '',
        root_cause: '',
        resolution: '',
      });
      await load(search);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="phase3-kb-page">
      <div className="card">
        <h3>Knowledge Base</h3>
        <p className="section-subtitle">
          FAISS + SentenceTransformers index of historical resolved bugs
          ({backend || '…'} · {total} documents)
        </p>
        <div className="phase1-connection-row">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search title, component, exception…"
            className="phase3-kb-search"
          />
          <button type="button" className="btn btn-secondary" onClick={() => load(search)}>
            Search
          </button>
          <button type="button" className="btn btn-secondary" onClick={handleSeed}>
            Seed Demo Bugs
          </button>
        </div>
        {message && <p className="phase1-badge ok">{message}</p>}
        {error && <p className="phase1-error">{error}</p>}
      </div>

      <div className="card">
        <h3>Add Resolved Bug</h3>
        <form className="phase1-form" onSubmit={handleAdd}>
          <label>
            Title <span className="req">*</span>
            <input name="title" value={form.title} onChange={onChange} required />
          </label>
          <label>
            Description
            <textarea name="description" value={form.description} onChange={onChange} rows={2} />
          </label>
          <label>
            Component
            <input name="component" value={form.component} onChange={onChange} placeholder="backend / api / database" />
          </label>
          <label>
            Exception type
            <input name="exception_type" value={form.exception_type} onChange={onChange} />
          </label>
          <label>
            Root cause
            <textarea name="root_cause" value={form.root_cause} onChange={onChange} rows={2} />
          </label>
          <label>
            Resolution
            <textarea name="resolution" value={form.resolution} onChange={onChange} rows={2} />
          </label>
          <button type="submit" className="btn btn-primary">
            Index in FAISS
          </button>
        </form>
      </div>

      <div className="card">
        <h3>Indexed Entries</h3>
        {loading ? (
          <p>Loading…</p>
        ) : items.length === 0 ? (
          <p className="section-subtitle">No entries yet. Click “Seed Demo Bugs” or add one above.</p>
        ) : (
          <div className="phase3-similar-list">
            {items.map((item) => (
              <div key={item.id} className="phase3-similar-item">
                <div className="phase3-similar-head">
                  <strong>{item.title}</strong>
                  <span className="phase1-badge">{item.status || 'resolved'}</span>
                </div>
                <p className="section-subtitle">
                  {item.id} · {item.component || 'n/a'} · {item.exception_type || 'n/a'}
                </p>
                {item.root_cause && <p><em>Root cause:</em> {item.root_cause}</p>}
                {item.resolution && <p><em>Resolution:</em> {item.resolution}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
