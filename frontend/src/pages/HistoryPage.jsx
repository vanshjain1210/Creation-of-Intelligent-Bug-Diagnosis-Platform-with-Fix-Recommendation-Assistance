import React from 'react';
import HistoryPanel from '../components/HistoryPanel';

/** Phase 1 History page — reuses existing history panel. */
export default function HistoryPage({ onSelectAnalysis }) {
  return (
    <div className="page-history">
      <HistoryPanel onSelectAnalysis={onSelectAnalysis} />
    </div>
  );
}
