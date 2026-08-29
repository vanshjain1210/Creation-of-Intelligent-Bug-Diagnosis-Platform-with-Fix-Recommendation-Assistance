import React from 'react';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: '◫' },
  { id: 'analyze', label: 'Analyze Bug', icon: '⚡' },
  { id: 'upload', label: 'Bug Upload', icon: '↑' },
  { id: 'history', label: 'History', icon: '☰' },
  { id: 'knowledge', label: 'Knowledge Base', icon: '◫' },
  { id: 'results', label: 'Analysis Findings', icon: '✓' },
  { id: 'analytics', label: 'Analytics', icon: '📈' },
  { id: 'health', label: 'System Health', icon: '♥' },
  { id: 'settings', label: 'Settings', icon: '⚙' },
];

export default function Sidebar({ activeView, onNavigate, systemStatus }) {
  const statusColor = {
    ready: '#10b981',
    degraded: '#f59e0b',
    unavailable: '#ef4444',
    checking: '#94a3b8',
  }[systemStatus] || '#94a3b8';

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1>Smart Bug Analyzer</h1>
        <p>Fix Advisor — Internship Project</p>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activeView === item.id ? 'active' : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>
      <div className="sidebar-status">
        <span
          className="status-dot"
          style={{ color: statusColor, backgroundColor: statusColor }}
        />
        Node Status: <strong style={{ color: statusColor }}>{systemStatus.toUpperCase()}</strong>
      </div>
    </aside>
  );
}
