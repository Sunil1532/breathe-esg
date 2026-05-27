import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Upload, ClipboardCheck, LogOut, Leaf, Menu, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { getMe } from '../api/client.js'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/ingest',    icon: Upload,          label: 'Ingest Data' },
  { to: '/review',    icon: ClipboardCheck,  label: 'Review' },
]

export default function Layout() {
  const nav = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { data } = useQuery({ queryKey: ['me'], queryFn: getMe, select: r => r.data })

  function logout() {
    localStorage.clear()
    nav('/login')
  }

  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="flex items-center justify-between px-5 h-16 border-b border-[var(--border)] shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-forest-600 flex items-center justify-center">
            <Leaf size={14} className="text-white" />
          </div>
          <span className="font-semibold text-[var(--text)] tracking-tight">Breathe ESG</span>
        </div>
        {/* Close button — mobile only */}
        <button
          className="lg:hidden text-[var(--text-muted)] hover:text-[var(--text)] p-1"
          onClick={() => setSidebarOpen(false)}
        >
          <X size={18} />
        </button>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                isActive
                  ? 'bg-forest-600/20 text-forest-400 font-medium'
                  : 'text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--bg-surface)]'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User footer */}
      <div className="border-t border-[var(--border)] p-3 shrink-0">
        <div className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg mb-1">
          <div className="w-7 h-7 rounded-full bg-forest-700 flex items-center justify-center text-xs font-semibold text-forest-200 shrink-0">
            {data?.username?.[0]?.toUpperCase() || '?'}
          </div>
          <div className="min-w-0">
            <div className="text-xs font-medium text-[var(--text)] truncate">{data?.username || '—'}</div>
            <div className="text-[10px] text-[var(--text-muted)] truncate">{data?.organization?.name || ''}</div>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-[var(--text-muted)] hover:text-red-400 hover:bg-red-900/10 transition-colors"
        >
          <LogOut size={13} />
          Sign out
        </button>
      </div>
    </>
  )

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg)]">

      {/* ── Desktop sidebar (always visible ≥ lg) ── */}
      <aside className="hidden lg:flex w-56 flex-col shrink-0 border-r border-[var(--border)] bg-[var(--bg-card)]">
        <SidebarContent />
      </aside>

      {/* ── Mobile sidebar overlay ── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Mobile sidebar drawer ── */}
      <aside
        className={`
          fixed top-0 left-0 z-50 h-full w-64 flex flex-col
          border-r border-[var(--border)] bg-[var(--bg-card)]
          transform transition-transform duration-300 ease-in-out lg:hidden
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <SidebarContent />
      </aside>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Mobile top bar */}
        <header className="lg:hidden flex items-center gap-3 px-4 h-14 border-b border-[var(--border)] bg-[var(--bg-card)] shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-[var(--text-muted)] hover:text-[var(--text)] p-1"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-md bg-forest-600 flex items-center justify-center">
              <Leaf size={10} className="text-white" />
            </div>
            <span className="font-semibold text-sm text-[var(--text)]">Breathe ESG</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
