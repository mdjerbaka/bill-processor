import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Attach token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ── Auth ────────────────────────────────────────────────
export const authAPI = {
  setupStatus: () => api.get('/auth/setup-status'),
  setup: (data) => api.post('/auth/setup', data),
  login: (username, password) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)
    return api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },
}

// ── Invoices ────────────────────────────────────────────
export const invoicesAPI = {
  list: (params) => api.get('/invoices', { params }),
  get: (id) => api.get(`/invoices/${id}`),
  update: (id, data) => api.put(`/invoices/${id}`, data),
  approve: (id) => api.post(`/invoices/${id}/approve`),
  markPaid: (id) => api.post(`/invoices/${id}/mark-paid`),
  junk: (id) => api.post(`/invoices/${id}/junk`),
  restore: (id) => api.post(`/invoices/${id}/restore`),
  getMatchSuggestions: (id) => api.get(`/invoices/${id}/match-suggestions`),
}

// ── Jobs ────────────────────────────────────────────────
export const jobsAPI = {
  list: (activeOnly = true) => api.get('/jobs', { params: { active_only: activeOnly } }),
  create: (data) => api.post('/jobs', data),
  update: (id, data) => api.put(`/jobs/${id}`, data),
  junk: (id) => api.delete(`/jobs/${id}`),
  restore: (id) => api.post(`/jobs/${id}/restore`),
  importCSV: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/jobs/import-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listVendorMappings: () => api.get('/jobs/vendor-mappings'),
  createVendorMapping: (data) => api.post('/jobs/vendor-mappings', data),
  deleteVendorMapping: (id) => api.delete(`/jobs/vendor-mappings/${id}`),
  deleteImported: () => api.delete('/jobs/imported'),
}

// ── Payables ────────────────────────────────────────────
export const payablesAPI = {
  list: (includePaid = false) => api.get('/payables', { params: { include_paid: includePaid } }),
  markPaid: (id) => api.post(`/payables/${id}/mark-paid`),
  junk: (id) => api.post(`/payables/${id}/junk`),
  restore: (id) => api.post(`/payables/${id}/restore`),
  setBankBalance: (balance) => api.post('/payables/bank-balance', { bank_balance: balance }),
  getRealBalance: () => api.get('/payables/real-balance'),
  exportExcel: () => api.get('/payables/export', { responseType: 'blob' }),
}

// ── Settings ────────────────────────────────────────────
export const settingsAPI = {
  getEmailConfig: () => api.get('/settings/email'),
  saveEmailConfig: (data) => api.post('/settings/email', data),
  testEmailConnection: () => api.post('/settings/email/test'),
  pollEmails: () => api.post('/settings/email/poll'),
  processPending: () => api.post('/settings/email/process-pending'),
  getOCRConfig: () => api.get('/settings/ocr'),
  saveOCRConfig: (data) => api.post('/settings/ocr', data),
  testOCRConfig: () => api.post('/settings/ocr/test'),
  resetInvoices: () => api.delete('/settings/reset-invoices'),
  resetJobs: () => api.delete('/settings/reset-jobs'),
  getQBConfig: () => api.get('/settings/quickbooks'),
  saveQBConfig: (data) => api.post('/settings/quickbooks', data),
}

// ── QuickBooks ──────────────────────────────────────────
export const quickbooksAPI = {
  connect: () => api.get('/quickbooks/connect'),
  status: () => api.get('/quickbooks/status'),
  vendors: () => api.get('/quickbooks/vendors'),
  accounts: (type = 'Expense') => api.get('/quickbooks/accounts', { params: { account_type: type } }),
  allAccounts: () => api.get('/quickbooks/accounts/all'),
  saveDefaults: (data) => api.post('/quickbooks/defaults', data),
  sendBill: (invoiceId, vendorId, accountId) =>
    api.post(`/quickbooks/send-bill/${invoiceId}`, null, {
      params: { qbo_vendor_id: vendorId, qbo_account_id: accountId },
    }),
  disconnect: () => api.post('/quickbooks/disconnect'),
}

// ── Microsoft 365 ───────────────────────────────────────
export const microsoftAPI = {
  connect: () => api.get('/microsoft/connect'),
  status: () => api.get('/microsoft/status'),
  test: () => api.post('/microsoft/test'),
  disconnect: () => api.post('/microsoft/disconnect'),
  poll: () => api.post('/microsoft/poll'),
}

// ── Health ──────────────────────────────────────────────
export const healthAPI = {
  check: () => api.get('/health'),
}

// ── Junk Bin ────────────────────────────────────────────
export const junkAPI = {
  list: () => api.get('/junk'),
}

export default api
