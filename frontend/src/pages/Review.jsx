import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getRecords, approveRecord, rejectRecord, bulkApprove, bulkReject, getAuditLog, editRecord
} from '../api/client.js'
import {
  CheckCircle, XCircle, AlertTriangle, ChevronsLeft, ChevronLeft,
  ChevronRight, ChevronsRight, Search, SlidersHorizontal, X
} from 'lucide-react'
import StatusBadge from '../components/StatusBadge.jsx'

const fmt = (n, d = 2) => n == null ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: d })
const fmtDate = (d) => d ? new Date(d).toLocaleDateString() : '—'

const SCOPE_COLORS = {
  '1': 'bg-blue-400/15 text-blue-300',
  '2': 'bg-purple-400/15 text-purple-300',
  '3': 'bg-emerald-400/15 text-emerald-300',
}
const SOURCE_COLORS = {
  SAP: 'bg-amber-400/15 text-amber-300',
  UTILITY: 'bg-purple-400/15 text-purple-300',
  TRAVEL: 'bg-emerald-400/15 text-emerald-300',
}

function Pill({ children, color = 'bg-[var(--bg)] text-[var(--text-muted)]' }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wide ${color}`}>
      {children}
    </span>
  )
}

/* ── Record detail modal ── */
function RecordModal({ record, onClose }) {
  const qc = useQueryClient()
  const [notes, setNotes] = useState('')
  const [editMode, setEditMode] = useState(false)
  const [editQty, setEditQty] = useState(String(record.raw_quantity))

  const { data: auditData } = useQuery({
    queryKey: ['audit', record.id],
    queryFn: () => getAuditLog(record.id),
  })
  const auditLogs = auditData?.data || []

  const approveMut = useMutation({
    mutationFn: () => approveRecord(record.id, notes),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['records'] }); onClose() },
  })
  const rejectMut = useMutation({
    mutationFn: () => rejectRecord(record.id, notes),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['records'] }); onClose() },
  })
  const editMut = useMutation({
    mutationFn: () => editRecord(record.id, { raw_quantity: parseFloat(editQty) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['records'] }); setEditMode(false) },
  })

  const canAct = !['APPROVED', 'REJECTED'].includes(record.status)

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full sm:max-w-2xl bg-[var(--bg-card)] border border-[var(--border)] rounded-t-2xl sm:rounded-2xl shadow-2xl flex flex-col max-h-[92vh] sm:max-h-[90vh]"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-4 sm:p-5 border-b border-[var(--border)] shrink-0">
          <div className="min-w-0 flex-1 pr-3">
            <div className="flex flex-wrap items-center gap-1.5 mb-1">
              <Pill color={SCOPE_COLORS[record.scope]}>S{record.scope}</Pill>
              <Pill color={SOURCE_COLORS[record.source_type]}>{record.source_type}</Pill>
              <StatusBadge status={record.status} />
              {record.is_manually_edited && <Pill color="bg-orange-400/15 text-orange-300">Edited</Pill>}
            </div>
            <h3 className="font-semibold text-[var(--text)] text-sm leading-snug">{record.description || record.category}</h3>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              {record.facility_code && `${record.facility_code} · `}
              {fmtDate(record.period_start)} – {fmtDate(record.period_end)}
            </p>
          </div>
          <button onClick={onClose} className="text-[var(--text-muted)] hover:text-[var(--text)] p-1 shrink-0">
            <X size={18} />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 p-4 sm:p-5 space-y-4">
          {/* Flags */}
          {record.flags?.length > 0 && (
            <div className="rounded-lg bg-yellow-400/10 border border-yellow-400/20 p-3 space-y-1">
              <div className="text-xs font-semibold text-yellow-400 flex items-center gap-1.5">
                <AlertTriangle size={12} /> Auto-flags
              </div>
              {record.flags.map((f, i) => (
                <div key={i} className="text-xs text-[var(--text-muted)]">• {f.message}</div>
              ))}
            </div>
          )}

          {/* Quantities */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[var(--bg)] rounded-lg p-3">
              <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Raw Quantity</div>
              {editMode ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <input type="number" value={editQty} onChange={e => setEditQty(e.target.value)}
                      className="bg-[var(--bg-card)] border border-[var(--border)] rounded px-2 py-1 text-sm text-[var(--text)] w-24" />
                    <span className="text-xs text-[var(--text-muted)]">{record.raw_unit}</span>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => editMut.mutate()} className="text-xs text-forest-400 hover:underline">Save</button>
                    <button onClick={() => setEditMode(false)} className="text-xs text-[var(--text-muted)]">Cancel</button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap items-baseline gap-1.5">
                  <span className="text-lg font-semibold text-[var(--text)] tabular-nums">{fmt(record.raw_quantity, 4)}</span>
                  <span className="text-xs text-[var(--text-muted)]">{record.raw_unit}</span>
                  {canAct && <button onClick={() => setEditMode(true)} className="text-[10px] text-forest-400 hover:underline">edit</button>}
                </div>
              )}
            </div>
            <div className="bg-[var(--bg)] rounded-lg p-3">
              <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">CO₂e</div>
              <div className="flex flex-wrap items-baseline gap-1.5">
                <span className="text-lg font-semibold text-[var(--text)] tabular-nums">
                  {record.quantity_co2e_kg != null ? fmt(record.quantity_co2e_kg / 1000, 3) : '—'}
                </span>
                <span className="text-xs text-[var(--text-muted)]">t CO₂e</span>
              </div>
            </div>
          </div>

          {record.emission_factor && (
            <div className="text-xs text-[var(--text-muted)] bg-[var(--bg)] rounded p-2.5 font-mono break-all">
              Factor: {record.emission_factor} kg CO₂e/{record.normalized_unit} · {record.emission_factor_source}
            </div>
          )}

          {/* Raw data */}
          <div>
            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1.5">Source Row</div>
            <pre className="text-[10px] bg-[var(--bg)] rounded-lg p-3 overflow-x-auto text-[var(--text-muted)] leading-relaxed whitespace-pre-wrap break-all">
              {JSON.stringify(record.raw_data, null, 2)}
            </pre>
          </div>

          {/* Audit log */}
          {auditLogs.length > 0 && (
            <div>
              <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-1.5">Audit Trail</div>
              <div className="space-y-1.5">
                {auditLogs.map(log => (
                  <div key={log.id} className="text-xs flex flex-wrap gap-x-2 gap-y-0.5">
                    <span className="text-[var(--text-muted)]">{new Date(log.timestamp).toLocaleString()}</span>
                    <span className="font-medium text-[var(--text)]">{log.user_display}</span>
                    <span className="text-[var(--text-muted)]">{log.action}</span>
                    {log.note && <span className="text-[var(--text-muted)] italic">"{log.note}"</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {canAct && (
            <div>
              <label className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider block mb-1.5">
                Review Notes (optional)
              </label>
              <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
                placeholder="Add context for the audit trail…"
                className="w-full bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs text-[var(--text)] resize-none focus:outline-none focus:border-forest-400/50"
              />
            </div>
          )}
        </div>

        {canAct && (
          <div className="flex gap-2 p-4 border-t border-[var(--border)] shrink-0">
            <button onClick={() => approveMut.mutate()} disabled={approveMut.isPending}
              className="btn-primary flex items-center gap-1.5 flex-1 justify-center text-sm">
              <CheckCircle size={13} /> Approve
            </button>
            <button onClick={() => rejectMut.mutate()} disabled={rejectMut.isPending}
              className="btn-secondary flex items-center gap-1.5 flex-1 justify-center text-sm text-red-400 border-red-400/30 hover:bg-red-400/10">
              <XCircle size={13} /> Reject
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Mobile record card ── */
function RecordCard({ record, selected, onSelect, onClick }) {
  const canSelect = !['APPROVED', 'REJECTED'].includes(record.status)
  return (
    <div className="card p-3 space-y-2 cursor-pointer active:opacity-80" onClick={onClick}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap gap-1 items-center">
          <Pill color={SCOPE_COLORS[record.scope]}>S{record.scope}</Pill>
          <Pill color={SOURCE_COLORS[record.source_type]}>{record.source_type}</Pill>
          <StatusBadge status={record.status} />
          {record.flags?.length > 0 && (
            <span className="inline-flex items-center gap-0.5 text-yellow-400 text-[10px]">
              <AlertTriangle size={10} />{record.flags.length}
            </span>
          )}
        </div>
        {canSelect && (
          <input type="checkbox" checked={selected} onClick={e => e.stopPropagation()}
            onChange={() => onSelect(record.id)} className="rounded shrink-0 mt-0.5" />
        )}
      </div>
      <div className="text-xs font-medium text-[var(--text)] leading-snug">{record.description || record.category}</div>
      <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)]">
        <span>{record.facility_code || '—'} · {fmtDate(record.period_start)}</span>
        <span className="font-mono tabular-nums font-semibold text-[var(--text)]">
          {record.quantity_co2e_kg != null ? `${fmt(record.quantity_co2e_kg / 1000, 3)} t` : '—'}
        </span>
      </div>
    </div>
  )
}

const PAGE_SIZE = 50

export default function Review() {
  const qc = useQueryClient()
  const [selected, setSelected] = useState(new Set())
  const [modalRecord, setModalRecord] = useState(null)
  const [page, setPage] = useState(1)
  const [showFilters, setShowFilters] = useState(false)
  const [filters, setFilters] = useState({ status: '', scope: '', source_type: '', search: '' })

  const params = { page, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) }

  const { data, isLoading } = useQuery({
    queryKey: ['records', params],
    queryFn: () => getRecords(params),
    keepPreviousData: true,
  })

  const records = data?.data?.results || []
  const count = data?.data?.count || 0
  const totalPages = Math.ceil(count / PAGE_SIZE)

  const bulkApproveMut = useMutation({
    mutationFn: () => bulkApprove([...selected]),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['records'] }); setSelected(new Set()) },
  })
  const bulkRejectMut = useMutation({
    mutationFn: () => bulkReject([...selected], ''),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['records'] }); setSelected(new Set()) },
  })

  const toggleSelect = useCallback((id) => {
    setSelected(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })
  }, [])

  const toggleAll = () => {
    const reviewable = records.filter(r => !['APPROVED', 'REJECTED'].includes(r.status))
    if (reviewable.every(r => selected.has(r.id))) setSelected(new Set())
    else setSelected(new Set(reviewable.map(r => r.id)))
  }

  const setFilter = (key, val) => { setFilters(f => ({ ...f, [key]: val })); setPage(1) }
  const hasFilters = Object.values(filters).some(Boolean)

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-4 sm:space-y-5 max-w-7xl mx-auto">

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold text-[var(--text)]">Review Queue</h1>
          <p className="text-sm text-[var(--text-muted)] mt-0.5">{count.toLocaleString()} records</p>
        </div>
        {selected.size > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-[var(--text-muted)]">{selected.size} selected</span>
            <button onClick={() => bulkApproveMut.mutate()} disabled={bulkApproveMut.isPending}
              className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1">
              <CheckCircle size={11} /> Approve
            </button>
            <button onClick={() => bulkRejectMut.mutate()} disabled={bulkRejectMut.isPending}
              className="text-xs py-1.5 px-3 flex items-center gap-1 rounded-lg border border-red-400/30 text-red-400 hover:bg-red-400/10">
              <XCircle size={11} /> Reject
            </button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="space-y-2">
        {/* Search + filter toggle */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input placeholder="Search description, facility…" value={filters.search}
              onChange={e => setFilter('search', e.target.value)}
              className="w-full bg-[var(--bg-card)] border border-[var(--border)] rounded-lg pl-8 pr-3 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-forest-400/50" />
          </div>
          <button onClick={() => setShowFilters(f => !f)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs transition-colors
              ${showFilters || hasFilters
                ? 'border-forest-400/50 text-forest-400 bg-forest-400/10'
                : 'border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)]'}`}>
            <SlidersHorizontal size={13} />
            <span className="hidden sm:inline">Filters</span>
            {hasFilters && <span className="w-1.5 h-1.5 rounded-full bg-forest-400" />}
          </button>
        </div>

        {/* Expandable filter dropdowns */}
        {showFilters && (
          <div className="flex flex-wrap gap-2">
            {[
              { key: 'status', label: 'Status', opts: ['PENDING', 'FLAGGED', 'APPROVED', 'REJECTED'] },
              { key: 'scope', label: 'Scope', opts: ['1', '2', '3'] },
              { key: 'source_type', label: 'Source', opts: ['SAP', 'UTILITY', 'TRAVEL'] },
            ].map(({ key, label, opts }) => (
              <select key={key} value={filters[key]} onChange={e => setFilter(key, e.target.value)}
                className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg px-2.5 py-2 text-xs text-[var(--text)] focus:outline-none focus:border-forest-400/50 cursor-pointer">
                <option value="">All {label}s</option>
                {opts.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            ))}
            {hasFilters && (
              <button onClick={() => { setFilters({ status: '', scope: '', source_type: '', search: '' }); setPage(1) }}
                className="text-xs text-forest-400 hover:underline px-1">Clear all</button>
            )}
          </div>
        )}
      </div>

      {/* ── Desktop table (hidden on mobile) ── */}
      <div className="hidden md:block card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--bg)]">
                <th className="w-8 px-3 py-2.5">
                  <input type="checkbox" onChange={toggleAll}
                    checked={records.filter(r => !['APPROVED','REJECTED'].includes(r.status)).length > 0 &&
                      records.filter(r => !['APPROVED','REJECTED'].includes(r.status)).every(r => selected.has(r.id))}
                    className="rounded" />
                </th>
                {['Status','Scope','Source','Description','Facility','Period','t CO₂e','Flags'].map(h => (
                  <th key={h} className={`px-3 py-2.5 font-semibold text-[var(--text-muted)] uppercase tracking-wider whitespace-nowrap ${h === 't CO₂e' ? 'text-right' : h === 'Flags' ? 'text-center' : 'text-left'}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={9} className="py-12 text-center text-[var(--text-muted)]">Loading…</td></tr>
              ) : records.length === 0 ? (
                <tr><td colSpan={9} className="py-12 text-center text-[var(--text-muted)]">No records match the current filters.</td></tr>
              ) : records.map(record => (
                <tr key={record.id} onClick={() => setModalRecord(record)}
                  className="border-b border-[var(--border)] hover:bg-[var(--bg)] cursor-pointer transition-colors">
                  <td className="px-3 py-2.5" onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={selected.has(record.id)} onChange={() => toggleSelect(record.id)}
                      disabled={['APPROVED','REJECTED'].includes(record.status)} className="rounded" />
                  </td>
                  <td className="px-3 py-2.5"><StatusBadge status={record.status} /></td>
                  <td className="px-3 py-2.5"><Pill color={SCOPE_COLORS[record.scope]}>S{record.scope}</Pill></td>
                  <td className="px-3 py-2.5"><Pill color={SOURCE_COLORS[record.source_type]}>{record.source_type}</Pill></td>
                  <td className="px-3 py-2.5 max-w-[180px]">
                    <div className="truncate text-[var(--text)]">{record.description || record.category}</div>
                    {record.subcategory && <div className="text-[10px] text-[var(--text-muted)] truncate">{record.subcategory}</div>}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-[var(--text-muted)] whitespace-nowrap">{record.facility_code || '—'}</td>
                  <td className="px-3 py-2.5 text-[var(--text-muted)] whitespace-nowrap">{fmtDate(record.period_start)}</td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-[var(--text)] whitespace-nowrap">
                    {record.quantity_co2e_kg != null ? fmt(record.quantity_co2e_kg / 1000, 3) : <span className="text-[var(--text-muted)]">—</span>}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    {record.flags?.length > 0 && (
                      <span className="inline-flex items-center gap-1 text-yellow-400">
                        <AlertTriangle size={11} /><span>{record.flags.length}</span>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--border)]">
            <span className="text-xs text-[var(--text-muted)]">Page {page} of {totalPages} · {count} records</span>
            <div className="flex items-center gap-1">
              {[
                { icon: ChevronsLeft,  action: () => setPage(1),                  disabled: page === 1 },
                { icon: ChevronLeft,   action: () => setPage(p => Math.max(1,p-1)),disabled: page === 1 },
                { icon: ChevronRight,  action: () => setPage(p => Math.min(totalPages,p+1)), disabled: page === totalPages },
                { icon: ChevronsRight, action: () => setPage(totalPages),          disabled: page === totalPages },
              ].map(({ icon: Icon, action, disabled }, i) => (
                <button key={i} onClick={action} disabled={disabled}
                  className="p-1.5 rounded hover:bg-[var(--bg)] disabled:opacity-40 text-[var(--text-muted)]">
                  <Icon size={14} />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Mobile cards (hidden on md+) ── */}
      <div className="md:hidden space-y-3">
        {isLoading ? (
          <div className="text-center text-xs text-[var(--text-muted)] py-8">Loading…</div>
        ) : records.length === 0 ? (
          <div className="text-center text-xs text-[var(--text-muted)] py-8">No records match the current filters.</div>
        ) : records.map(record => (
          <RecordCard key={record.id} record={record}
            selected={selected.has(record.id)}
            onSelect={toggleSelect}
            onClick={() => setModalRecord(record)}
          />
        ))}

        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-[var(--text-muted)]">Page {page} of {totalPages}</span>
            <div className="flex gap-1">
              <button onClick={() => setPage(p => Math.max(1,p-1))} disabled={page === 1}
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs text-[var(--text-muted)] disabled:opacity-40">Prev</button>
              <button onClick={() => setPage(p => Math.min(totalPages,p+1))} disabled={page === totalPages}
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs text-[var(--text-muted)] disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>

      {modalRecord && <RecordModal record={modalRecord} onClose={() => setModalRecord(null)} />}
    </div>
  )
}
