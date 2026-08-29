import React from 'react';

/**
 * Phase 1 Dashboard page wrapper.
 * Existing dashboard UI is still rendered from App for now;
 * this page is the structural hook for later phases.
 */
export default function DashboardPage({ children }) {
  return <div className="page-dashboard">{children}</div>;
}
