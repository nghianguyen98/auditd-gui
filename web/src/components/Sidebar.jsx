import { NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Monitor, Users, Bell, Settings, LogOut, Activity, Server } from 'lucide-react'
import { api, getStoredUser, apiGet } from '../api/client'
import { useState, useEffect } from 'react'
import { useNodeContext } from '../NodeContext'

export default function Sidebar() {
  const navigate = useNavigate()
  const user = getStoredUser()
  const { selectedNodeId } = useNodeContext()
  const [alertCount, setAlertCount] = useState(0)

  useEffect(() => {
    const q = selectedNodeId ? `?node_id=${selectedNodeId}` : ''
    apiGet(`/alerts/summary${q}`).then(data => {
      const total = Object.values(data).reduce((a, b) => a + b, 0)
      setAlertCount(total)
    }).catch(() => {})
    
    const interval = setInterval(() => {
      apiGet(`/alerts/summary${q}`).then(data => {
        setAlertCount(Object.values(data).reduce((a, b) => a + b, 0))
      }).catch(() => {})
    }, 30000)
    
    return () => clearInterval(interval)
  }, [selectedNodeId])

  function handleLogout() {
    api.logout()
    navigate('/login')
  }

  const navItems = [
    { to: '/',        icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/nodes',   icon: Server,          label: 'Servers' },
    { to: '/sessions', icon: Monitor,         label: 'Sessions' },
    { to: '/users',   icon: Users,           label: 'Users' },
    { to: '/alerts',  icon: Bell,            label: 'Alerts', badge: alertCount },
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">🛡️</div>
        <div>
          <div className="logo-text">Auditd GUI</div>
          <div className="logo-version">v1.0 · Monitor</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Navigation</div>
        {navItems.map(({ to, icon: Icon, label, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <Icon className="nav-icon" size={16} />
            {label}
            {badge > 0 && <span className="nav-badge">{badge}</span>}
          </NavLink>
        ))}

        {user?.is_admin && (
          <>
            <div className="nav-section-label" style={{ marginTop: 8 }}>Admin</div>
            <NavLink
              to="/settings"
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <Settings className="nav-icon" size={16} />
              Settings
            </NavLink>
          </>
        )}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-user" onClick={handleLogout} title="Sign out">
          <div className="user-avatar">
            {(user?.username || 'U')[0].toUpperCase()}
          </div>
          <div className="user-info">
            <div className="user-name">{user?.username || 'User'}</div>
            <div className="user-role">{user?.is_admin ? 'Administrator' : 'Viewer'}</div>
          </div>
          <LogOut size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        </div>
      </div>
    </aside>
  )
}
