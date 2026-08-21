import { useState, useEffect } from 'react'
import { CheckCircle, Filter, AlertTriangle, RefreshCw } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../api/client'
import { useNodeContext } from '../NodeContext'
import { formatDistanceToNow, fromUnixTime } from 'date-fns'

const SEV_COLOR  = { LOW: 'var(--sev-low)', MEDIUM: 'var(--sev-medium)', HIGH: 'var(--sev-high)', CRITICAL: 'var(--sev-critical)' }
const SEVERITIES = ['', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

export default function Alerts() {
  const { selectedNodeId } = useNodeContext()
  const [alerts, setAlerts]  = useState([])
  const [total, setTotal]    = useState(0)
  const [loading, setLoading]  = useState(true)
  const [severity, setSeverity] = useState('')
  const [resolved, setResolved] = useState(false)
  const [page, setPage]       = useState(0)
  const PER_PAGE = 30

  async function load() {
    setLoading(true)
    try {
      const d = await api.alerts({
        node_id: selectedNodeId || undefined,
        severity: severity || undefined,
        resolved: resolved,
        limit: PER_PAGE,
        offset: page * PER_PAGE,
      })
      setAlerts(d.alerts); setTotal(d.total)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [severity, resolved, page, selectedNodeId])

  async function resolve(id) {
    await api.resolveAlert(id)
    load()
  }

  async function resolveAll() {
    await api.resolveAllAlerts()
    load()
  }

  return (
    <Layout
      title="Alerts"
      subtitle={`${total} ${resolved ? 'resolved' : 'open'} alerts`}
      actions={
        !resolved && alerts.length > 0 && (
          <button className="btn btn-ghost btn-sm" onClick={resolveAll}>
            <CheckCircle size={14} /> Resolve All
          </button>
        )
      }
    >
      <div className="filter-bar">
        <select className="input" value={severity} onChange={e => { setSeverity(e.target.value); setPage(0) }}>
          {SEVERITIES.map(s => <option key={s} value={s}>{s || 'All Severities'}</option>)}
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 13 }}>
          <input type="checkbox" checked={resolved} onChange={e => { setResolved(e.target.checked); setPage(0) }} />
          Show resolved
        </label>
        <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCw size={13} /></button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading
          ? <div className="spinner">Loading...</div>
          : alerts.length === 0
            ? (
              <div className="empty-state" style={{ padding: '60px 20px' }}>
                <div className="empty-state-icon">✅</div>
                <div className="empty-state-text">No alerts {resolved ? 'resolved' : 'open'}!</div>
              </div>
            )
            : alerts.map(a => (
              <div key={a.id} className="alert-row">
                <div className="alert-severity-bar" style={{ background: SEV_COLOR[a.severity] || '#666' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                    <span className={`badge badge-${a.severity?.toLowerCase()}`}>{a.severity}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
                      {a.alert_type}
                    </span>
                  </div>
                  <div className="alert-desc">{a.description}</div>
                  <div className="alert-meta">
                    {a.username && <><strong>{a.username}</strong> · </>}
                    {formatDistanceToNow(fromUnixTime(a.timestamp), { addSuffix: true })}
                    {a.resolved ? ' · ✓ Resolved' : ''}
                  </div>
                </div>
                {!a.resolved && (
                  <button className="btn btn-ghost btn-sm" onClick={() => resolve(a.id)}>
                    <CheckCircle size={13} /> Resolve
                  </button>
                )}
              </div>
            ))
        }
      </div>

      {total > PER_PAGE && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
          <button className="btn btn-ghost btn-sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
          <span style={{ padding: '6px 12px', color: 'var(--text-secondary)', fontSize: 13 }}>
            Page {page + 1} of {Math.ceil(total / PER_PAGE)}
          </span>
          <button className="btn btn-ghost btn-sm" disabled={(page + 1) * PER_PAGE >= total} onClick={() => setPage(p => p + 1)}>Next →</button>
        </div>
      )}
    </Layout>
  )
}
