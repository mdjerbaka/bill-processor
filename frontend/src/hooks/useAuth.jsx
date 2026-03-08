import { createContext, useContext, useState, useEffect } from 'react'
import { authAPI } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [isSetup, setIsSetup] = useState(null) // null = loading
  const [setupStatus, setSetupStatus] = useState(null)

  useEffect(() => {
    checkSetup()
  }, [])

  async function checkSetup() {
    try {
      const res = await authAPI.setupStatus()
      setSetupStatus(res.data)
      setIsSetup(res.data.is_setup_complete)
    } catch {
      setIsSetup(false)
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
      token, isAuthenticated, isSetup, setupStatus,
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
