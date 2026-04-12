import { useState, useEffect } from 'react'
import { payablesAPI } from '../services/api'
import { TrashIcon, PencilIcon, PlusIcon, CheckCircleIcon, XMarkIcon, LockClosedIcon, LockOpenIcon, ArrowUpTrayIcon, EyeIcon, EyeSlashIcon, DocumentIcon } from '@heroicons/react/24/outline'
import ContextMenu from '../components/ContextMenu'
import toast from 'react-hot-toast'

const emptyForm = {
  vendor_name: '',
  amount: '',
  due_date: '',
  invoice_number: '',
  is_permanent: false,
}

export default function PayablesPage() {
  const [payables, setPayables] = useState([])
  const [summary, setSummary] = useState({ total_outstanding: 0, total_overdue: 0 })
  const [bankBalance, setBankBalance] = useState(0)
  const [realBalance, setRealBalance] = useState(0)
  const [buffer, setBuffer] = useState(0)
  const [editingBalance, setEditingBalance] = useState(false)
  const [balanceInput, setBalanceInput] = useState('')
  const [editingBuffer, setEditingBuffer] = useState(false)
  const [bufferInput, setBufferInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingPayable, setEditingPayable] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [showImport, setShowImport] = useState(false)
  const [importFile, setImportFile] = useState(null)
  const [importing, setImporting] = useState(false)
  const [showPaymentModal, setShowPaymentModal] = useState(false)
  const [paymentTarget, setPaymentTarget] = useState(null)
  const [paymentForm, setPaymentForm] = useState({ payment_method: 'check', check_number: '', job_name: '', notes: '' })

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [payRes, realRes] = await Promise.all([
        payablesAPI.list(),
        payablesAPI.getRealBalance(),
      ])
      setPayables(payRes.data.items.filter(p => !p.is_permanent))
      setSummary({ total_outstanding: payRes.data.total_outstanding, total_overdue: payRes.data.total_overdue })
      setBankBalance(realRes.data.bank_balance)
      setBalanceInput(realRes.data.bank_balance?.toString() || '0')
      setBuffer(realRes.data.buffer || 0)
      setBufferInput((realRes.data.buffer || 0).toString())
      setRealBalance(realRes.data.real_available)
    } catch {
      toast.error('Failed to load payables')
    }
    setLoading(false)
    window.dispatchEvent(new Event('balance-changed'))
  }

  async function handleSaveBalance() {
    try {
      await payablesAPI.setBankBalance(parseFloat(balanceInput))
      const res = await payablesAPI.getRealBalance()
      setBankBalance(parseFloat(balanceInput))
      setBuffer(res.data.buffer || 0)
      setRealBalance(res.data.real_available)
      setEditingBalance(false)
      toast.success('Bank balance updated')
    } catch {
      toast.error('Failed to update')
    }
  }

  async function handleSaveBuffer() {
    try {
      const res = await payablesAPI.setBuffer(parseFloat(bufferInput))
      setBuffer(parseFloat(bufferInput))
      setRealBalance(res.data.real_available)
      setEditingBuffer(false)
      toast.success('Buffer updated')
    } catch {
      toast.error('Failed to update buffer')
    }
  }

  async function handleJunk(id) {
    try {
      await payablesAPI.junk(id)
      toast.success('Sent to junk')
      loadData()
    } catch {
      toast.error('Failed to junk payable')
    }
  }

  function openAddForm() {
    setForm(emptyForm)
    setEditingPayable(null)
    setShowForm(true)
  }

  function openEditForm(payable) {
    setForm({
      vendor_name: payable.vendor_name || '',
      amount: payable.amount?.toString() || '',
      due_date: payable.due_date ? new Date(payable.due_date).toISOString().slice(0, 10) : '',
      invoice_number: payable.invoice_number || '',
      is_permanent: payable.is_permanent || false,
    })
    setEditingPayable(payable)
    setShowForm(true)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const payload = {
      vendor_name: form.vendor_name,
      amount: parseFloat(form.amount),
      due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
      invoice_number: form.invoice_number || null,
      is_permanent: form.is_permanent,
    }
    try {
      if (editingPayable) {
        await payablesAPI.update(editingPayable.id, payload)
        toast.success('Payable updated')
      } else {
        await payablesAPI.create(payload)
        toast.success('Payable created')
      }
      setShowForm(false)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save payable')
    }
  }

  async function handleMarkPaid(id, paymentBody) {
    try {
      await payablesAPI.markPaid(id, paymentBody || undefined)
      toast.success(paymentBody ? 'Marked as paid & recorded payment' : 'Marked as paid')
      setShowPaymentModal(false)
      setPaymentTarget(null)
      loadData()
    } catch {
      toast.error('Failed to mark paid')
    }
  }

  function openPaymentModal(payable) {
    setPaymentTarget(payable)
    setPaymentForm({ payment_method: 'check', check_number: '', job_name: '', notes: '' })
    setShowPaymentModal(true)
  }

  const contextMenu = ContextMenu({
    items: [
      { label: 'Edit', icon: PencilIcon, onClick: (data) => openEditForm(data) },
      { label: 'Mark Paid', icon: CheckCircleIcon, onClick: (data) => openPaymentModal(data), hidden: (data) => data.is_permanent },
      { label: 'Send to Junk', icon: TrashIcon, danger: true, onClick: (data) => handleJunk(data.id) },
    ],
  })

  async function handleExport() {
    try {
      const res = await payablesAPI.exportExcel()
      const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `payables_${new Date().toISOString().slice(0, 10)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Excel exported')
    } catch {
      toast.error('Export failed')
    }
  }

  async function handleImport() {
    if (!importFile) {
      toast.error('Please select a CSV file')
      return
    }
    setImporting(true)
    try {
      const res = await payablesAPI.importCSV(importFile)
      toast.success(`Imported ${res.data.count} payables`)
      if (res.data.warnings?.length) {
        toast(res.data.warnings.join('\n'), { icon: '⚠️', duration: 8000 })
      }
      setShowImport(false)
      setImportFile(null)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Import failed')
    } finally {
      setImporting(false)
    }
  }

  async function handleDownloadTemplate() {
    try {
      const res = await payablesAPI.downloadTemplate()
      const blob = new Blob([res.data], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'payables_template.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Failed to download template')
    }
  }

  async function handleTogglePermanent(payable) {
    try {
      await payablesAPI.update(payable.id, { is_permanent: !payable.is_permanent })
      toast.success(payable.is_permanent ? 'Removed permanent flag' : 'Marked as permanent')
      loadData()
    } catch {
      toast.error('Failed to update')
    }
  }

  async function handleToggleCashflow(payable) {
    try {
      const res = await payablesAPI.toggleCashflow(payable.id)
      toast.success(res.data.included_in_cashflow ? 'Included in cash flow' : 'Excluded from cash flow')
      loadData()
    } catch {
      toast.error('Failed to toggle cash flow')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Payables Tracker</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={openAddForm}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-1"
          >
            <PlusIcon className="h-4 w-4" />
            Add Payable
          </button>
          <button
            onClick={() => setShowImport(true)}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 flex items-center gap-1"
          >
            <ArrowUpTrayIcon className="h-4 w-4" />
            Import CSV
          </button>
          <button
            onClick={handleExport}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700"
          >
            Export Excel
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Outstanding</p>
          <p className="text-2xl font-bold text-gray-100">
            ${summary.total_outstanding?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Overdue</p>
          <p className="text-2xl font-bold text-red-600">
            ${summary.total_overdue?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Bank Balance</p>
          {editingBalance ? (
            <div className="flex gap-2 mt-1">
              <input
                type="number"
                step="0.01"
                value={balanceInput}
                onChange={(e) => setBalanceInput(e.target.value)}
                className="w-32 px-2 py-1 border border-gray-600 bg-gray-700 text-gray-200 rounded text-sm"
              />
              <button onClick={handleSaveBalance} className="px-2 py-1 bg-blue-600 text-white text-xs rounded">Save</button>
              <button onClick={() => setEditingBalance(false)} className="px-2 py-1 text-xs text-gray-400">Cancel</button>
            </div>
          ) : (
            <p className="text-2xl font-bold text-gray-100 cursor-pointer" onClick={() => setEditingBalance(true)}>
              ${bankBalance?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              <span className="text-xs text-blue-400 ml-2">edit</span>
            </p>
          )}
        </div>
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Buffer</p>
          {editingBuffer ? (
            <div className="flex gap-2 mt-1">
              <input
                type="number"
                step="0.01"
                value={bufferInput}
                onChange={(e) => setBufferInput(e.target.value)}
                className="w-32 px-2 py-1 border border-gray-600 bg-gray-700 text-gray-200 rounded text-sm"
              />
              <button onClick={handleSaveBuffer} className="px-2 py-1 bg-blue-600 text-white text-xs rounded">Save</button>
              <button onClick={() => setEditingBuffer(false)} className="px-2 py-1 text-xs text-gray-400">Cancel</button>
            </div>
          ) : (
            <p className="text-2xl font-bold text-orange-400 cursor-pointer" onClick={() => setEditingBuffer(true)}>
              ${buffer?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              <span className="text-xs text-blue-400 ml-2">edit</span>
            </p>
          )}
        </div>
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Real Available</p>
          <p className={`text-2xl font-bold ${realBalance < 0 ? 'text-red-600' : 'text-green-600'}`}>
            ${realBalance?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
        </div>
      </div>

      {/* Payables Table */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 overflow-hidden overflow-x-auto">
        <table className="w-full min-w-[600px]">
          <thead className="bg-gray-900 border-b border-gray-700">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Vendor</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Invoice #</th>
              <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">Amount</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Due Date</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Status</th>
              <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {payables.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-10 text-gray-400">No payables yet</td>
              </tr>
            )}
            {payables.map((p) => {
              const isOverdue = p.status === 'overdue'
              const dueDate = p.due_date ? new Date(p.due_date) : null
              const daysUntil = dueDate ? Math.ceil((dueDate - new Date()) / 86400000) : null
              return (
                <tr key={p.id} className={`${isOverdue ? 'bg-red-900/20' : ''} ${!p.included_in_cashflow ? 'opacity-50' : ''} cursor-context-menu`} onContextMenu={(e) => contextMenu.show(e, p)}>
                  <td className="px-4 py-3 text-sm font-medium text-gray-200">
                    <button
                      onClick={() => handleToggleCashflow(p)}
                      className={`inline-flex items-center mr-1.5 -mt-0.5 ${p.included_in_cashflow ? 'text-green-400 hover:text-green-300' : 'text-gray-600 hover:text-green-400'} transition-colors`}
                      title={p.included_in_cashflow ? 'Click to exclude from cash flow' : 'Click to include in cash flow'}
                    >
                      {p.included_in_cashflow ? <EyeIcon className="h-4 w-4" /> : <EyeSlashIcon className="h-4 w-4" />}
                    </button>
                    <button
                      onClick={() => handleTogglePermanent(p)}
                      className={`inline-flex items-center mr-1 -mt-0.5 ${p.is_permanent ? 'text-orange-400 hover:text-orange-300' : 'text-gray-600 hover:text-orange-400'} transition-colors`}
                      title={p.is_permanent ? 'Click to remove permanent flag' : 'Click to mark as permanent'}
                    >
                      {p.is_permanent ? <LockClosedIcon className="h-4 w-4" /> : <LockOpenIcon className="h-4 w-4" />}
                    </button>
                    {p.vendor_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-400">{p.invoice_number || '—'}</td>
                  <td className="px-4 py-3 text-sm text-right font-medium text-gray-200">
                    ${parseFloat(p.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {dueDate ? (
                      <span>
                        {dueDate.toLocaleDateString()}
                        {daysUntil != null && (
                          <span className={`ml-2 text-xs ${daysUntil < 0 ? 'text-red-600' : daysUntil <= 7 ? 'text-yellow-600' : 'text-gray-400'}`}>
                            {daysUntil < 0 ? `${Math.abs(daysUntil)}d overdue` : `${daysUntil}d`}
                          </span>
                        )}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      isOverdue ? 'bg-red-900/50 text-red-400' : 'bg-yellow-900/50 text-yellow-400'
                    }`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {p.has_attachment && (
                        <button
                          onClick={async () => {
                            try {
                              const res = await payablesAPI.getAttachment(p.id)
                              const blob = new Blob([res.data])
                              const url = URL.createObjectURL(blob)
                              window.open(url, '_blank')
                            } catch {
                              toast.error('Failed to load attachment')
                            }
                          }}
                          className="p-1.5 text-gray-400 hover:text-cyan-400 transition-colors"
                          title="View invoice attachment"
                        >
                          <DocumentIcon className="h-4 w-4" />
                        </button>
                      )}
                      {p.status !== 'paid' && !p.is_permanent && (
                        <button
                          onClick={() => openPaymentModal(p)}
                          className="px-2 py-1 text-xs font-medium rounded-lg bg-emerald-900/50 text-emerald-400 hover:bg-emerald-800 transition-colors"
                          title="Mark as paid"
                        >
                          <CheckCircleIcon className="h-4 w-4 inline -mt-0.5 mr-0.5" />
                          Paid
                        </button>
                      )}
                      <button
                        onClick={() => openEditForm(p)}
                        className="p-1.5 text-gray-400 hover:text-blue-400 transition-colors"
                        title="Edit payable"
                      >
                        <PencilIcon className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleJunk(p.id)}
                        className="p-1.5 text-gray-400 hover:text-red-400 transition-colors"
                        title="Send to junk"
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {contextMenu.menu}

      {/* Add/Edit Payable Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-100">
                {editingPayable ? 'Edit Payable' : 'Add Payable'}
              </h3>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-white">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Vendor Name</label>
                <input
                  value={form.vendor_name}
                  onChange={(e) => setForm({ ...form, vendor_name: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Amount</label>
                  <input
                    type="number"
                    step="0.01"
                    value={form.amount}
                    onChange={(e) => setForm({ ...form, amount: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Due Date</label>
                  <input
                    type="date"
                    value={form.due_date}
                    onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Invoice # (optional)</label>
                <input
                  value={form.invoice_number}
                  onChange={(e) => setForm({ ...form, invoice_number: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_permanent"
                  checked={form.is_permanent}
                  onChange={(e) => setForm({ ...form, is_permanent: e.target.checked })}
                  className="h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600"
                />
                <label htmlFor="is_permanent" className="text-sm text-gray-400">Permanent (always outstanding, e.g. payroll)</label>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-gray-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
                >
                  {editingPayable ? 'Update Payable' : 'Add Payable'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import CSV Modal */}
      {showImport && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-100">Import Payables from CSV</h3>
              <button onClick={() => { setShowImport(false); setImportFile(null) }} className="text-gray-400 hover:text-white">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Upload CSV File</label>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setImportFile(e.target.files[0])}
                  className="w-full text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-600 file:text-white hover:file:bg-blue-700"
                />
                {importFile && (
                  <p className="text-xs text-gray-500 mt-1">{importFile.name} ({(importFile.size / 1024).toFixed(1)} KB)</p>
                )}
              </div>
              <div className="bg-gray-700/50 rounded-lg p-3">
                <p className="text-xs text-gray-400 mb-1">CSV columns: vendor_name, amount, due_date, status, is_permanent, notes</p>
                <button onClick={handleDownloadTemplate} className="text-xs text-blue-400 hover:text-blue-300 underline">
                  Download template CSV
                </button>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => { setShowImport(false); setImportFile(null) }} className="px-4 py-2 text-sm text-gray-400 hover:text-white">
                  Cancel
                </button>
                <button
                  onClick={handleImport}
                  disabled={!importFile || importing}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {importing ? 'Importing...' : 'Import'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Mark Paid Modal */}
      {showPaymentModal && paymentTarget && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-100">Mark as Paid</h3>
              <button onClick={() => setShowPaymentModal(false)} className="text-gray-400 hover:text-white">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-gray-400 mb-4">
              <span className="text-gray-200 font-medium">{paymentTarget.vendor_name}</span> &mdash; ${paymentTarget.amount?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </p>
            <p className="text-xs text-gray-500 mb-4">
              Optionally record this as a payment to track in Payments Out (outstanding checks/ACH).
            </p>
            <div className="space-y-3 mb-6">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Payment Method</label>
                  <select
                    value={paymentForm.payment_method}
                    onChange={(e) => setPaymentForm({ ...paymentForm, payment_method: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="check">Check</option>
                    <option value="ach">ACH</option>
                    <option value="debit">Debit</option>
                    <option value="online">Online</option>
                    <option value="wire">Wire</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Check/Ref #</label>
                  <input
                    value={paymentForm.check_number}
                    onChange={(e) => setPaymentForm({ ...paymentForm, check_number: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                    placeholder="Optional"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Job Name</label>
                <input
                  value={paymentForm.job_name}
                  onChange={(e) => setPaymentForm({ ...paymentForm, job_name: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  placeholder="Optional"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Notes</label>
                <input
                  value={paymentForm.notes}
                  onChange={(e) => setPaymentForm({ ...paymentForm, notes: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  placeholder="Optional"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowPaymentModal(false)}
                className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleMarkPaid(paymentTarget.id)}
                className="px-4 py-2 text-sm bg-gray-600 hover:bg-gray-500 text-white rounded-lg transition-colors"
              >
                Mark Paid Only
              </button>
              <button
                onClick={() => handleMarkPaid(paymentTarget.id, {
                  payment_method: paymentForm.payment_method,
                  check_number: paymentForm.check_number || null,
                  job_name: paymentForm.job_name || null,
                  notes: paymentForm.notes || null,
                })}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                Mark Paid &amp; Record Payment
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
