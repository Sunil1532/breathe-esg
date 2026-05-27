import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ingestFile, getJobs } from '../api/client.js'
import { Upload, CheckCircle, AlertTriangle, XCircle, Clock, FileText, ChevronDown, ChevronUp } from 'lucide-react'

const SOURCES = [
  {
    key: 'sap',
    label: 'SAP Fuel & Procurement',
    scope: 'Scope 1',
    scopeColor: 'text-blue-400',
    description: 'MB51/SE16 semicolon-delimited export with German headers. Movement types 261, 201, 281, 551.',
    acceptedFormat: '.csv,.txt',
    fields: ['MANDT', 'BUKRS', 'WERKS', 'MATNR', 'MAKTX', 'BLDAT', 'MENGE', 'MEINS', 'BWART'],
  },
  {
    key: 'utility',
    label: 'Utility — Electricity',
    scope: 'Scope 2',
    scopeColor: 'text-purple-400',
    description: 'Portal CSV export. Meter ID, billing period, consumption in kWh.',
    acceptedFormat: '.csv',
    fields: ['meter_id', 'site_name', 'period_start', 'period_end', 'consumption_kwh'],
  },
  {
    key: 'travel',
    label: 'Corporate Travel',
    scope: 'Scope 3',
    scopeColor: 'text-emerald-400',
    description: 'Concur-style segment CSV. Air uses haversine distance from airport codes.',
    acceptedFormat: '.csv',
    fields: ['trip_id', 'segment_type', 'origin_code', 'destination_code', 'cabin_class'],
  },
]

const STATUS_CONFIG = {
  COMPLETED:  { icon: CheckCircle,  color: 'text-forest-400',  bg: 'bg-forest-400/10',  label: 'Completed' },
  PARTIAL:    { icon: AlertTriangle,color: 'text-yellow-400',  bg: 'bg-yellow-400/10',  label: 'Partial'   },
  FAILED:     { icon: XCircle,      color: 'text-red-400',     bg: 'bg-red-400/10',     label: 'Failed'    },
  PROCESSING: { icon: Clock,        color: 'text-blue-400',    bg: 'bg-blue-400/10',    label: 'Processing'},
}

function UploadZone({ source, onUploadSuccess }) {
  const [dragOver, setDragOver] = useState(false)
  const [result, setResult] = useState(null)
  const inputRef = useRef()
  const qc = useQueryClient()

  const { mutate, isPending } = useMutation({
    mutationFn: (file) => ingestFile(source.key, file),
    onSuccess: (res) => {
      setResult({ ok: true, data: res.data })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      onUploadSuccess?.()
    },
    onError: (err) => {
      setResult({ ok: false, msg: err.response?.data?.detail || 'Upload failed.' })
    },
  })

  const handleFile = (file) => { if (!file) return; setResult(null); mutate(file) }
  const onDrop = (e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]) }

  return (
    <div className="card space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <h3 className="font-semibold text-[var(--text)] text-sm">{source.label}</h3>
          <span className={`text-[10px] font-bold tracking-widest uppercase ${source.scopeColor}`}>
            {source.scope}
          </span>
        </div>
        <p className="text-xs text-[var(--text-muted)] leading-relaxed">{source.description}</p>
      </div>

      {/* Expected fields — wraps on small screens */}
      <div className="flex flex-wrap gap-1">
        {source.fields.map(f => (
          <code key={f} className="text-[10px] px-1.5 py-0.5 bg-[var(--bg)] border border-[var(--border)] rounded text-[var(--text-muted)] font-mono">
            {f}
          </code>
        ))}
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !isPending && inputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-xl p-6 sm:p-8 text-center cursor-pointer transition-all
          ${dragOver ? 'border-forest-400 bg-forest-400/5' : 'border-[var(--border)] hover:border-forest-400/50 hover:bg-[var(--bg)]'}
          ${isPending ? 'opacity-60 cursor-not-allowed' : ''}
        `}
      >
        <input ref={inputRef} type="file" accept={source.acceptedFormat} className="hidden"
          onChange={(e) => handleFile(e.target.files[0])} />
        {isPending ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-2 border-forest-400 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-[var(--text-muted)]">Parsing and normalizing…</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload size={20} className="text-[var(--text-muted)]" />
            <p className="text-xs text-[var(--text-muted)]">
              Drop <span className="font-mono">{source.acceptedFormat}</span> here or <span className="text-forest-400">tap to browse</span>
            </p>
          </div>
        )}
      </div>

      {result && (
        result.ok ? (
          <div className="rounded-lg bg-forest-400/10 border border-forest-400/20 p-3 space-y-1">
            <div className="flex items-center gap-2 text-forest-400 text-xs font-semibold">
              <CheckCircle size={13} /> Ingested successfully
            </div>
            <div className="text-xs text-[var(--text-muted)] flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
              <span>{result.data.total_rows} rows parsed</span>
              <span>{result.data.success_rows} ok</span>
              <span>{result.data.flagged_rows} flagged</span>
              {result.data.error_rows > 0 && <span className="text-red-400">{result.data.error_rows} errors</span>}
            </div>
          </div>
        ) : (
          <div className="rounded-lg bg-red-400/10 border border-red-400/20 p-3 text-xs text-red-400">{result.msg}</div>
        )
      )}
    </div>
  )
}

function JobRow({ job }) {
  const [open, setOpen] = useState(false)
  const cfg = STATUS_CONFIG[job.status] || STATUS_CONFIG.PROCESSING
  const Icon = cfg.icon

  return (
    <div className="border-b border-[var(--border)] last:border-0">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 py-2.5 px-3 hover:bg-[var(--bg)] transition-colors text-left">
        <div className={`w-6 h-6 rounded flex items-center justify-center shrink-0 ${cfg.bg}`}>
          <Icon size={12} className={cfg.color} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-medium text-[var(--text)] truncate max-w-[140px] sm:max-w-xs">{job.file_name}</span>
            <span className="text-[10px] text-[var(--text-muted)] shrink-0">{job.source_type_display}</span>
          </div>
          <div className="text-[10px] text-[var(--text-muted)] mt-0.5">
            {job.success_rows}/{job.total_rows} rows · {job.flagged_rows} flagged · {new Date(job.created_at).toLocaleString()}
          </div>
        </div>
        {open ? <ChevronUp size={13} className="text-[var(--text-muted)] shrink-0" /> : <ChevronDown size={13} className="text-[var(--text-muted)] shrink-0" />}
      </button>

      {open && (job.parse_errors?.length > 0 || job.parse_warnings?.length > 0) && (
        <div className="px-3 pb-3 space-y-2">
          {job.parse_errors?.length > 0 && (
            <div>
              <div className="text-[10px] font-semibold text-red-400 mb-1">Errors ({job.parse_errors.length})</div>
              <div className="space-y-0.5 max-h-28 overflow-auto">
                {job.parse_errors.slice(0, 10).map((e, i) => (
                  <div key={i} className="text-[10px] text-[var(--text-muted)] font-mono break-all">Row {e.row}: {e.message}</div>
                ))}
              </div>
            </div>
          )}
          {job.parse_warnings?.length > 0 && (
            <div>
              <div className="text-[10px] font-semibold text-yellow-400 mb-1">Warnings ({job.parse_warnings.length})</div>
              <div className="space-y-0.5 max-h-24 overflow-auto">
                {job.parse_warnings.slice(0, 8).map((w, i) => (
                  <div key={i} className="text-[10px] text-[var(--text-muted)] font-mono break-all">Row {w.row}: {w.message}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Ingest() {
  const qc = useQueryClient()
  const { data: jobsData } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => getJobs(),
    refetchInterval: 5000,
  })
  const jobs = jobsData?.data?.results || jobsData?.data || []

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 sm:space-y-8 max-w-6xl mx-auto">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold text-[var(--text)]">Data Ingestion</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Upload files from each source. Rows are parsed, normalized to CO₂e, and queued for review.
        </p>
      </div>

      {/* Upload zones — stack on mobile, 3 cols on large */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {SOURCES.map(source => (
          <UploadZone key={source.key} source={source}
            onUploadSuccess={() => qc.invalidateQueries({ queryKey: ['jobs'] })} />
        ))}
      </div>

      {/* Job history */}
      <div>
        <h2 className="text-sm font-semibold text-[var(--text)] mb-3 flex items-center gap-2">
          <FileText size={14} /> Import History
        </h2>
        <div className="card p-0 overflow-hidden">
          {jobs.length === 0 ? (
            <div className="p-8 text-center text-xs text-[var(--text-muted)]">
              No imports yet. Upload a file above to get started.
            </div>
          ) : (
            jobs.map(job => <JobRow key={job.id} job={job} />)
          )}
        </div>
      </div>
    </div>
  )
}
