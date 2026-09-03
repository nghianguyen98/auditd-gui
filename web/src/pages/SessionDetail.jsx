import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Terminal, FileText, Shield } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../api/client'
import { format, fromUnixTime } from 'date-fns'

const DANGER_CMDS = new Set(['rm', 'sudo', 'su', 'chmod', 'chown', 'dd', 'wget', 'curl', 'nc', 'ncat', 'bash', 'python', 'python3'])

function fmtTime(ts) {
  if (!ts) return ''
  try { return format(fromUnixTime(ts), 'HH:mm:ss') }
  catch { return '' }
}

function CommandLine({ cmd }) {
  const isRoot = cmd.effective_uid === 0
  const isDanger = DANGER_CMDS.has(cmd.command)
  return (
    <div className={`cmd-line ${isDanger ? 'cmd-danger' : ''}`}>
      <span className={`cmd-prompt ${isRoot ? 'root' : 'user'}`}>
        {isRoot ? `${cmd.username} ➔ root#` : `${cmd.username}$`}
      </span>
      <div style={{ flex: 1 }}>
        <span className="cmd-text" style={{ color: isDanger ? '#fca5a5' : undefined }}>
          {cmd.command}
        </span>
        {cmd.args?.length > 0 && (
          <span className="cmd-text cmd-args">{' '}{cmd.args.join(' ')}</span>
        )}
        {cmd.effective_uid === 0 && cmd.username && (
          <span className="badge badge-high" style={{ marginLeft: 8, verticalAlign: 'middle', fontSize: 10 }}>
            <Shield size={9} /> sudo
          </span>
        )}
      </div>
      <span className="cmd-time">{fmtTime(cmd.timestamp)}</span>
    </div>
  )
}

export default function SessionDetail() {
  const { id }   = useParams()
  const navigate = useNavigate()
  const [session, setSession]   = useState(null)
  const [commands, setCommands] = useState([])
  const [files, setFiles]       = useState([])
  const [tab, setTab]           = useState('commands')
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    Promise.all([
      api.session(id),
      api.sessionCommands(id, { limit: 500 }),
      api.sessionFiles(id),
    ]).then(([s, c, f]) => {
      setSession(s); 
      setCommands([...c].sort((a, b) => b.timestamp - a.timestamp)); 
      setFiles([...f].sort((a, b) => b.timestamp - a.timestamp));
    }).catch(console.error)
    .finally(() => setLoading(false))
  }, [id])

  if (loading) return <Layout title="Session Detail"><div className="spinner">Loading...</div></Layout>
  if (!session) return <Layout title="Session Detail"><div className="empty-state">Session not found</div></Layout>

  const dangerCount = commands.filter(c => DANGER_CMDS.has(c.command)).length

  return (
    <Layout
      title={`Session: ${session.username}`}
      actions={
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/sessions')}>
          <ArrowLeft size={14} /> Back
        </button>
      }
    >
      {/* Session Meta */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24 }}>
          {[
            ['User (AUID)', `${session.username} (auid=${session.auid})`],
            ['IP Address', session.ip || '—'],
            ['Terminal', session.terminal || '—'],
            ['Login', session.login_time ? format(fromUnixTime(session.login_time), 'MMM dd yyyy HH:mm:ss') : '—'],
            ['Logout', session.logout_time ? format(fromUnixTime(session.logout_time), 'MMM dd yyyy HH:mm:ss') : 'Active'],
            ['Commands', commands.length],
            ['Dangerous Cmds', dangerCount],
            ['File Events', files.length],
          ].map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>{k}</div>
              <div style={{ fontSize: 14, fontWeight: 500, fontFamily: k === 'User (AUID)' ? 'JetBrains Mono' : undefined }}>
                {String(v)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {[
          { key: 'commands', label: `Commands (${commands.length})`, icon: Terminal },
          { key: 'files',    label: `File Access (${files.length})`, icon: FileText },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            className={`btn ${tab === key ? 'btn-primary' : 'btn-ghost'} btn-sm`}
            onClick={() => setTab(key)}
          >
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>

      {tab === 'commands' && (
        <div className="card" style={{ padding: '8px 16px' }}>
          {commands.length === 0
            ? <div className="empty-state"><div className="empty-state-text">No commands recorded</div></div>
            : commands.map(c => <CommandLine key={c.id} cmd={c} />)
          }
        </div>
      )}

      {tab === 'files' && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Action</th>
                <th>Path</th>
                <th>Tag</th>
              </tr>
            </thead>
            <tbody>
              {files.length === 0
                ? <tr><td colSpan={4}><div className="empty-state"><div className="empty-state-text">No file events</div></div></td></tr>
                : files.map(f => (
                  <tr key={f.id}>
                    <td style={{ fontFamily: 'JetBrains Mono', fontSize: 12 }}>{fmtTime(f.timestamp)}</td>
                    <td><span className="badge badge-medium">{f.action}</span></td>
                    <td style={{ fontFamily: 'JetBrains Mono', fontSize: 12, color: '#7dd3fc' }}>{f.path}</td>
                    <td><span className="badge badge-neutral">{f.key}</span></td>
                  </tr>
                ))
              }
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  )
}
