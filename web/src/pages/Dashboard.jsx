import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { Monitor, Terminal, AlertTriangle, Users, RefreshCw } from 'lucide-react'
import Layout from '../components/Layout'
import { api, apiGet } from '../api/client'
import { useNodeContext } from '../NodeContext'
import { formatDistanceToNow, fromUnixTime } from 'date-fns'

const SEV_COLOR = { LOW: 'var(--sev-low)', MEDIUM: 'var(--sev-medium)', HIGH: 'var(--sev-high)', CRITICAL: 'var(--sev-critical)' }

function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className="stat-card">
      <div className="stat-header">
        <div className="stat-icon" style={{ color }}>
          <Icon size={20} />
        </div>
        <div className="stat-label">{label}</div>
      </div>
      <div className="stat-value">{value ?? '—'}</div>
    </div>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-elevated)', border: '1px solid var(--glass-border)',
      backdropFilter: 'var(--blur-md)', padding: '12px 16px', borderRadius: '12px', 
      fontSize: 13, boxShadow: 'var(--shadow-glass)'
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
      <div style={{ color: '#7dd3fc', fontWeight: 600 }}>{payload[0].value} commands</div>
    </div>
  )
}

export default function Dashboard() {
  const { selectedNodeId } = useNodeContext()
  const [stats, setStats]       = useState(null)
  const [chart, setChart]       = useState([])
  const [topUsers, setTopUsers] = useState([])
  const [alerts, setAlerts]     = useState([])
  const [loading, setLoading]   = useState(true)
  const [lastRefresh, setLastRefresh] = useState(Date.now())
  const navigate = useNavigate()

  const load = useCallback(async () => {
    try {
      const q = selectedNodeId ? `?node_id=${selectedNodeId}` : ''
      const qAmp = selectedNodeId ? `&node_id=${selectedNodeId}` : ''
      const [s, c, u, a] = await Promise.all([
        apiGet(`/dashboard/stats${q}`), 
        apiGet(`/dashboard/activity-chart?hours=24${qAmp}`), 
        apiGet(`/dashboard/top-users?days=7&limit=5${qAmp}`), 
        apiGet(`/dashboard/recent-alerts?limit=6${qAmp}`)
      ])
      setStats(s); setChart(c); setTopUsers(u); setAlerts(a)
      setLastRefresh(Date.now())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [selectedNodeId])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [load])

  if (loading) return (
    <Layout title="Dashboard">
      <div className="spinner">Loading...</div>
    </Layout>
  )

  return (
    <Layout
      title="Dashboard"
      subtitle="Overview of user activity"
      actions={
        <button className="btn btn-ghost btn-sm" onClick={load}>
          <RefreshCw size={14} /> Refresh
        </button>
      }
    >
      {/* Stat Cards */}
      <div className="stats-grid">
        <StatCard label="Sessions Today" value={stats?.sessions_today} icon={Monitor} color="#3b82f6" />
        <StatCard label="Commands Today" value={stats?.commands_today} icon={Terminal} color="#10b981" />
        <StatCard label="Open Alerts"    value={stats?.alerts_open}    icon={AlertTriangle} color="#f59e0b" />
        <StatCard label="Active Sessions" value={stats?.active_sessions} icon={Users} color="#6366f1" />
        <StatCard label="Active Users (7d)" value={stats?.active_users_7d} icon={Users} color="#8b5cf6" />
      </div>

      <div className="grid-2" style={{ marginBottom: 20 }}>
        {/* Activity Chart */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <div className="card-title">
            <span style={{ color: 'var(--accent)' }}>📈</span>
            Command Activity (Last 24h)
            <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="live-dot" /> Live
            </span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chart} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <defs>
                <linearGradient id="cmdGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="hour" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} tickLine={false} />
              <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="commands" stroke="#3b82f6" strokeWidth={2}
                fill="url(#cmdGrad)" dot={false} activeDot={{ r: 4, fill: '#3b82f6' }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid-2">
        {/* Top Users */}
        <div className="card">
          <div className="card-title">👥 Top Users (7 days)</div>
          {topUsers.length === 0
            ? <div className="empty-state"><div className="empty-state-text">No data yet</div></div>
            : topUsers.map((u, i) => (
              <div key={u.username} style={{
                display: 'flex', alignItems: 'center', gap: 16,
                padding: '14px 0', borderBottom: i < topUsers.length-1 ? '1px solid rgba(255,255,255,0.03)' : 'none',
                transition: '0.2s', cursor: 'default'
              }}>
                <div style={{
                  width: 32, height: 32, background: 'rgba(59, 130, 246, 0.1)',
                  borderRadius: '50%', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 13, fontWeight: 700, color: 'var(--accent)',
                  border: '1px solid rgba(59, 130, 246, 0.2)'
                }}>
                  {i + 1}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500 }}>{u.username}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {u.sessions} sessions · {u.commands} commands
                  </div>
                </div>
                <div style={{
                  width: `${Math.round((u.commands / (topUsers[0]?.commands || 1)) * 80)}px`,
                  height: 4, background: 'var(--accent)', borderRadius: 2, minWidth: 4
                }} />
              </div>
            ))
          }
        </div>

        {/* Recent Alerts */}
        <div className="card">
          <div className="card-title">
            🚨 Recent Alerts
            <button className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }}
              onClick={() => navigate('/alerts')}>
              View all
            </button>
          </div>
          {alerts.length === 0
            ? <div className="empty-state"><div className="empty-state-text">No alerts — looking good!</div></div>
            : alerts.map(a => (
              <div key={a.id} className="alert-row" onClick={() => navigate('/alerts')}>
                <div className="alert-severity-bar"
                  style={{ background: SEV_COLOR[a.severity] || '#666' }} />
                <div style={{ flex: 1 }}>
                  <div className="alert-desc">{a.description}</div>
                  <div className="alert-meta">
                    {a.username && <><strong>{a.username}</strong> · </>}
                    {formatDistanceToNow(fromUnixTime(a.timestamp), { addSuffix: true })}
                  </div>
                </div>
                <span className={`badge badge-${a.severity.toLowerCase()}`}>{a.severity}</span>
              </div>
            ))
          }
        </div>
      </div>
    </Layout>
  )
}
