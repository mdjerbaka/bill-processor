import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { authAPI, settingsAPI } from '../services/api'
import toast from 'react-hot-toast'

const STEPS = ['Create Account', 'Email Setup', 'All Done']

export default function SetupWizard() {
  const { login, checkSetup } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)

  // Account form
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPw, setConfirmPw] = useState('')

  // Email form
  const [imapHost, setImapHost] = useState('')
  const [imapPort, setImapPort] = useState(993)
  const [imapUsername, setImapUsername] = useState('')
  const [imapPassword, setImapPassword] = useState('')
  const [useSsl, setUseSsl] = useState(true)

  async function handleCreateAccount(e) {
    e.preventDefault()
    if (password !== confirmPw) {
      toast.error('Passwords do not match')
      return
    }
    setLoading(true)
    try {
      const res = await authAPI.setup({ username, password })
      login(res.data.access_token)
      toast.success('Account created!')
      setStep(1)
    } catch (err) {
      const detail = err.response?.data?.detail || 'Setup failed'
      if (detail === 'Setup already completed') {
        toast.success('Account already exists. Redirecting to login...')
        navigate('/login')
        return
      }
      toast.error(detail)
    } finally {
      setLoading(false)
    }
  }

  async function handleEmailSetup(e) {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await settingsAPI.saveEmailConfig({
        imap_host: imapHost,
        imap_port: imapPort,
        imap_username: imapUsername,
        imap_password: imapPassword,
        use_ssl: useSsl,
      })
      if (res.data.is_connected) {
        toast.success('Email connected successfully!')
      } else {
        toast.success('Email config saved (connection test pending)')
      }
      setStep(2)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Email setup failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleFinish() {
    await checkSetup()
    window.location.href = '/'
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <div className="max-w-lg w-full bg-gray-800 rounded-xl shadow-lg p-8">
        <h1 className="text-2xl font-bold text-center mb-2 text-gray-100">Welcome to Bill Processor</h1>
        <p className="text-gray-400 text-center mb-6">Let's get you set up in a few steps</p>

        {/* Step indicator */}
        <div className="flex items-center justify-center mb-8">
          {STEPS.map((label, i) => (
            <div key={i} className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                i <= step ? 'bg-blue-600 text-white' : 'bg-gray-600 text-gray-400'
              }`}>
                {i < step ? '✓' : i + 1}
              </div>
              <span className={`ml-2 text-sm ${i <= step ? 'text-gray-100' : 'text-gray-500'}`}>
                {label}
              </span>
              {i < STEPS.length - 1 && <div className="w-8 h-px bg-gray-600 mx-3" />}
            </div>
          ))}
        </div>

        {/* Step 0: Create account */}
        {step === 0 && (
          <form onSubmit={handleCreateAccount} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                minLength={3}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                minLength={8}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Confirm Password</label>
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                minLength={8}
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Account & Continue'}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-gray-400">
            Already have an account?{' '}
            <Link to="/login" className="text-blue-400 hover:text-blue-300 font-medium">
              Sign in here
            </Link>
          </p>
        )}

        {/* Step 1: Email setup */}
        {step === 1 && (
          <form onSubmit={handleEmailSetup} className="space-y-4">
            <p className="text-sm text-gray-400 mb-4">
              Connect your invoice email inbox so bills are automatically imported.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 sm:col-span-1">
                <label className="block text-sm font-medium text-gray-300 mb-1">IMAP Server</label>
                <input
                  type="text"
                  value={imapHost}
                  onChange={(e) => setImapHost(e.target.value)}
                  placeholder="imap.gmail.com"
                  className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-500"
                  required
                />
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label className="block text-sm font-medium text-gray-300 mb-1">Port</label>
                <input
                  type="number"
                  value={imapPort}
                  onChange={(e) => setImapPort(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Email / Username</label>
              <input
                type="text"
                value={imapUsername}
                onChange={(e) => setImapUsername(e.target.value)}
                placeholder="invoices@santimawcontracting.com"
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-500"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Password / App Password</label>
              <input
                type="password"
                value={imapPassword}
                onChange={(e) => setImapPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={useSsl}
                onChange={(e) => setUseSsl(e.target.checked)}
                className="rounded border-gray-600 bg-gray-700"
              />
              <span className="text-sm text-gray-300">Use SSL</span>
            </label>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="flex-1 py-2.5 border border-gray-600 text-gray-300 rounded-lg font-medium hover:bg-gray-700"
              >
                Skip for Now
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Connecting...' : 'Save & Continue'}
              </button>
            </div>
          </form>
        )}

        {/* Step 2: Done */}
        {step === 2 && (
          <div className="text-center space-y-4">
            <div className="text-5xl mb-4">🎉</div>
            <h2 className="text-xl font-semibold text-gray-100">You're all set!</h2>
            <p className="text-gray-400">
              Your bill processor is ready. You can configure QuickBooks
              and import jobs from the Settings page at any time.
            </p>
            <button
              onClick={handleFinish}
              className="w-full py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
            >
              Go to Dashboard
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
