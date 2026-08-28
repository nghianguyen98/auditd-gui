import { useState, useEffect } from 'react'
import { Users, Plus, Edit2, Trash2, Shield, User } from 'lucide-react'
import Layout from '../components/Layout'
import { apiGet, apiPost, apiDelete, getStoredUser } from '../api/client'
import { formatDistanceToNow, fromUnixTime } from 'date-fns'

export default function UsersPage() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const currentUser = getStoredUser()

  const [showAddModal, setShowAddModal] = useState(false)
  const [addForm, setAddForm] = useState({ username: '', password: '', is_admin: false })
  
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [passwordForm, setPasswordForm] = useState({ username: '', password: '' })

  const [deleteUser, setDeleteUser] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const data = await apiGet('/auth/users')
      setUsers(data)
    } catch (err) {
      console.error("Failed to load users", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleAddUser(e) {
    e.preventDefault()
    try {
      await apiPost('/auth/users', addForm)
      setShowAddModal(false)
      setAddForm({ username: '', password: '', is_admin: false })
      load()
    } catch (err) {
      alert("Failed to add user: " + err.message)
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault()
    try {
      await apiPost(`/auth/users/${passwordForm.username}/password`, { password: passwordForm.password })
      setShowPasswordModal(false)
      setPasswordForm({ username: '', password: '' })
      alert("Password changed successfully!")
    } catch (err) {
      alert("Failed to change password: " + err.message)
    }
  }

  async function handleConfirmDelete() {
    try {
      await apiDelete(`/auth/users/${deleteUser.username}`)
      setDeleteUser(null)
      load()
    } catch (err) {
      alert("Failed to delete user: " + err.message)
    }
  }

  return (
    <Layout title="Users" subtitle="Manage system access and roles" actions={
      <button className="btn btn-primary btn-sm" onClick={() => setShowAddModal(true)}>
        <Plus size={14} /> Add User
      </button>
    }>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th><User size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Username</th>
                <th>Role</th>
                <th>Created At</th>
                <th>Last Login</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && users.length === 0
                ? <tr><td colSpan={5} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>Loading...</td></tr>
                : users.length === 0
                  ? <tr><td colSpan={5}><div className="empty-state"><div className="empty-state-text">No users found.</div></div></td></tr>
                  : users.map(u => (
                    <tr key={u.id}>
                      <td><strong>{u.username}</strong> {u.username === currentUser?.username && <span className="badge badge-info" style={{ marginLeft: 8 }}>You</span>}</td>
                      <td>
                        {u.is_admin ? (
                          <span className="badge badge-primary"><Shield size={10} style={{ marginRight: 4 }}/> Admin</span>
                        ) : (
                          <span className="badge badge-neutral">Viewer</span>
                        )}
                      </td>
                      <td style={{ color: 'var(--text-secondary)' }}>
                        {formatDistanceToNow(fromUnixTime(u.created_at), { addSuffix: true })}
                      </td>
                      <td style={{ color: 'var(--text-secondary)' }}>
                        {u.last_login ? formatDistanceToNow(fromUnixTime(u.last_login), { addSuffix: true }) : 'Never'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button 
                          className="btn btn-ghost btn-sm" 
                          style={{ padding: '0 8px', marginRight: '4px' }} 
                          onClick={() => { setPasswordForm({ username: u.username, password: '' }); setShowPasswordModal(true); }}
                          title="Change Password"
                        >
                          <Edit2 size={14} />
                        </button>
                        {u.username !== currentUser?.username && (
                          <button 
                            className="btn btn-ghost btn-sm" 
                            style={{ padding: '0 8px', color: 'var(--danger)' }} 
                            onClick={() => setDeleteUser(u)}
                            title="Delete User"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>
      </div>

      {/* Add User Modal */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '400px' }}>
            <h3 style={{ margin: '0 0 1rem 0' }}>Add New User</h3>
            <form onSubmit={handleAddUser}>
              <div className="form-group">
                <label className="form-label">Username</label>
                <input 
                  type="text" 
                  required
                  className="input input-full"
                  value={addForm.username} 
                  onChange={e => setAddForm({...addForm, username: e.target.value})} 
                  placeholder="e.g. security_auditor"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Password</label>
                <input 
                  type="password" 
                  required
                  minLength={6}
                  className="input input-full"
                  value={addForm.password} 
                  onChange={e => setAddForm({...addForm, password: e.target.value})}
                  placeholder="Minimum 6 characters"
                />
              </div>
              <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input 
                  type="checkbox" 
                  id="isAdmin"
                  checked={addForm.is_admin}
                  onChange={e => setAddForm({...addForm, is_admin: e.target.checked})}
                />
                <label htmlFor="isAdmin" style={{ cursor: 'pointer', margin: 0 }}>Administrator privileges (Can modify settings & nodes)</label>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowAddModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Create User</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Change Password Modal */}
      {showPasswordModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '400px' }}>
            <h3 style={{ margin: '0 0 1rem 0' }}>Change Password: {passwordForm.username}</h3>
            <form onSubmit={handleChangePassword}>
              <div className="form-group">
                <label className="form-label">New Password</label>
                <input 
                  type="password" 
                  required
                  minLength={6}
                  className="input input-full"
                  value={passwordForm.password} 
                  onChange={e => setPasswordForm({...passwordForm, password: e.target.value})}
                  placeholder="Minimum 6 characters"
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowPasswordModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Password</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {deleteUser && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '400px' }}>
            <h3 style={{ margin: '0 0 1rem 0', color: 'var(--danger)' }}>Delete User</h3>
            <p>Are you sure you want to delete user <strong>{deleteUser.username}</strong>?</p>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              This action cannot be undone. They will immediately lose access to the system.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '20px' }}>
              <button className="btn btn-ghost" onClick={() => setDeleteUser(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={handleConfirmDelete}>Delete User</button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
