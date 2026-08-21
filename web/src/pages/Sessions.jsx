import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Monitor, Wifi, Terminal, Clock } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../api/client'
import { useNodeContext } from '../NodeContext'
import { format, fromUnixTime, formatDuration, intervalToDuration } from 'date-fns'

function fmtTime(ts) {
  if (!ts) return '—'
  try { return format(fromUnixTime(ts), 'MMM dd HH:mm:ss') }
  catch { return '—' }
}

function fmtDuration(secs) {
  if (!secs || secs < 0) return '—'
  const d = intervalToDuration({ start: 0, end: secs * 1000 })
  if (d.hours > 0) return `${d.hours}h ${d.minutes}m`
  if (d.minutes > 0) return `${d.minutes}m ${d.seconds}s`
  return `${d.seconds}s`
}

export default function Sessions() {
  const { selectedNodeId } = useNodeContext()
  const [sessions, setSessions] = useState([])
  const [total, setTotal]       = useState(0)
  const [loading, setLoading]   = useState(true)
  const [username, setUsername] = useState('')
  const [page, setPage]         = useState(0)
  const PER_PAGE = 25
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    api.sessions({ node_id: selectedNodeId || undefined, username: username || undefined, limit: PER_PAGE, offset: page * PER_PAGE })
      .then(d => { setSessions(d.sessions); setTotal(d.total) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [username, page, selectedNodeId])

  return (
    <Layout title="Sessions" subtitle={`${total} total sessions`}>
      <div className="filter-bar">
        <input
          className="input"
          placeholder="Filter by username..."
          value={username}
          onChange={e => { setUsername(e.target.value); setPage(0) }}
          style={{ width: 220 }}
        />
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          {total} results
        </span>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th><Monitor size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />User</th>
              <th><Wifi size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />IP Address</th>
              <th>Terminal</th>
              <th><Clock size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />Login Time</th>
              <th>Duration</th>
              <th><Terminal size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />Commands</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>Loading...</td></tr>
              : sessions.length === 0
                ? <tr><td colSpan={7}><div className="empty-state"><div className="empty-state-icon">📋</div><div className="empty-state-text">No sessions found</div></div></td></tr>
                : sessions.map(s => (
                  <tr key={s.id} onClick={() => navigate(`/sessions/${s.id}`)}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{
                          width: 32, height: 32, background: 'rgba(59, 130, 246, 0.1)',
                          borderRadius: '50%', display: 'flex', alignItems: 'center',
                          justifyContent: 'center', fontSize: 13, fontWeight: 700, color: 'var(--accent)',
                          border: '1px solid rgba(59, 130, 246, 0.2)'
                        }}>
                          {s.username[0]?.toUpperCase()}
                        </div>
                        <strong>{s.username}</strong>
                      </div>
                    </td>
                    <td>{s.ip ? <span className="tag">{s.ip}</span> : <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                    <td><span className="tag">{s.terminal || '?'}</span></td>
                    <td style={{ fontFamily: 'JetBrains Mono', fontSize: 12 }}>{fmtTime(s.login_time)}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{fmtDuration(s.duration)}</td>
                    <td>
                      <span style={{
                        background: 'rgba(59, 130, 246, 0.15)', color: 'var(--accent)',
                        padding: '4px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                        border: '1px solid rgba(59, 130, 246, 0.2)'
                      }}>
                        {s.command_count ?? 0}
                      </span>
                    </td>
                    <td>
                      {s.logout_time
                        ? <span className="badge badge-neutral">Closed</span>
                        : <span className="badge badge-success">● Active</span>
                      }
                    </td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </div>

      {/* Pagination */}
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
