import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { getDashboard } from '../api/client.js'
import { Clock, CheckCircle, AlertTriangle, XCircle, Upload, ArrowRight } from 'lucide-react'

const SCOPE_COLORS = { '1': '#60a5fa', '2': '#a78bfa', '3': '#34d399' }
const SOURCE_COLORS = { SAP: '#f59e0b', UTILITY: '#a78bfa', TRAVEL: '#34d399' }

function Stat({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="card flex items-start gap-3 sm:gap-4">
      <div className={`w-8 h-8 sm:w-9 sm:h-9 rounded-lg flex items-center justify-center shrink-0 ${color}`}>
        <Icon size={15} />
      </div>
      <div className="min-w-0">
        <div className="text-xl sm:text-2xl font-semibold text-[var(--text)] tabular-nums">{value ?? '—'}</div>
        <div className="text-xs font-medium text-[var(--text-muted)] mt-0.5 leading-tight">{label}</div>
        {sub && <div className="text-[10px] text-[var(--text-muted)] mt-1 opacity-70">{sub}</div>}
      </div>
    </div>
  )
}

function JobRow({ job }) {
  const statusColor = {
    COMPLETED: 'text-forest-400',
    PARTIAL: 'text-yellow-400',
    FAILED: 'text-red-400',
    PROCESSING: 'text-blue-400',
  }[job.status] || 'text-[var(--text-muted)]'

  return (
    <div className="flex items-start sm:items-center justify-between gap-2 py-2.5 border-b border-[var(--border)] last:border-0">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-medium text-[var(--text)] truncate max-w-[160px] sm:max-w-none">{job.file_name}</span>
          <span className="badge bg-[var(--bg-surface)] text-[var(--text-muted)] border border-[var(--border)] shrink-0">
            {job.source_type_display}
          </span>
        </div>
        <div className="text-[10px] text-[var(--text-muted)] mt-0.5">
          {job.success_rows} rows · {job.flagged_rows} flagged · {job.error_rows} errors
        </div>
      </div>
      <span className={`text-xs font-medium shrink-0 ${statusColor}`}>{job.status}</span>
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload?.length) {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs shadow-xl">
        <div className="text-[var(--text-muted)] mb-1">{label}</div>
        <div className="text-[var(--text)] font-medium">{payload[0].value?.toFixed(2)} t CO₂e</div>
      </div>
    )
  }
  return null
}

export default function Dashboard() {
  const { data: raw, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
    select: r => r.data,
    refetchInterval: 30_000,
  })

  if (isLoading) return (
    <div className="p-6 sm:p-8">
      <div className="text-sm text-[var(--text-muted)] animate-pulse">Loading dashboard…</div>
    </div>
  )

  if (error) return (
    <div className="p-6 sm:p-8">
      <div className="text-sm text-red-400">Failed to load dashboard. Check your connection.</div>
    </div>
  )

  const scopeChartData = Object.entries(raw.scope_breakdown || {}).map(([scope, tonnes]) => ({
    name: `Scope ${scope}`, tonnes, color: SCOPE_COLORS[scope] || '#888',
  }))

  const sourceChartData = Object.entries(raw.source_breakdown || {}).map(([src, d]) => ({
    name: src, count: d.count, pending: d.pending, flagged: d.flagged,
    approved: d.approved, color: SOURCE_COLORS[src] || '#888',
  }))

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto">

      {/* Header */}
      <div className="mb-6 sm:mb-8 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold text-[var(--text)]">Dashboard</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">Emissions data overview</p>
        </div>
        <Link to="/ingest" className="btn-primary text-xs">
          <Upload size={13} />
          Import data
        </Link>
      </div>

      {/* Stat cards — 2 cols on mobile, 4 on desktop */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-5 sm:mb-6">
        <Stat icon={Clock} label="Pending review" value={raw.pending}
          color="bg-yellow-900/40 text-yellow-300"
          sub={`${raw.flagged} flagged`}
        />
        <Stat icon={CheckCircle} label="Approved" value={raw.approved}
          color="bg-forest-900/60 text-forest-300"
          sub={`${raw.approved_co2e_tonnes?.toFixed(1)} t CO₂e locked`}
        />
        <Stat icon={AlertTriangle} label="Flagged" value={raw.flagged}
          color="bg-orange-900/40 text-orange-300"
          sub="needs attention"
        />
        <Stat icon={XCircle} label="Rejected" value={raw.rejected}
          color="bg-red-900/30 text-red-400"
        />
      </div>

      {/* Total CO2e banner */}
      <div className="card mb-5 sm:mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs text-[var(--text-muted)] mb-1">Total CO₂e (all records)</div>
          <div className="text-2xl sm:text-3xl font-semibold text-[var(--text)] tabular-nums">
            {raw.total_co2e_tonnes?.toFixed(1)}
            <span className="text-base sm:text-lg text-[var(--text-muted)] font-normal ml-2">t CO₂e</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-[var(--text-muted)] mb-1">Approved &amp; locked</div>
          <div className="text-lg sm:text-xl font-semibold text-forest-400 tabular-nums">
            {raw.approved_co2e_tonnes?.toFixed(1)} t
          </div>
        </div>
      </div>

      {/* Charts — stack on mobile, side by side on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5 sm:mb-6">
        <div className="card">
          <div className="text-xs font-medium text-[var(--text-muted)] mb-4">CO₂e by Scope (approved)</div>
          {scopeChartData.length ? (
            <ResponsiveContainer width="100%" height={150}>
              <BarChart data={scopeChartData} barSize={28}>
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={45} tickFormatter={v => `${v.toFixed(0)}t`} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="tonnes" radius={[4, 4, 0, 0]}>
                  {scopeChartData.map((e, i) => <Cell key={i} fill={e.color} fillOpacity={0.85} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-36 flex items-center justify-center text-sm text-[var(--text-muted)]">No approved records yet</div>
          )}
        </div>

        <div className="card">
          <div className="text-xs font-medium text-[var(--text-muted)] mb-4">Records by Source</div>
          {sourceChartData.length ? (
            <ResponsiveContainer width="100%" height={150}>
              <BarChart data={sourceChartData} barSize={28}>
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={35} />
                <Tooltip content={({ active, payload, label }) => active && payload?.length ? (
                  <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs space-y-0.5 shadow-xl">
                    <div className="text-[var(--text-muted)]">{label}</div>
                    <div className="text-[var(--text)]">Total: {payload[0].payload.count}</div>
                    <div className="text-yellow-400">Pending: {payload[0].payload.pending}</div>
                    <div className="text-orange-400">Flagged: {payload[0].payload.flagged}</div>
                    <div className="text-forest-400">Approved: {payload[0].payload.approved}</div>
                  </div>
                ) : null} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {sourceChartData.map((e, i) => <Cell key={i} fill={e.color} fillOpacity={0.85} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-36 flex items-center justify-center text-sm text-[var(--text-muted)]">No records yet</div>
          )}
        </div>
      </div>

      {/* Recent jobs */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-medium text-[var(--text-muted)]">Recent ingestion jobs</div>
          <Link to="/ingest" className="text-xs text-forest-400 hover:text-forest-300 flex items-center gap-1">
            View all <ArrowRight size={11} />
          </Link>
        </div>
        {raw.recent_jobs?.length ? (
          raw.recent_jobs.map(j => <JobRow key={j.id} job={j} />)
        ) : (
          <div className="text-sm text-[var(--text-muted)] py-4 text-center">
            No imports yet. <Link to="/ingest" className="text-forest-400 underline">Import your first file →</Link>
          </div>
        )}
      </div>
    </div>
  )
}
