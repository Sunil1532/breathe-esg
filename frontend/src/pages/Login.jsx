import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Leaf } from 'lucide-react'
import { login } from '../api/client.js'

export default function Login() {
  const [creds, setCreds] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const nav = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const { data } = await login(creds.username, creds.password)
      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)
      nav('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] px-4">
      {/* Background grid */}
      <div className="fixed inset-0 opacity-[0.03]"
        style={{ backgroundImage: 'linear-gradient(var(--accent) 1px, transparent 1px), linear-gradient(90deg, var(--accent) 1px, transparent 1px)', backgroundSize: '40px 40px' }}
      />

      <div className="w-full max-w-sm relative z-10">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-forest-600 flex items-center justify-center mb-4 shadow-lg shadow-forest-900/50">
            <Leaf size={22} className="text-white" />
          </div>
          <h1 className="text-xl font-semibold text-[var(--text)]">Breathe ESG</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1 text-center">Emissions Ingestion Platform</p>
        </div>

        <div className="card space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">Username</label>
            <input className="input" value={creds.username}
              onChange={e => setCreds(p => ({ ...p, username: e.target.value }))}
              placeholder="analyst" autoComplete="username" required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">Password</label>
            <input type="password" className="input" value={creds.password}
              onChange={e => setCreds(p => ({ ...p, password: e.target.value }))}
              placeholder="••••••••" autoComplete="current-password" required
            />
          </div>

          {error && (
            <div className="rounded-lg bg-red-900/30 border border-red-900/50 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}

          <button onClick={handleSubmit} type="button"
            className="btn-primary w-full justify-center py-2.5 text-sm" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </div>

      </div>
    </div>
  )
}
