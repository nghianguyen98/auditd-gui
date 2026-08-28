import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { isAuthenticated, getStoredUser } from './api/client'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Sessions from './pages/Sessions'
import SessionDetail from './pages/SessionDetail'
import Users from './pages/Users'
import Alerts from './pages/Alerts'
import Settings from './pages/Settings'
import Nodes from './pages/Nodes'
import { NodeProvider } from './NodeContext'
import { ThemeProvider } from './ThemeContext'

function PrivateRoute({ children }) {
  return isAuthenticated() ? children : <Navigate to="/login" replace />
}

function AdminRoute({ children }) {
  const user = getStoredUser();
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  if (user && !user.is_admin) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <ThemeProvider>
      <NodeProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
            <Route path="/sessions" element={<PrivateRoute><Sessions /></PrivateRoute>} />
            <Route path="/sessions/:id" element={<PrivateRoute><SessionDetail /></PrivateRoute>} />
            <Route path="/users" element={<AdminRoute><Users /></AdminRoute>} />
            <Route path="/alerts" element={<PrivateRoute><Alerts /></PrivateRoute>} />
            <Route path="/settings" element={<AdminRoute><Settings /></AdminRoute>} />
            <Route path="/nodes" element={<PrivateRoute><Nodes /></PrivateRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </NodeProvider>
    </ThemeProvider>
  )
}
