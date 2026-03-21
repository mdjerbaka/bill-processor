import { createContext, useContext, useState, useEffect } from 'react'
import { authAPI } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [isSetup, setIsSetup] = useState(null) // null = loading
  const [setupStatus, setSetupStatus] = useState(null)
  const [connectionError, setConnectionError] = useState(false)

  useEffect(() => {
    checkSetup()
    validateToken()
  }, [])

  async function checkSetup(retries = 2) {
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const res = await authAPI.setupStatus()
        setSetupStatus(res.data)
        setIsSetup(res.data.is_setup_complete)
        setConnectionError(false)
        return
      } catch {
        if (attempt < retries) {
          await new Promise(r => setTimeout(r, 1500))
        }
      }
    }
    // All retries failed — assume setup is done (safe: shows login page)
    setSetupStatus({ has_user: true, has_email_config: false, has_qbo_connection: false, has_jobs: false })
    setIsSetup(false)
    setConnectionError(true)
  }

  async function validateToken() {
    const stored = localStorage.getItem('token')
    if (!stored) return
    try {
      await authAPI.me()
    } catch {
      localStorage.removeItem('token')
      setToken(null)
    }
  }

  function login(newToken) {
    localStorage.setItem('token', newToken)
    setToken(newToken)
  }

  function logout() {
    localStorage.removeItem('token')
    setToken(null)
  }

  const isAuthenticated = !!token

  return (
    <AuthContext.Provider value={{
      token, isAuthenticated, isSetup, setupStatus, connectionError,
      login, logout, checkSetup,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
