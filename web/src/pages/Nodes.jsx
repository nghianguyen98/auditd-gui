import { useState, useEffect } from 'react'
import { Server, Activity, RefreshCw, Plus, Edit2, Trash2, Copy, Check, Terminal, ShieldAlert } from 'lucide-react'
import Layout from '../components/Layout'
import { apiGet, apiPut, apiDelete, apiPost, getStoredUser } from '../api/client'
import { formatDistanceToNow, fromUnixTime } from 'date-fns'

export default function Nodes() {
  const [nodes, setNodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(Date.now())
  const user = getStoredUser()
  const isAdmin = user && user.is_admin

  // Modals state
  const [showInstallModal, setShowInstallModal] = useState(false)
  const [showUninstallModal, setShowUninstallModal] = useState(false)
  const [installTab, setInstallTab] = useState('docker')
  const [apiUrl, setApiUrl] = useState(window.location.origin)
  const [copied, setCopied] = useState(false)
  const [installToken, setInstallToken] = useState(null)
  const [generatingToken, setGeneratingToken] = useState(false)

  const [editNode, setEditNode] = useState(null)
  const [editForm, setEditForm] = useState({ alias: '', description: '' })
  const [deleteNode, setDeleteNode] = useState(null)
  
  async function load() {
    setLoading(true)
    try {
      const data = await apiGet('/nodes')
      setNodes(data)
      setLastRefresh(Date.now())
    } catch (err) {
      console.error("Failed to load nodes", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  async function handleOpenInstall() {
    setApiUrl(window.location.origin)
    setShowInstallModal(true)
    setGeneratingToken(true)
    try {
      // apiPost requires a body, we can just pass an empty object or change apiPost to allow undefined. 
      // Let's use apiPost('/nodes/generate-token', {})
      const res = await apiPost('/nodes/generate-token', {})
      setInstallToken(res.token)
    } catch (err) {
      alert("Failed to generate secure token: " + err.message)
    } finally {
      setGeneratingToken(false)
    }
  }

  function handleCopyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text)
        .then(() => showCopied())
        .catch(err => fallbackCopyTextToClipboard(text))
    } else {
      fallbackCopyTextToClipboard(text)
    }
  }

  function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement("textarea")
    textArea.value = text
    
    // Avoid scrolling to bottom
    textArea.style.top = "0"
    textArea.style.left = "0"
    textArea.style.position = "fixed"

    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()

    try {
      document.execCommand('copy')
      showCopied()
    } catch (err) {
      console.error('Fallback: Oops, unable to copy', err)
      alert('Failed to copy. Please copy the command manually.')
    }

    document.body.removeChild(textArea)
  }

  function showCopied() {
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function handleSaveEdit(e) {
    e.preventDefault()
    try {
      await apiPut(`/nodes/${editNode.id}`, editForm)
      setEditNode(null)
      load()
    } catch (err) {
      alert("Failed to update node: " + err.message)
    }
  }

  async function handleConfirmDelete() {
    try {
      await apiDelete(`/nodes/${deleteNode.id}`)
      setDeleteNode(null)
      load()
    } catch (err) {
      alert("Failed to delete node: " + err.message)
    }
  }

  return (
    <Layout title="Nodes" subtitle="Manage connected agent servers" actions={
      <div style={{ display: 'flex', gap: '8px' }}>
        <button className="btn btn-ghost btn-sm" onClick={load}>
          <RefreshCw size={14} /> Refresh
        </button>
        {isAdmin && (
          <>
            <button className="btn btn-outline btn-sm" onClick={() => { setApiUrl(window.location.origin); setShowUninstallModal(true); }} style={{ borderColor: 'var(--error)', color: 'var(--error)' }}>
              <Trash2 size={14} /> Uninstall Agent
            </button>
            <button className="btn btn-primary btn-sm" onClick={handleOpenInstall}>
              <Plus size={14} /> Install Agent
            </button>
          </>
        )}
      </div>
    }>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th><Server size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Hostname</th>
                <th>IP Address</th>
                <th>Description</th>
                <th><Activity size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Status</th>
                <th>Last Seen</th>
                {isAdmin && <th style={{ textAlign: 'right' }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {loading && nodes.length === 0
                ? <tr><td colSpan={isAdmin ? 6 : 5} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>Loading...</td></tr>
                : nodes.length === 0
                  ? <tr><td colSpan={isAdmin ? 6 : 5}><div className="empty-state"><div className="empty-state-text">No nodes registered yet.</div></div></td></tr>
                  : nodes.map(n => (
                    <tr key={n.id}>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <strong>{n.alias || n.hostname}</strong>
                          {n.alias && <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{n.hostname}</span>}
                        </div>
                      </td>
                      <td>{n.ip_address ? <span className="tag">{n.ip_address}</span> : <span style={{ color: 'var(--text-muted)' }}>Unknown</span>}</td>
                      <td style={{ color: 'var(--text-secondary)' }}>{n.description || '-'}</td>
                      <td>
                        {n.status === 'online' 
                          ? <span className="badge badge-success">● Online</span> 
                          : <span className="badge badge-neutral">Offline</span>}
                      </td>
                      <td style={{ color: 'var(--text-secondary)' }}>
                        {formatDistanceToNow(fromUnixTime(n.last_seen), { addSuffix: true })}
                      </td>
                      {isAdmin && (
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn btn-ghost btn-sm" style={{ padding: '0 6px', marginRight: '4px' }} onClick={() => {
                            setEditForm({ alias: n.alias || '', description: n.description || '' })
                            setEditNode(n)
                          }}>
                            <Edit2 size={14} />
                          </button>
                          <button className="btn btn-ghost btn-sm" style={{ padding: '0 6px', color: 'var(--danger)' }} onClick={() => setDeleteNode(n)}>
                            <Trash2 size={14} />
                          </button>
                        </td>
                      )}
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>
      </div>

      {/* Edit Modal */}
      {editNode && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '400px' }}>
            <h3 style={{ margin: '0 0 1rem 0' }}>Edit Node</h3>
            <form onSubmit={handleSaveEdit}>
              <div className="form-group">
                <label className="form-label">Alias (Friendly Name)</label>
                <input 
                  type="text" 
                  className="input input-full"
                  value={editForm.alias} 
                  onChange={e => setEditForm({...editForm, alias: e.target.value})} 
                  placeholder={editNode.hostname}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea 
                  className="input input-full"
                  value={editForm.description} 
                  onChange={e => setEditForm({...editForm, description: e.target.value})}
                  rows={3}
                ></textarea>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setEditNode(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Changes</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {deleteNode && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '400px' }}>
            <h3 style={{ margin: '0 0 1rem 0', color: 'var(--danger)' }}>Delete Node</h3>
            <p>Are you sure you want to delete <strong>{deleteNode.alias || deleteNode.hostname}</strong>?</p>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              This will permanently delete all sessions, commands, file events, and alerts associated with this server. This action cannot be undone.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button className="btn btn-ghost" onClick={() => setDeleteNode(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={handleConfirmDelete}>Delete Everything</button>
            </div>
          </div>
        </div>
      )}

      {/* Install Agent Modal */}
      {showInstallModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '650px', padding: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '32px' }}>
              <div className="stat-icon" style={{ width: '48px', height: '48px', background: 'var(--accent-glow)', border: '1px solid rgba(59,130,246,0.3)', flexShrink: 0 }}>
                <Terminal size={24} color="var(--accent)" />
              </div>
              <div>
                <h2 style={{ margin: 0, fontFamily: "'Outfit', sans-serif", fontSize: '24px', letterSpacing: '-0.5px' }}>Deploy Agent</h2>
                <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '4px' }}>Connect a new Linux server to your central dashboard.</div>
              </div>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
              {/* Step 1 */}
              <div>
                <div style={{ fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px' }}>
                  <span className="badge badge-info" style={{ padding: '4px 10px', fontSize: '11px' }}>Step 1</span> 
                  Choose Installation Mode
                </div>
                <div style={{ display: 'flex', gap: '8px', background: 'var(--bg-elevated)', padding: '6px', borderRadius: 'var(--radius)', border: '1px solid var(--glass-border)' }}>
                  <button 
                    className={`btn ${installTab === 'docker' ? 'btn-primary' : 'btn-ghost'}`} 
                    style={{ flex: 1, borderRadius: '8px', border: installTab === 'docker' ? 'none' : '' }}
                    onClick={() => setInstallTab('docker')}
                  >
                    Docker
                  </button>
                  <button 
                    className={`btn ${installTab === 'native' ? 'btn-primary' : 'btn-ghost'}`} 
                    style={{ flex: 1, borderRadius: '8px', border: installTab === 'native' ? 'none' : '' }}
                    onClick={() => setInstallTab('native')}
                  >
                    Native (Standalone)
                  </button>
                  <button 
                    className={`btn ${installTab === 'native-zip' ? 'btn-primary' : 'btn-ghost'}`} 
                    style={{ flex: 1, borderRadius: '8px', border: installTab === 'native-zip' ? 'none' : '' }}
                    onClick={() => setInstallTab('native-zip')}
                  >
                    Native (ZIP)
                  </button>
                </div>
              </div>

              {/* Step 2 */}
              <div>
                <div style={{ fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px' }}>
                  <span className="badge badge-info" style={{ padding: '4px 10px', fontSize: '11px' }}>Step 2</span> 
                  Verify Central API Address
                </div>
                <input 
                  type="text" 
                  className="input input-full" 
                  value={apiUrl}
                  onChange={e => setApiUrl(e.target.value)}
                  style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '14px', padding: '12px 16px' }}
                />
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '8px' }}>
                  The agent will send logs to this address. Ensure port <strong>7432</strong> is accessible from the target server.
                </div>
              </div>

              {/* Step 3 */}
              <div>
                <div style={{ fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px', flexWrap: 'wrap' }}>
                  <span className="badge badge-info" style={{ padding: '4px 10px', fontSize: '11px' }}>Step 3</span> 
                  Run Command on Target Server
                </div>
                <div style={{ 
                  background: '#0f172a', 
                  borderRadius: 'var(--radius)', 
                  border: '1px solid rgba(255,255,255,0.1)',
                  boxShadow: 'inset 0 4px 15px rgba(0,0,0,0.5)',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden'
                }}>
                  <div style={{ padding: '16px 20px', overflowX: 'auto' }}>
                    <code style={{ fontFamily: "'JetBrains Mono', monospace", color: '#38bdf8', fontSize: '13px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                      {generatingToken ? "Generating secure token..." : `curl -sL "${apiUrl}/api/nodes/install/script?mode=${installTab}&api_url=${encodeURIComponent(apiUrl)}&token=${installToken || ''}" | sudo bash`}
                    </code>
                  </div>
                  <div style={{ 
                    borderTop: '1px solid rgba(255,255,255,0.05)', 
                    background: 'rgba(0,0,0,0.2)', 
                    padding: '10px 16px',
                    display: 'flex',
                    justifyContent: 'flex-end'
                  }}>
                    <button 
                      onClick={() => handleCopyText(`curl -sL "${apiUrl}/api/nodes/install/script?mode=${installTab}&api_url=${encodeURIComponent(apiUrl)}&token=${installToken || ''}" | sudo bash`)}
                      className="btn btn-primary btn-sm" 
                      style={{ padding: '6px 16px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', minWidth: '100px', justifyContent: 'center' }}
                    >
                      {copied ? <Check size={14} /> : <Copy size={14} />} 
                      {copied ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Info Box */}
              <div style={{ 
                background: 'var(--accent-glow)', 
                padding: '20px', 
                borderRadius: 'var(--radius-lg)', 
                border: '1px solid rgba(59,130,246,0.3)', 
                display: 'flex', 
                gap: '16px',
                alignItems: 'flex-start'
              }}>
                <ShieldAlert size={24} color="var(--accent)" style={{ flexShrink: 0 }} />
                <div style={{ fontSize: '13.5px', color: 'var(--text-primary)', lineHeight: '1.6' }}>
                  <strong style={{ display: 'block', marginBottom: '6px', fontSize: '15px' }}>Secure Deployment</strong>
                  <p style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>
                    This command securely downloads the collector agent straight from your Central Server. It will automatically generate a secure <code>NODE_API_KEY</code> and establish a private connection. No data ever leaves your infrastructure.
                  </p>
                  
                  <strong style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: 'var(--text-primary)' }}>What this script executes:</strong>
                  <ul style={{ paddingLeft: '20px', margin: 0, color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {installTab === 'docker' && (
                      <>
                        <li><strong>Prerequisites:</strong> Installs <code>auditd</code> (if missing) to enable kernel logging.</li>
                        <li><strong>Configuration:</strong> Creates <code>/opt/auditvisual-agent/docker-compose.yml</code> with your secure token.</li>
                        <li><strong>Isolation:</strong> Mounts host logs as <strong>Read-Only</strong> (<code>:ro</code>) to guarantee system safety.</li>
                        <li><strong>Execution:</strong> Pulls the collector image and starts it securely in the background.</li>
                      </>
                    )}
                    {installTab === 'native' && (
                      <>
                        <li><strong>Prerequisites:</strong> Safely installs <code>auditd</code> and <code>python3</code> (only if missing, strictly no-upgrade).</li>
                        <li><strong>Deployment:</strong> Embeds agent source code directly into <code>/opt/auditvisual-agent</code> (0 downloads).</li>
                        <li><strong>Isolation:</strong> Creates a <code>venv</code> and installs dependencies (<code>watchdog</code>, <code>schedule</code>) without touching system Python.</li>
                        <li><strong>Execution:</strong> Registers a native Systemd service to run the agent continuously.</li>
                      </>
                    )}
                    {installTab === 'native-zip' && (
                      <>
                        <li><strong>Prerequisites:</strong> Safely installs <code>auditd</code>, <code>python3</code>, and <code>unzip</code> (only if missing, strictly no-upgrade).</li>
                        <li><strong>Deployment:</strong> Downloads the collector ZIP from this server and extracts to <code>/opt/auditvisual-agent</code>.</li>
                        <li><strong>Isolation:</strong> Creates a <code>venv</code> and installs dependencies without touching system Python.</li>
                        <li><strong>Execution:</strong> Registers a native Systemd service to run the agent continuously.</li>
                      </>
                    )}
                    <li>Automatically configures the agent to communicate with <strong>{apiUrl}</strong>.</li>
                    {(installTab === 'native' || installTab === 'native-zip') && (
                      <li style={{ marginTop: '8px' }}>
                        <strong style={{ color: 'var(--success)' }}>✔ Zero-Impact Guarantee:</strong> Never upgrades system packages, uses isolated <code>venv</code>, and enforces strict CPU (30%) & RAM (150MB) limits.
                      </li>
                    )}
                  </ul>
                </div>
              </div>

            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '32px', paddingTop: '20px', borderTop: '1px solid var(--glass-border)' }}>
              <button className="btn btn-ghost" style={{ padding: '10px 24px' }} onClick={() => setShowInstallModal(false)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Uninstall Agent Modal */}
      {showUninstallModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '650px', padding: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '32px' }}>
              <div className="stat-icon" style={{ width: '48px', height: '48px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', flexShrink: 0 }}>
                <Trash2 size={24} color="var(--error)" />
              </div>
              <div>
                <h2 style={{ margin: 0, fontFamily: "'Outfit', sans-serif", fontSize: '24px', letterSpacing: '-0.5px' }}>Uninstall Agent</h2>
                <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '4px' }}>Completely remove the agent from a target server.</div>
              </div>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px', flexWrap: 'wrap' }}>
                  Run Uninstallation Command
                </div>
                <div style={{ 
                  background: '#0f172a', 
                  borderRadius: 'var(--radius)', 
                  border: '1px solid rgba(255,255,255,0.1)',
                  boxShadow: 'inset 0 4px 15px rgba(0,0,0,0.5)',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden'
                }}>
                  <div style={{ padding: '16px 20px', overflowX: 'auto' }}>
                    <code style={{ fontFamily: "'JetBrains Mono', monospace", color: '#ef4444', fontSize: '13px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                      {`curl -sL "${apiUrl}/api/nodes/uninstall/script" | sudo bash`}
                    </code>
                  </div>
                  <div style={{ 
                    borderTop: '1px solid rgba(255,255,255,0.05)', 
                    background: 'rgba(0,0,0,0.2)', 
                    padding: '10px 16px',
                    display: 'flex',
                    justifyContent: 'flex-end'
                  }}>
                    <button 
                      onClick={() => handleCopyText(`curl -sL "${apiUrl}/api/nodes/uninstall/script" | sudo bash`)}
                      className="btn btn-primary btn-sm" 
                      style={{ padding: '6px 16px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', minWidth: '100px', justifyContent: 'center', background: 'var(--error)', borderColor: 'var(--error)', color: '#fff' }}
                    >
                      {copied ? <Check size={14} /> : <Copy size={14} />} 
                      {copied ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Info Box */}
              <div style={{ 
                background: 'rgba(239, 68, 68, 0.05)', 
                padding: '20px', 
                borderRadius: 'var(--radius-lg)', 
                border: '1px solid rgba(239, 68, 68, 0.2)', 
                display: 'flex', 
                gap: '16px',
                alignItems: 'flex-start'
              }}>
                <ShieldAlert size={24} color="var(--error)" style={{ flexShrink: 0 }} />
                <div style={{ fontSize: '13.5px', color: 'var(--text-primary)', lineHeight: '1.6' }}>
                  <strong style={{ display: 'block', marginBottom: '6px', fontSize: '15px' }}>Clean Removal Guarantee</strong>
                  <p style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>
                    This script safely stops all agent processes, cleans up Docker containers or Systemd services, removes installed files from <code>/opt/auditvisual-agent</code>, and clears custom Auditd rules.
                  </p>
                  <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                    Your underlying system and auditd daemon will remain perfectly intact.
                  </p>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '32px' }}>
              <button className="btn btn-ghost" onClick={() => setShowUninstallModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
