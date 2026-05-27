import clsx from 'clsx'

const CONFIG = {
  PENDING:  { label: 'Pending',  cls: 'bg-yellow-900/40 text-yellow-300 border border-yellow-800/50' },
  FLAGGED:  { label: 'Flagged',  cls: 'bg-orange-900/40 text-orange-300 border border-orange-800/50' },
  APPROVED: { label: 'Approved', cls: 'bg-forest-900/60 text-forest-300 border border-forest-700/50' },
  REJECTED: { label: 'Rejected', cls: 'bg-red-900/30 text-red-400 border border-red-900/50' },
}

export default function StatusBadge({ status }) {
  const c = CONFIG[status] || CONFIG.PENDING
  return (
    <span className={clsx('badge', c.cls)}>
      {c.label}
    </span>
  )
}

export function ScopeBadge({ scope }) {
  const colors = {
    '1': 'bg-blue-900/40 text-blue-300 border border-blue-800/50',
    '2': 'bg-purple-900/40 text-purple-300 border border-purple-800/50',
    '3': 'bg-cyan-900/40 text-cyan-300 border border-cyan-800/50',
  }
  return (
    <span className={clsx('badge', colors[scope] || 'bg-gray-800 text-gray-400')}>
      Scope {scope}
    </span>
  )
}

export function SourceBadge({ sourceType }) {
  const labels = { SAP: 'SAP', UTILITY: 'Utility', TRAVEL: 'Travel' }
  return (
    <span className="badge bg-[var(--bg-surface)] text-[var(--text-muted)] border border-[var(--border)]">
      {labels[sourceType] || sourceType}
    </span>
  )
}
