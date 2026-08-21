import { useState, useEffect } from 'react'
import { Save, UserPlus, Trash2 } from 'lucide-react'
import Layout from '../components/Layout'
import { api, getStoredUser } from '../api/client'

function Toggle({ checked, onChange }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      <span className="toggle-slider" />
    </label>
  )
}

export default function Settings() {
  const user = getStoredUser()
  const [settings, setSettings] = useState({})
  const [users, setUsers]       = useState([])
  const [saved, setSaved]       = useState(false)
  const [newUser, setNewUser]   = useState({ username: '', password: '', is_admin: false })
  const [userMsg, setUserMsg]   = useState('')

  useEffect(() => {
    api.getSettings().then(setSettings)
    if (user?.is_admin) api.getUsers().then(setUsers)
  }, [])

  function updateSetting(key, value) {
    setSettings(s => ({ ...s, [key]: String(value) }))
  }

  async function saveSettings() {
    await api.updateSettings(settings)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  async function addUser() {
    if (!newUser.username || !newUser.password) return
    try {
      await api.createUser(newUser)
      setNewUser({ username: '', password: '', is_admin: false })
      setUserMsg('User created!')
      api.getUsers().then(setUsers)
    } catch (e) {
      setUserMsg(e.message)
    }
    setTimeout(() => setUserMsg(''), 3000)
  }

  async function deleteUser(u) {
    if (!confirm(`Delete user "${u}"?`)) return
    await api.deleteUser(u)
    api.getUsers().then(setUsers)
  }

  return (
    <Layout
      title="Settings"
      subtitle="Configure AuditVisual behavior"
      actions={
        <button className="btn btn-primary btn-sm" onClick={saveSettings}>
          <Save size={13} /> {saved ? 'Saved!' : 'Save'}
        </button>
      }
    >
      <div style={{ maxWidth: 640 }}>
        {/* Data Retention */}
        <div className="settings-section card" style={{ marginBottom: 20 }}>
          <h3>Data Retention</h3>
          <div className="setting-row">
            <div>
              <div className="setting-label">Log Retention</div>
              <div className="setting-desc">Delete records older than N days (0 = keep forever)</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input className="input" type="number" min="0" max="365" style={{ width: 80 }}
                value={settings.log_retention_days || 90}
                onChange={e => updateSetting('log_retention_days', e.target.value)} />
              <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>days</span>
            </div>
          </div>
        </div>

        {/* Alert Rules */}
        <div className="settings-section card" style={{ marginBottom: 20 }}>
          <h3>Alert Rules</h3>
          {[
            { key: 'alert_sudo_escalation', label: 'Sudo Escalation', desc: 'Alert when user runs sudo -i or su' },
            { key: 'alert_mass_delete',     label: 'Mass Delete',     desc: 'Alert when many files deleted quickly' },
            { key: 'alert_suspicious_cmd',  label: 'Suspicious Commands', desc: 'curl|bash, reverse shells, etc.' },
            { key: 'alert_brute_force',     label: 'Brute Force SSH', desc: 'Multiple failed login attempts' },
            { key: 'alert_sensitive_file',  label: 'Sensitive Files', desc: '/etc/shadow, /etc/sudoers, etc.' },
          ].map(({ key, label, desc }) => (
            <div className="setting-row" key={key}>
              <div>
                <div className="setting-label">{label}</div>
                <div className="setting-desc">{desc}</div>
              </div>
              <Toggle
                checked={settings[key] === 'true'}
                onChange={v => updateSetting(key, v)}
              />
            </div>
          ))}
        </div>

        {/* Thresholds */}
        <div className="settings-section card" style={{ marginBottom: 20 }}>
          <h3>Alert Thresholds</h3>
          {[
            { key: 'brute_force_count',     label: 'Brute Force Count',   unit: 'failures',  min: 1, max: 50 },
            { key: 'brute_force_window_min',label: 'Brute Force Window',  unit: 'minutes',   min: 1, max: 60 },
            { key: 'mass_delete_count',     label: 'Mass Delete Count',   unit: 'files',     min: 1, max: 100 },
            { key: 'mass_delete_window_sec',label: 'Mass Delete Window',  unit: 'seconds',   min: 5, max: 300 },
          ].map(({ key, label, unit, min, max }) => (
            <div className="setting-row" key={key}>
              <div className="setting-label">{label}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input className="input" type="number" min={min} max={max} style={{ width: 80 }}
                  value={settings[key] || ''}
                  onChange={e => updateSetting(key, e.target.value)} />
                <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{unit}</span>
              </div>
            </div>
          ))}
        </div>

        {/* User Management (admin only) */}
        {user?.is_admin && (
          <div className="settings-section card">
            <h3>AuditVisual Users</h3>
            {users.map(u => (
              <div className="setting-row" key={u.id}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{
                    width: 32, height: 32, background: 'rgba(59, 130, 246, 0.1)',
                    borderRadius: '50%', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', fontSize: 13, fontWeight: 700, color: 'var(--accent)',
                    border: '1px solid rgba(59, 130, 246, 0.2)'
                  }}>
                    {u.username[0]?.toUpperCase()}
                  </div>
                  <div>
                    <div className="setting-label">{u.username}</div>
                    <div className="setting-desc">{u.is_admin ? '🔑 Administrator' : 'Viewer'}</div>
                  </div>
                </div>
                {u.username !== user.username && (
                  <button className="btn btn-danger btn-sm" onClick={() => deleteUser(u.username)}>
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            ))}

            {/* Add new user */}
            <div style={{ 
              marginTop: 16, padding: '16px', background: 'rgba(0,0,0,0.2)', 
              borderRadius: '12px', border: '1px solid var(--glass-border)' 
            }}>
              <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 13 }}>Add User</div>
              {userMsg && <div style={{ marginBottom: 10, fontSize: 12, color: 'var(--success)' }}>{userMsg}</div>}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <input className="input" placeholder="Username" style={{ flex: 1, minWidth: 120 }}
                  value={newUser.username} onChange={e => setNewUser(u => ({ ...u, username: e.target.value }))} />
                <input className="input" type="password" placeholder="Password" style={{ flex: 1, minWidth: 120 }}
                  value={newUser.password} onChange={e => setNewUser(u => ({ ...u, password: e.target.value }))} />
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                  <input type="checkbox" checked={newUser.is_admin}
                    onChange={e => setNewUser(u => ({ ...u, is_admin: e.target.checked }))} />
                  Admin
                </label>
                <button className="btn btn-primary btn-sm" onClick={addUser}>
                  <UserPlus size={13} /> Add
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
