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
  changePassword: (data) => api.post('/auth/change-password', data),
  me: () => api.get('/auth/me'),
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
  create: (data) => api.post('/invoices', data),
  update: (id, data) => api.put(`/invoices/${id}`, data),
  approve: (id) => api.post(`/invoices/${id}/approve`),
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
  create: (data) => api.post('/payables', data),
  update: (id, data) => api.put(`/payables/${id}`, data),
  markPaid: (id, body) => api.post(`/payables/${id}/mark-paid`, body || null),
  junk: (id) => api.post(`/payables/${id}/junk`),
  restore: (id) => api.post(`/payables/${id}/restore`),
  toggleCashflow: (id) => api.post(`/payables/${id}/toggle-cashflow`),
  setBankBalance: (balance) => api.post('/payables/bank-balance', { bank_balance: balance }),
  setBuffer: (buffer) => api.post('/payables/buffer', { buffer }),
  getRealBalance: () => api.get('/payables/real-balance'),
  getCombinedTotal: () => api.get('/payables/combined-total'),
  exportExcel: () => api.get('/payables/export', { responseType: 'blob' }),
  importCSV: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/payables/import-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadTemplate: () => api.get('/payables/template-csv', { responseType: 'blob' }),
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
  listFolders: () => api.get('/microsoft/folders'),
  getFolderSetting: () => api.get('/microsoft/folder-setting'),
  saveFolderSetting: (data) => api.post('/microsoft/folder-setting', data),
  getTargetMailbox: () => api.get('/microsoft/target-mailbox'),
  saveTargetMailbox: (data) => api.post('/microsoft/target-mailbox', data),
  adminStatus: (userId) => api.get('/microsoft/admin/status', { params: { user_id: userId } }),
}

// ── Health ──────────────────────────────────────────────
export const healthAPI = {
  check: () => api.get('/health'),
}

// ── Junk Bin ────────────────────────────────────────────
export const junkAPI = {
  list: () => api.get('/junk'),
}

// ── Recurring Bills ─────────────────────────────────────
export const recurringBillsAPI = {
  list: (includeInactive = false) => api.get('/recurring-bills', { params: { include_inactive: includeInactive } }),
  create: (data) => api.post('/recurring-bills', data),
  update: (id, data) => api.put(`/recurring-bills/${id}`, data),
  delete: (id) => api.delete(`/recurring-bills/${id}`),
  deleteAll: () => api.delete('/recurring-bills/all'),
  listOccurrences: (params) => api.get('/recurring-bills/occurrences', { params }),
  skip: (occurrenceId) => api.post(`/recurring-bills/occurrences/${occurrenceId}/skip`),
  markPaid: (occurrenceId, body) => api.post(`/recurring-bills/occurrences/${occurrenceId}/mark-paid`, body || null),
  toggleCashflow: (occurrenceId) => api.post(`/recurring-bills/occurrences/${occurrenceId}/toggle-cashflow`),
  bulkDeleteOccurrences: (ids) => api.post('/recurring-bills/occurrences/bulk-delete', { ids }),
  getCashFlow: () => api.get('/recurring-bills/cash-flow'),
  getCalendar: (startDate, endDate) => api.get('/recurring-bills/calendar', { params: { start_date: startDate, end_date: endDate } }),
  bulkImport: (bills) => api.post('/recurring-bills/import', bills),
  setOutstandingChecks: (amount) => api.post('/recurring-bills/outstanding-checks', { amount }),
  importCSV: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/recurring-bills/import-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadTemplate: () => api.get('/recurring-bills/template-csv', { responseType: 'blob' }),
}

// ── Notifications ───────────────────────────────────────
export const notificationsAPI = {
  list: (includeRead = false) => api.get('/notifications', { params: { include_read: includeRead } }),
  count: () => api.get('/notifications/count'),
  markRead: (id) => api.post(`/notifications/${id}/read`),
  markAllRead: () => api.post('/notifications/read-all'),
}

// ── Receivable Checks ───────────────────────────────────
export const receivablesAPI = {
  list: () => api.get('/receivables'),
  create: (data) => api.post('/receivables', data),
  update: (id, data) => api.put(`/receivables/${id}`, data),
  delete: (id) => api.delete(`/receivables/${id}`),
  deleteAll: () => api.delete('/receivables/all'),
  toggleCollect: (id) => api.post(`/receivables/${id}/toggle-collect`),
  getTotals: () => api.get('/receivables/totals'),
  syncQuickbooks: () => api.post('/receivables/sync-quickbooks'),
  getAgingSummary: () => api.get('/receivables/aging-summary'),
  importCSV: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/receivables/import-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

// ── Payments Out ────────────────────────────────────────
export const paymentsOutAPI = {
  list: () => api.get('/payments-out'),
  history: (startDate, endDate) => api.get('/payments-out/history', { params: { start_date: startDate, end_date: endDate } }),
  create: (data) => api.post('/payments-out', data),
  update: (id, data) => api.put(`/payments-out/${id}`, data),
  delete: (id) => api.delete(`/payments-out/${id}`),
  markCleared: (id) => api.post(`/payments-out/${id}/mark-cleared`),
  totalOutstanding: () => api.get('/payments-out/total-outstanding'),
  allHistory: (params) => api.get('/payments-out/all-history', { params }),
  importCSV: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/payments-out/import-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadTemplate: () => api.get('/payments-out/template-csv', { responseType: 'blob' }),
}

// ── Vendor Accounts ────────────────────────────────────────
export const vendorAccountsAPI = {
  list: () => api.get('/vendor-accounts'),
  create: (data) => api.post('/vendor-accounts', data),
  update: (id, data) => api.put(`/vendor-accounts/${id}`, data),
  delete: (id) => api.delete(`/vendor-accounts/${id}`),
}

export default api
