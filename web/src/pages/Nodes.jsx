import { useState, useEffect } from 'react'
import { Server, Activity, RefreshCw, Plus, Edit2, Trash2, Copy, Check } from 'lucide-react'
import Layout from '../components/Layout'
import { apiGet, apiPut, apiDelete, getStoredUser } from '../api/client'
import { formatDistanceToNow, fromUnixTime } from 'date-fns'

export default function Nodes() {
  const [nodes, setNodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(Date.now())
  const user = getStoredUser()
  const isAdmin = user && user.is_admin

  // Modals state
  const [showInstallModal, setShowInstallModal] = useState(false)
  const [installTab, setInstallTab] = useState('docker')
  const [apiUrl, setApiUrl] = useState(window.location.origin)
  const [copied, setCopied] = useState(false)

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

  function handleOpenInstall() {
    setApiUrl(window.location.origin)
    setShowInstallModal(true)
  }

  function handleCopy() {
    const text = `curl -sL "${apiUrl}/api/nodes/install/script?mode=${installTab}&api_url=${encodeURIComponent(apiUrl)}" | sudo bash`
    navigator.clipboard.writeText(text)
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
          <button className="btn btn-primary btn-sm" onClick={handleOpenInstall}>
            <Plus size={14} /> Install Agent
          </button>
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
          <div className="modal-content" style={{ maxWidth: '700px' }}>
            <h3 style={{ margin: '0 0 1rem 0' }}>Install Agent</h3>
            
            <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid var(--glass-border)', marginBottom: '1rem' }}>
              <button 
                className={`btn btn-ghost ${installTab === 'docker' ? 'active' : ''}`} 
                style={{ borderRadius: '0', borderBottom: installTab === 'docker' ? '2px solid var(--accent)' : 'none', color: installTab === 'docker' ? 'var(--accent)' : 'var(--text-secondary)' }}
                onClick={() => setInstallTab('docker')}
              >
                Docker Compose (Recommended)
              </button>
              <button 
                className={`btn btn-ghost ${installTab === 'native' ? 'active' : ''}`} 
                style={{ borderRadius: '0', borderBottom: installTab === 'native' ? '2px solid var(--accent)' : 'none', color: installTab === 'native' ? 'var(--accent)' : 'var(--text-secondary)' }}
                onClick={() => setInstallTab('native')}
              >
                Native Linux (Systemd)
              </button>
            </div>

            <p style={{ color: 'var(--text-secondary)', marginBottom: '0.5rem', fontWeight: 600 }}>
              Central API URL:
            </p>
            <input 
              type="text" 
              className="input input-full" 
              value={apiUrl}
              onChange={e => setApiUrl(e.target.value)}
              style={{ marginBottom: '1.5rem', maxWidth: '300px' }}
              placeholder="e.g. http://192.168.1.100:7432"
            />

            <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              To install and start the agent on a new server, simply run this command as root or with sudo:
            </p>

            <div style={{ position: 'relative', marginBottom: '1.5rem' }}>
              <pre style={{ 
                background: 'rgba(0,0,0,0.4)', 
                padding: '1rem', 
                borderRadius: '8px', 
                overflowX: 'auto',
                fontSize: '0.9rem',
                border: '1px solid var(--glass-border)'
              }}>
                <code style={{ fontFamily: "'JetBrains Mono', monospace", color: '#38bdf8' }}>
                  curl -sL "{apiUrl}/api/nodes/install/script?mode={installTab}&api_url={encodeURIComponent(apiUrl)}" | sudo bash
                </code>
              </pre>
              <button 
                onClick={handleCopy}
                className="btn btn-sm btn-ghost" 
                style={{ position: 'absolute', top: '8px', right: '8px' }}
              >
                {copied ? <Check size={14} color="var(--success)" /> : <Copy size={14} />} 
                {copied ? ' Copied!' : ' Copy'}
              </button>
            </div>
            
            <div style={{ background: 'var(--bg-surface)', padding: '16px', borderRadius: '8px', border: '1px solid var(--glass-border)', fontSize: '13px', color: 'var(--text-secondary)' }}>
              <h4 style={{ color: 'var(--text-primary)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Activity size={14} className="text-accent" /> What this script does
              </h4>
              <ul style={{ paddingLeft: '20px', margin: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <li>Downloads the latest agent collector zip from this server.</li>
                {installTab === 'docker' ? (
                  <li>Builds and starts the <code>auditvisual-collector</code> docker container.</li>
                ) : (
                  <li>Extracts the collector and installs it as a native <code>auditvisual-collector</code> systemd service.</li>
                )}
                <li>Automatically points the agent to communicate with <strong>{apiUrl}</strong>.</li>
              </ul>
              
              <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--glass-border)' }}>
                <strong><Server size={12} style={{ display: 'inline', verticalAlign: 'text-bottom' }} /> Network Requirements:</strong> Ensure this central server is reachable from the agent. If you have a firewall enabled, ensure port <code>7432</code> is open and accessible.
              </div>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '20px' }}>
              <button className="btn btn-primary" onClick={() => setShowInstallModal(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
