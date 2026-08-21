import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import { api } from '../api/client'

export default function Users() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.topUsers(30).then(setUsers).catch(console.error).finally(() => setLoading(false))
  }, [])

  const max = users[0]?.commands || 1

  return (
    <Layout title="Users" subtitle="Active Linux users on this host">
      {loading
        ? <div className="spinner">Loading...</div>
        : users.length === 0
          ? <div className="empty-state"><div className="empty-state-icon">👥</div><div className="empty-state-text">No user activity recorded yet</div></div>
          : (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Username</th>
                    <th>Sessions (30d)</th>
                    <th>Commands (30d)</th>
                    <th>Activity</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u, i) => (
                    <tr key={u.username} onClick={() => navigate(`/sessions?username=${u.username}`)}>
                      <td style={{ color: 'var(--text-muted)', width: 40 }}>{i + 1}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div style={{
                            width: 32, height: 32, background: 'rgba(59, 130, 246, 0.1)',
                            borderRadius: '50%', display: 'flex', alignItems: 'center',
                            justifyContent: 'center', fontSize: 13, fontWeight: 700, color: 'var(--accent)',
                            border: '1px solid rgba(59, 130, 246, 0.2)'
                          }}>
                            {u.username[0]?.toUpperCase()}
                          </div>
                          <strong style={{ fontSize: 14 }}>{u.username}</strong>
                        </div>
                      </td>
                      <td>{u.sessions}</td>
                      <td>
                        <strong style={{ color: 'var(--accent)' }}>{u.commands}</strong>
                      </td>
                      <td style={{ width: 180 }}>
                        <div style={{
                          height: 6, borderRadius: 3, background: 'var(--bg-elevated)', overflow: 'hidden'
                        }}>
                          <div style={{
                            height: '100%',
                            width: `${Math.round((u.commands / max) * 100)}%`,
                            background: 'var(--accent)',
                            borderRadius: 3,
                          }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
      }
    </Layout>
  )
}
