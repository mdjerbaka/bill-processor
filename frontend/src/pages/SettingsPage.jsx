import { useState, useEffect } from 'react'
import { settingsAPI, quickbooksAPI, healthAPI, microsoftAPI, authAPI } from '../services/api'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const [emailConfig, setEmailConfig] = useState({
    imap_host: '', imap_port: 993, imap_username: '', imap_password: '', use_ssl: true
  })
  const [qbStatus, setQbStatus] = useState({ connected: false })
  const [health, setHealth] = useState(null)
  const [ocrConfig, setOcrConfig] = useState({
    ocr_provider: 'none', openai_api_key: '', azure_endpoint: '', azure_api_key: '',
    aws_access_key_id: '', aws_secret_access_key: '', aws_region: '',
  })
  const [ocrStatus, setOcrStatus] = useState({ openai_key_set: false, azure_key_set: false, aws_key_set: false })
  const [savingEmail, setSavingEmail] = useState(false)
  const [testingEmail, setTestingEmail] = useState(false)
  const [pollingEmail, setPollingEmail] = useState(false)
  const [processingPending, setProcessingPending] = useState(false)
  const [savingOcr, setSavingOcr] = useState(false)
  const [testingOcr, setTestingOcr] = useState(false)
  const [msStatus, setMsStatus] = useState({ connected: false, email: '' })
  const [pollingMs, setPollingMs] = useState(false)
  const [msFolders, setMsFolders] = useState([])
  const [msFolder, setMsFolder] = useState({ folder_id: '', folder_name: 'All Folders' })
  const [loadingFolders, setLoadingFolders] = useState(false)
  const [loading, setLoading] = useState(true)
  const [qbEnvConfigured, setQbEnvConfigured] = useState(false)
  const [qbConfig, setQbConfig] = useState({
    client_id: '', client_secret: '', redirect_uri: '', environment: 'sandbox'
  })
  const [savingQB, setSavingQB] = useState(false)
  const [qbAccounts, setQbAccounts] = useState({ expense_accounts: [], bank_accounts: [] })
  const [qbDefaults, setQbDefaults] = useState({ expense_account: '', bank_account: '' })
  const [savingQBDefaults, setSavingQBDefaults] = useState(false)
  const [passwordForm, setPasswordForm] = useState({ current: '', newPw: '', confirm: '' })
  const [savingPassword, setSavingPassword] = useState(false)

  useEffect(() => {
    loadSettings()
  }, [])

  async function loadSettings() {
    setLoading(true)
    try {
      const [emailRes, qbRes, healthRes, ocrRes, msRes, qbConfigRes] = await Promise.all([
        settingsAPI.getEmailConfig().catch(() => ({ data: {} })),
        quickbooksAPI.status().catch(() => ({ data: { connected: false } })),
        healthAPI.check().catch(() => ({ data: {} })),
        settingsAPI.getOCRConfig().catch(() => ({ data: { ocr_provider: 'none' } })),
        microsoftAPI.status().catch(() => ({ data: { connected: false, email: '' } })),
        settingsAPI.getQBConfig().catch(() => ({ data: {} })),
      ])
      if (emailRes.data) {
        setEmailConfig({
          imap_host: emailRes.data.imap_host || '',
          imap_port: emailRes.data.imap_port || 993,
          imap_username: emailRes.data.imap_username || '',
          imap_password: '', // never returned
          use_ssl: emailRes.data.use_ssl ?? true,
        })
      }
      setQbStatus(qbRes.data)
      // If QB is connected, load default accounts and account lists
      if (qbRes.data?.connected) {
        setQbDefaults({
          expense_account: qbRes.data.default_expense_account || '',
          bank_account: qbRes.data.default_bank_account || '',
        })
        try {
          const acctRes = await quickbooksAPI.allAccounts()
          setQbAccounts(acctRes.data || { expense_accounts: [], bank_accounts: [] })
        } catch {}
      }
      setHealth(healthRes.data)
      if (ocrRes.data) {
        setOcrConfig(prev => ({
          ...prev,
          ocr_provider: ocrRes.data.ocr_provider || 'none',
          azure_endpoint: ocrRes.data.azure_endpoint || '',
          aws_region: ocrRes.data.aws_region || '',
        }))
        setOcrStatus(ocrRes.data)
      }
      if (msRes.data) {
        setMsStatus(msRes.data)
        if (msRes.data.connected) {
          try {
            const [foldersRes, folderSettingRes] = await Promise.all([
              microsoftAPI.listFolders(),
              microsoftAPI.getFolderSetting(),
            ])
            setMsFolders(foldersRes.data.folders || [])
            if (folderSettingRes.data) setMsFolder(folderSettingRes.data)
          } catch {}
        }
      }
      if (qbConfigRes.data) {
        setQbConfig(prev => ({
          ...prev,
          client_id: qbConfigRes.data.client_id || '',
          redirect_uri: qbConfigRes.data.redirect_uri || '',
          environment: qbConfigRes.data.environment || 'sandbox',
          // Don't overwrite secret field — only show placeholder if set
          client_secret: '',
          _secret_set: qbConfigRes.data.client_secret_set || false,
        }))
        setQbEnvConfigured(qbConfigRes.data.env_configured || false)
      }
    } catch {}
    setLoading(false)
  }

  async function handleSaveEmail() {
    setSavingEmail(true)
    try {
      await settingsAPI.saveEmailConfig(emailConfig)
      toast.success('Email settings saved')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save')
    }
    setSavingEmail(false)
  }

  async function handleTestEmail() {
    setTestingEmail(true)
    try {
      const res = await settingsAPI.testEmailConnection()
      if (res.data.connected) {
        toast.success(`Connected! ${res.data.message || ''}`)
      } else {
        toast.error(res.data.message || 'Connection failed')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Test failed')
    }
    setTestingEmail(false)
  }

  async function handlePollNow() {
    setPollingEmail(true)
    try {
      const res = await settingsAPI.pollEmails()
      const { emails_fetched, invoices_created, errors } = res.data
      if (emails_fetched > 0) {
        toast.success(`Fetched ${emails_fetched} emails, created ${invoices_created} invoices`)
      } else {
        toast.success('No new emails with invoice attachments found')
      }
      if (errors?.length) {
        toast.error(`${errors.length} error(s): ${errors[0]}`)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Poll failed')
    }
    setPollingEmail(false)
  }

  async function handleProcessPending() {
    setProcessingPending(true)
    try {
      const res = await settingsAPI.processPending()
      const { total_pending, processed, errors } = res.data
      toast.success(`Processed ${processed} of ${total_pending} pending emails`)
      if (errors?.length) {
        toast.error(`${errors.length} error(s): ${errors[0]}`)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Processing failed')
    }
    setProcessingPending(false)
  }

  async function handleConnectQB() {
    try {
      const res = await quickbooksAPI.connect()
      const popup = window.open(res.data.auth_url, '_blank')
      // Poll for connection status while popup is open
      const poll = setInterval(async () => {
        try {
          const statusRes = await quickbooksAPI.status()
          if (statusRes.data.connected) {
            clearInterval(poll)
            setQbStatus(statusRes.data)
            toast.success('QuickBooks connected!')
            // Reload accounts
            const accts = await quickbooksAPI.getAccounts()
            if (accts.data) setQbAccounts(accts.data)
          }
        } catch {}
      }, 2000)
      // Stop polling after 5 minutes
      setTimeout(() => clearInterval(poll), 300000)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to start QuickBooks connection. Check your credentials in the form above.')
    }
  }

  async function handleSaveQBConfig() {
    setSavingQB(true)
    try {
      await settingsAPI.saveQBConfig(qbConfig)
      toast.success('QuickBooks credentials saved')
      setQbConfig(prev => ({ ...prev, client_secret: '', _secret_set: true }))
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save QB config')
    }
    setSavingQB(false)
  }

  async function handleSaveQBDefaults() {
    setSavingQBDefaults(true)
    try {
      await quickbooksAPI.saveDefaults(qbDefaults)
      toast.success('Default accounts saved — approved bills will auto-send to QuickBooks')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save QB defaults')
    }
    setSavingQBDefaults(false)
  }

  async function handleDisconnectQB() {
    if (!window.confirm('Disconnect from QuickBooks? You can reconnect later.')) return
    try {
      await quickbooksAPI.disconnect()
      setQbStatus({ connected: false })
      toast.success('QuickBooks disconnected')
    } catch {
      toast.error('Failed to disconnect QuickBooks')
    }
  }

  async function handleConnectMS() {
    try {
      const res = await microsoftAPI.connect()
      const popup = window.open(res.data.auth_url, '_blank')
      // Poll for connection status while popup is open
      const poll = setInterval(async () => {
        try {
          const statusRes = await microsoftAPI.status()
          if (statusRes.data.connected) {
            clearInterval(poll)
            setMsStatus(statusRes.data)
            toast.success('Microsoft 365 connected!')
            // Load folders after connecting
            try {
              const foldersRes = await microsoftAPI.listFolders()
              setMsFolders(foldersRes.data.folders || [])
            } catch {}
          }
        } catch {}
      }, 2000)
      // Stop polling after 5 minutes
      setTimeout(() => clearInterval(poll), 300000)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to start Microsoft 365 connection')
    }
  }

  async function handleDisconnectMS() {
    if (!window.confirm('Disconnect from Microsoft 365? You can reconnect later.')) return
    try {
      await microsoftAPI.disconnect()
      setMsStatus({ connected: false, email: '' })
      toast.success('Microsoft 365 disconnected')
    } catch {
      toast.error('Failed to disconnect')
    }
  }

  async function handlePollMS() {
    setPollingMs(true)
    try {
      const res = await microsoftAPI.poll()
      const { emails_fetched, invoices_created, errors } = res.data
      if (emails_fetched > 0) {
        toast.success(`Fetched ${emails_fetched} emails, created ${invoices_created} invoices`)
      } else {
        toast.success('No new emails with invoice attachments found')
      }
      if (errors?.length) {
        toast.error(`${errors.length} error(s): ${errors[0]}`)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Poll failed')
    }
    setPollingMs(false)
  }

  async function handleSaveMsFolder(folderId) {
    const folder = msFolders.find(f => f.id === folderId)
    const data = {
      folder_id: folderId,
      folder_name: folder ? folder.name : 'All Folders',
    }
    try {
      await microsoftAPI.saveFolderSetting(data)
      setMsFolder(data)
      toast.success(`Mail folder set to: ${data.folder_name}`)
    } catch (err) {
      toast.error('Failed to save folder setting')
    }
  }

  async function handleSaveOcr() {
    setSavingOcr(true)
    try {
      const res = await settingsAPI.saveOCRConfig(ocrConfig)
      setOcrStatus(res.data)
      // Clear key fields after save
      setOcrConfig(prev => ({ ...prev, openai_api_key: '', azure_api_key: '', aws_access_key_id: '', aws_secret_access_key: '' }))
      toast.success('API key settings saved')
      loadSettings()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save')
    }
    setSavingOcr(false)
  }

  async function handleTestOcr() {
    setTestingOcr(true)
    try {
      const res = await settingsAPI.testOCRConfig()
      if (res.data.ok) {
        toast.success(res.data.message)
      } else {
        toast.error(res.data.message || 'Test failed')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Test failed')
    }
    setTestingOcr(false)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      {/* Email Configuration */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-100">Email Configuration</h2>
        <p className="text-sm text-gray-400 mb-4">
          Configure the IMAP email account to poll for incoming bills and invoices.
        </p>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">IMAP Server</label>
              <input
                type="text"
                placeholder="outlook.office365.com"
                value={emailConfig.imap_host}
                onChange={(e) => setEmailConfig({ ...emailConfig, imap_host: e.target.value })}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">IMAP Port</label>
              <input
                type="number"
                value={emailConfig.imap_port}
                onChange={(e) => setEmailConfig({ ...emailConfig, imap_port: parseInt(e.target.value) || 993 })}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Email / Username</label>
            <input
              type="text"
              placeholder="bills@yourcompany.com"
              value={emailConfig.imap_username}
              onChange={(e) => setEmailConfig({ ...emailConfig, imap_username: e.target.value })}
              className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Password / App Password</label>
            <input
              type="password"
              placeholder="Enter password..."
              value={emailConfig.imap_password}
              onChange={(e) => setEmailConfig({ ...emailConfig, imap_password: e.target.value })}
              className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
            />
            <p className="text-xs text-gray-500 mt-1">For Outlook/M365, use an App Password. For Gmail, use an App Password (not your regular password).</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="use_ssl"
              checked={emailConfig.use_ssl}
              onChange={(e) => setEmailConfig({ ...emailConfig, use_ssl: e.target.checked })}
              className="rounded"
            />
            <label htmlFor="use_ssl" className="text-sm text-gray-300">Use SSL/TLS</label>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleSaveEmail}
              disabled={savingEmail}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {savingEmail ? 'Saving...' : 'Save Email Settings'}
            </button>
            <button
              onClick={handleTestEmail}
              disabled={testingEmail}
              className="px-4 py-2 border border-gray-600 text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-700 disabled:opacity-50"
            >
              {testingEmail ? 'Testing...' : 'Test Connection'}
            </button>
            <button
              onClick={handlePollNow}
              disabled={pollingEmail}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
            >
              {pollingEmail ? 'Polling...' : 'Poll Now'}
            </button>
            <button
              onClick={handleProcessPending}
              disabled={processingPending}
              className="px-4 py-2 border border-amber-600 text-amber-400 rounded-lg text-sm font-medium hover:bg-amber-900/30 disabled:opacity-50"
            >
              {processingPending ? 'Processing...' : 'Process Pending'}
            </button>
          </div>
        </div>
      </div>

      {/* Microsoft 365 Email (OAuth — recommended for Outlook) */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-100">Microsoft 365 Email</h2>
        <p className="text-sm text-gray-400 mb-4">
          Connect your Outlook / Microsoft 365 mailbox using OAuth. This is <span className="text-amber-400 font-medium">required</span> for
          Microsoft 365 accounts — basic password authentication is no longer supported by Microsoft.
        </p>

        <div className="flex flex-wrap items-center gap-4">
          {msStatus.connected ? (
            <>
              <span className="flex items-center gap-2 text-sm text-green-400">
                <span className="w-2 h-2 bg-green-500 rounded-full" />
                Connected
                {msStatus.email && <span className="text-gray-400">({msStatus.email})</span>}
              </span>
              <button
                onClick={handlePollMS}
                disabled={pollingMs}
                className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
              >
                {pollingMs ? 'Polling...' : 'Poll Now'}
              </button>
              <button
                onClick={handleConnectMS}
                className="px-4 py-2 border border-gray-600 text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-700"
              >
                Reconnect
              </button>
              <button
                onClick={handleDisconnectMS}
                className="px-4 py-2 border border-red-700 text-red-400 rounded-lg text-sm font-medium hover:bg-red-900/30"
              >
                Disconnect
              </button>
            </>
          ) : (
            <button
              onClick={handleConnectMS}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
            >
              Connect Microsoft 365
            </button>
          )}
        </div>
        {msStatus.connected && (
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-300 mb-1">Mail Folder to Poll</label>
            <select
              value={msFolder.folder_id}
              onChange={(e) => handleSaveMsFolder(e.target.value)}
              className="w-full max-w-md px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
            >
              <option value="">All Folders (default)</option>
              {msFolders.map(f => (
                <option key={f.id} value={f.id}>{f.name} ({f.count})</option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Choose a specific folder to only poll emails from that folder, or leave as "All Folders" to scan everything.
            </p>
          </div>
        )}
        {!msStatus.connected && (
          <p className="text-xs text-gray-500 mt-3">
            Requires an Azure App Registration with <code className="text-gray-400">Mail.Read</code> permission.
            Set <code className="text-gray-400">MS_CLIENT_ID</code>, <code className="text-gray-400">MS_CLIENT_SECRET</code>, and <code className="text-gray-400">MS_TENANT_ID</code> in your .env file.
          </p>
        )}
      </div>

      {/* QuickBooks Integration */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-100">API Keys &amp; OCR</h2>
        <p className="text-sm text-gray-400 mb-4">
          Configure the AI provider used to automatically extract invoice data from attachments.
          Your API key is encrypted and stored securely.
        </p>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">OCR Provider</label>
            <select
              value={ocrConfig.ocr_provider}
              onChange={(e) => setOcrConfig({ ...ocrConfig, ocr_provider: e.target.value })}
              className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
            >
              <option value="none">None (Manual Entry)</option>
              <option value="openai">OpenAI GPT-4o Vision</option>
              <option value="azure">Azure Document Intelligence</option>
              <option value="aws">AWS Textract</option>
            </select>
          </div>

          {ocrConfig.ocr_provider === 'openai' && (
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">OpenAI API Key</label>
              <input
                type="password"
                placeholder={ocrStatus.openai_key_set ? '••••••••  (key saved)' : 'sk-...'}
                value={ocrConfig.openai_api_key}
                onChange={(e) => setOcrConfig({ ...ocrConfig, openai_api_key: e.target.value })}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
              />
              <p className="text-xs text-gray-500 mt-1">
                Get your key at <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">platform.openai.com/api-keys</a>
              </p>
              {ocrStatus.openai_key_set && (
                <p className="text-xs text-green-600 mt-1">Key is saved. Leave blank to keep existing key.</p>
              )}
            </div>
          )}

          {ocrConfig.ocr_provider === 'azure' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Azure Endpoint</label>
                <input
                  type="text"
                  placeholder="https://your-resource.cognitiveservices.azure.com"
                  value={ocrConfig.azure_endpoint}
                  onChange={(e) => setOcrConfig({ ...ocrConfig, azure_endpoint: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Azure API Key</label>
                <input
                  type="password"
                  placeholder={ocrStatus.azure_key_set ? '••••••••  (key saved)' : 'Enter key...'}
                  value={ocrConfig.azure_api_key}
                  onChange={(e) => setOcrConfig({ ...ocrConfig, azure_api_key: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
                />
              </div>
            </>
          )}

          {ocrConfig.ocr_provider === 'aws' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">AWS Access Key ID</label>
                  <input
                    type="password"
                    placeholder={ocrStatus.aws_key_set ? '••••••••  (key saved)' : 'AKIA...'}
                    value={ocrConfig.aws_access_key_id}
                    onChange={(e) => setOcrConfig({ ...ocrConfig, aws_access_key_id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">AWS Secret Key</label>
                  <input
                    type="password"
                    placeholder={ocrStatus.aws_key_set ? '••••••••  (saved)' : 'Enter secret...'}
                    value={ocrConfig.aws_secret_access_key}
                    onChange={(e) => setOcrConfig({ ...ocrConfig, aws_secret_access_key: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">AWS Region</label>
                <input
                  type="text"
                  placeholder="us-east-1"
                  value={ocrConfig.aws_region}
                  onChange={(e) => setOcrConfig({ ...ocrConfig, aws_region: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
                />
              </div>
            </>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleSaveOcr}
              disabled={savingOcr}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {savingOcr ? 'Saving...' : 'Save API Settings'}
            </button>
            {ocrConfig.ocr_provider !== 'none' && (
              <button
                onClick={handleTestOcr}
                disabled={testingOcr}
                className="px-4 py-2 border border-gray-600 text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-700 disabled:opacity-50"
              >
                {testingOcr ? 'Testing...' : 'Test API Key'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* QuickBooks Integration */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-100">QuickBooks Online</h2>
        <p className="text-sm text-gray-400 mb-4">
          Connect to QuickBooks to automatically push approved bills as accounts-payable entries.
        </p>

        {/* QB Credentials Form — hidden when pre-configured via .env */}
        {qbEnvConfigured ? (
          <div className="flex items-center gap-2 mb-4 px-3 py-2.5 bg-green-900/30 border border-green-800/50 rounded-lg">
            <span className="w-2 h-2 bg-green-500 rounded-full" />
            <span className="text-sm text-green-300">QuickBooks credentials are pre-configured. Just click Connect below to sign in with your QuickBooks account.</span>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Client ID</label>
                <input
                  type="text"
                  value={qbConfig.client_id}
                  onChange={(e) => setQbConfig(prev => ({ ...prev, client_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-700 text-gray-200 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                  placeholder="Your QuickBooks Client ID"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Client Secret {qbConfig._secret_set && <span className="text-green-400 text-xs">(saved)</span>}
                </label>
                <input
                  type="password"
                  value={qbConfig.client_secret}
                  onChange={(e) => setQbConfig(prev => ({ ...prev, client_secret: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-700 text-gray-200 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                  placeholder={qbConfig._secret_set ? '••••••••' : 'Your QuickBooks Client Secret'}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Redirect URI</label>
                <input
                  type="text"
                  value={qbConfig.redirect_uri}
                  onChange={(e) => setQbConfig(prev => ({ ...prev, redirect_uri: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-700 text-gray-200 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                  placeholder="http://localhost:8000/api/v1/quickbooks/callback"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Environment</label>
                <select
                  value={qbConfig.environment}
                  onChange={(e) => setQbConfig(prev => ({ ...prev, environment: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-700 text-gray-200 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                >
                  <option value="sandbox">Sandbox</option>
                  <option value="production">Production</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-3 mb-4">
              <button
                onClick={handleSaveQBConfig}
                disabled={savingQB}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {savingQB ? 'Saving...' : 'Save Credentials'}
              </button>
            </div>
          </>
        )}

        <div className="border-t border-gray-700 pt-4">
          <div className="flex items-center gap-4">
            {qbStatus.connected ? (
              <>
                <span className="flex items-center gap-2 text-sm text-green-600">
                  <span className="w-2 h-2 bg-green-500 rounded-full" />
                  Connected
                  {qbStatus.company_name && <span className="text-gray-400">({qbStatus.company_name})</span>}
                </span>
                <button
                  onClick={handleConnectQB}
                  className="px-4 py-2 border border-gray-600 text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-700"
                >
                  Reconnect
                </button>
                <button
                  onClick={handleDisconnectQB}
                  className="px-4 py-2 border border-red-700 text-red-400 rounded-lg text-sm font-medium hover:bg-red-900/30"
                >
                  Disconnect
                </button>
              </>
            ) : (
              <button
                onClick={handleConnectQB}
                className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700"
              >
                Connect QuickBooks
              </button>
            )}
          </div>
        </div>

        {/* Default Accounts — shown when connected */}
        {qbStatus.connected && (
          <div className="border-t border-gray-700 pt-4 mt-4">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">Default Accounts for Auto-Sync</h3>
            <p className="text-xs text-gray-400 mb-3">
              When you approve a bill, it will automatically be sent to QuickBooks and posted to the expense account below. When you mark a bill as paid, the payment will sync to QuickBooks using the bank account.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Default Expense Account</label>
                <select
                  value={qbDefaults.expense_account}
                  onChange={(e) => setQbDefaults(prev => ({ ...prev, expense_account: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-700 text-gray-200 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                >
                  <option value="">Auto-detect (first Expense account)</option>
                  {qbAccounts.expense_accounts.map(a => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Default Bank Account (for payments)</label>
                <select
                  value={qbDefaults.bank_account}
                  onChange={(e) => setQbDefaults(prev => ({ ...prev, bank_account: e.target.value }))}
                  className="w-full px-3 py-2 bg-gray-700 text-gray-200 border border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                >
                  <option value="">Auto-detect (first Bank account)</option>
                  {qbAccounts.bank_accounts.map(a => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </div>
            </div>
            <button
              onClick={handleSaveQBDefaults}
              disabled={savingQBDefaults}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {savingQBDefaults ? 'Saving...' : 'Save Default Accounts'}
            </button>
          </div>
        )}
      </div>

      {/* System Status */}
      {health && (
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-100">System Status</h2>
          <div className="space-y-3">
            {[
              { label: 'Database', ok: health.db_connected },
              { label: 'Redis', ok: health.redis_connected },
              { label: 'Email Polling', ok: !!health.last_email_poll },
              { label: 'OCR Provider', value: health.ocr_provider },
            ].map(({ label, ok, value }) => (
              <div key={label} className="flex items-center justify-between py-2 border-b border-gray-700 last:border-0">
                <span className="text-sm text-gray-400">{label}</span>
                {value !== undefined ? (
                  <span className="text-sm font-medium text-gray-200">{value || '—'}</span>
                ) : (
                  <span className={`flex items-center gap-2 text-sm ${ok ? 'text-green-600' : 'text-red-600'}`}>
                    <span className={`w-2 h-2 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
                    {ok ? 'Connected' : 'Disconnected'}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Change Password */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-100">Change Password</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Current Password</label>
            <input
              type="password"
              value={passwordForm.current}
              onChange={(e) => setPasswordForm({ ...passwordForm, current: e.target.value })}
              className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">New Password</label>
            <input
              type="password"
              value={passwordForm.newPw}
              onChange={(e) => setPasswordForm({ ...passwordForm, newPw: e.target.value })}
              className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Confirm New Password</label>
            <input
              type="password"
              value={passwordForm.confirm}
              onChange={(e) => setPasswordForm({ ...passwordForm, confirm: e.target.value })}
              className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
            />
          </div>
          <button
            disabled={savingPassword || !passwordForm.current || !passwordForm.newPw || !passwordForm.confirm}
            onClick={async () => {
              if (passwordForm.newPw !== passwordForm.confirm) {
                toast.error('New passwords do not match')
                return
              }
              if (passwordForm.newPw.length < 8) {
                toast.error('Password must be at least 8 characters')
                return
              }
              setSavingPassword(true)
              try {
                await authAPI.changePassword({ current_password: passwordForm.current, new_password: passwordForm.newPw })
                toast.success('Password changed successfully')
                setPasswordForm({ current: '', newPw: '', confirm: '' })
              } catch (err) {
                toast.error(err.response?.data?.detail || 'Failed to change password')
              }
              setSavingPassword(false)
            }}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {savingPassword ? 'Saving...' : 'Change Password'}
          </button>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-red-900/50 p-6">
        <h2 className="text-lg font-semibold mb-2 text-red-400">Danger Zone</h2>
        <p className="text-sm text-gray-400 mb-4">
          Reset all invoice data (invoices, emails, attachments, payables). The email poller will re-process your inbox on its next run.
        </p>
        <div className="flex gap-3">
          <button
            onClick={async () => {
              if (!window.confirm('This will DELETE all invoices, emails, attachments, and payables. Are you sure?')) return
              try {
                const res = await settingsAPI.resetInvoices()
                toast.success(`Deleted ${res.data.deleted_invoices} invoices and ${res.data.deleted_emails} emails`)
              } catch (err) {
                toast.error(err.response?.data?.detail || 'Reset failed')
              }
            }}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Reset All Invoice Data
          </button>
          <button
            onClick={async () => {
              if (!window.confirm('This will DELETE all jobs and vendor mappings. Are you sure?')) return
              try {
                const res = await settingsAPI.resetJobs()
                toast.success(`Deleted ${res.data.deleted_jobs} jobs`)
              } catch (err) {
                toast.error(err.response?.data?.detail || 'Reset failed')
              }
            }}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Reset All Job Data
          </button>
        </div>
      </div>
    </div>
  )
}
