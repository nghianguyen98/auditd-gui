import Sidebar from './Sidebar'
import NodeSelector from './NodeSelector'
import { useTheme } from '../ThemeContext'
import { Sun, Moon } from 'lucide-react'

export default function Layout({ title, subtitle, actions, children }) {
  const { theme, toggleTheme } = useTheme()

  return (
    <>
      <div className="ambient-bg">
        <div className="ambient-orb ambient-orb-1" />
        <div className="ambient-orb ambient-orb-2" />
      </div>
      <div className="app-layout">
        <Sidebar />
      <div className="main-content">
        <header className="page-header">
          <div className="page-title">{title}</div>
          {subtitle && <div className="page-subtitle">{subtitle}</div>}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 16 }}>
            <NodeSelector />
            <button 
              onClick={toggleTheme} 
              className="btn btn-ghost btn-icon" 
              title="Toggle Theme"
            >
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            {actions && <div style={{ display: 'flex', gap: 8 }}>{actions}</div>}
          </div>
        </header>
        <main className="page-content fade-in">
          {children}
        </main>
      </div>
      </div>
    </>
  )
}
