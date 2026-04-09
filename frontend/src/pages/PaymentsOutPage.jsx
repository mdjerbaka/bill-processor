import { useState, useEffect, useCallback } from 'react'
import { paymentsOutAPI, quickbooksAPI } from '../services/api'
import toast from 'react-hot-toast'
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  XMarkIcon,
  ArrowPathIcon,
  ArrowUpTrayIcon,
  BanknotesIcon,
  CheckCircleIcon,
  ChevronUpDownIcon,
  ChevronUpIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline'

const PAYMENT_METHODS = [
  { value: 'check', label: 'Check' },
  { value: 'ach', label: 'ACH' },
  { value: 'debit', label: 'Debit' },
  { value: 'online', label: 'Online' },
  { value: 'wire', label: 'Wire' },
  { value: 'other', label: 'Other' },
]

const emptyForm = {
  payment_method: 'check',
  check_number: '',
  vendor_name: '',
  job_name: '',
  amount: '',
  payment_date: new Date().toISOString().slice(0, 10),
  notes: '',
}

export default function PaymentsOutPage() {
  const [tab, setTab] = useState('outstanding')
  const [payments, setPayments] = useState([])
  const [total, setTotal] = useState(0)
  const [totalOutstanding, setTotalOutstanding] = useState(0)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingPayment, setEditingPayment] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [showImport, setShowImport] = useState(false)
  const [importFile, setImportFile] = useState(null)
  const [importing, setImporting] = useState(false)
  const [sortColumn, setSortColumn] = useState('payment_date')
  const [sortDirection, setSortDirection] = useState('desc')
  const [selectedPayments, setSelectedPayments] = useState(new Set())
  const [syncing, setSyncing] = useState(false)

  // History date filters
  const [historyStart, setHistoryStart] = useState('')
  const [historyEnd, setHistoryEnd] = useState('')

  function handleSort(column) {
    if (sortColumn === column) {
      setSortDirection(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortColumn(column)
      setSortDirection('asc')
    }
  }

  function SortIcon({ column }) {
    if (sortColumn !== column) return <ChevronUpDownIcon className="h-3.5 w-3.5 text-gray-600 ml-1 inline" />
    return sortDirection === 'asc'
      ? <ChevronUpIcon className="h-3.5 w-3.5 text-blue-400 ml-1 inline" />
      : <ChevronDownIcon className="h-3.5 w-3.5 text-blue-400 ml-1 inline" />
  }

  const sortedPayments = [...payments].sort((a, b) => {
    const dir = sortDirection === 'asc' ? 1 : -1
    switch (sortColumn) {
      case 'payment_date': return dir * ((a.payment_date || '').localeCompare(b.payment_date || ''))
      case 'vendor_name': return dir * ((a.vendor_name || '').localeCompare(b.vendor_name || ''))
      case 'job_name': return dir * ((a.job_name || '').localeCompare(b.job_name || ''))
      case 'amount': return dir * ((a.amount || 0) - (b.amount || 0))
      case 'check_number': return dir * ((a.check_number || '').localeCompare(b.check_number || ''))
      case 'payment_method': return dir * ((a.payment_method || '').localeCompare(b.payment_method || ''))
      default: return 0
    }
  })

  const loadData = useCallback(async () => {
    try {
      if (tab === 'outstanding') {
        const res = await paymentsOutAPI.list()
        setPayments(res.data.items || [])
        setTotal(res.data.total || 0)
        setTotalOutstanding(res.data.total_outstanding || 0)
      } else {
        const res = await paymentsOutAPI.history(historyStart || undefined, historyEnd || undefined)
        setPayments(res.data.items || [])
        setTotal(res.data.total || 0)
        setTotalOutstanding(res.data.total_outstanding || 0)
      }
    } catch {
      toast.error('Failed to load payments')
    } finally {
      setLoading(false)
    }
  }, [tab, historyStart, historyEnd])

  useEffect(() => {
    setLoading(true)
    setSelectedPayments(new Set())
    loadData()
  }, [loadData])

  function openAddForm() {
    setForm(emptyForm)
    setEditingPayment(null)
    setShowForm(true)
  }

  function openEditForm(payment) {
    setForm({
      payment_method: payment.payment_method,
      check_number: payment.check_number || '',
      vendor_name: payment.vendor_name,
      job_name: payment.job_name || '',
      amount: payment.amount.toString(),
      payment_date: payment.payment_date,
      notes: payment.notes || '',
    })
    setEditingPayment(payment)
    setShowForm(true)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const payload = {
      ...form,
      amount: parseFloat(form.amount),
      check_number: form.check_number || null,
      job_name: form.job_name || null,
      notes: form.notes || null,
    }
    try {
      if (editingPayment) {
        await paymentsOutAPI.update(editingPayment.id, payload)
        toast.success('Payment updated')
      } else {
        await paymentsOutAPI.create(payload)
        toast.success('Payment added')
      }
      setShowForm(false)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save')
    }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this payment record?')) return
    try {
      await paymentsOutAPI.delete(id)
      toast.success('Deleted')
      loadData()
    } catch {
      toast.error('Failed to delete')
    }
  }

  async function handleMarkCleared(id) {
    try {
      await paymentsOutAPI.markCleared(id)
      toast.success('Marked as cleared')
      loadData()
    } catch {
      toast.error('Failed to mark cleared')
    }
  }

  async function handleBulkDelete() {
    if (selectedPayments.size === 0) return
    if (!confirm(`Delete ${selectedPayments.size} selected payment(s)?`)) return
    try {
      await Promise.all([...selectedPayments].map(id => paymentsOutAPI.delete(id)))
      toast.success(`Deleted ${selectedPayments.size} payments`)
      setSelectedPayments(new Set())
      loadData()
    } catch {
      toast.error('Failed to delete selected')
    }
  }

  async function handleBulkMarkCleared() {
    if (selectedPayments.size === 0) return
    try {
      await Promise.all([...selectedPayments].map(id => paymentsOutAPI.markCleared(id)))
      toast.success(`Marked ${selectedPayments.size} as cleared`)
      setSelectedPayments(new Set())
      loadData()
    } catch {
      toast.error('Failed to mark cleared')
    }
  }

  async function handleImport() {
    if (!importFile) {
      toast.error('Please select a CSV file')
      return
    }
    setImporting(true)
    try {
      const res = await paymentsOutAPI.importCSV(importFile)
      toast.success(res.data.detail)
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

  async function handleSyncQB() {
    setSyncing(true)
    try {
      const res = await quickbooksAPI.syncPayments()
      const { payables_marked, payments_cleared, checked } = res.data
      if (payables_marked === 0 && payments_cleared === 0) {
        toast(`Checked ${checked} bills in QuickBooks — nothing new to clear`, { icon: '✓' })
      } else {
        toast.success(`Synced from QuickBooks: ${payables_marked} payable(s) marked paid, ${payments_cleared} payment(s) cleared`)
        loadData()
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'QuickBooks sync failed')
    } finally {
      setSyncing(false)
    }
  }

  async function handleDownloadTemplate() {
    try {
      const res = await paymentsOutAPI.downloadTemplate()
      const blob = new Blob([res.data], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'payments_out_template.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Failed to download template')
    }
  }

  function toggleSelectAll() {
    if (selectedPayments.size === sortedPayments.length) {
      setSelectedPayments(new Set())
    } else {
      setSelectedPayments(new Set(sortedPayments.map(p => p.id)))
    }
  }

  function toggleSelect(id) {
    setSelectedPayments(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const fmt = (n) => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <ArrowPathIcon className="h-8 w-8 animate-spin text-gray-500" />
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Payments Out</h1>
        <div className="flex gap-2">
          <button
            onClick={handleSyncQB}
            disabled={syncing}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 flex items-center gap-1"
          >
            <ArrowPathIcon className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Syncing…' : 'Sync QB Payments'}
          </button>
          <button
            onClick={() => setShowImport(true)}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 flex items-center gap-1"
          >
            <ArrowUpTrayIcon className="h-4 w-4" />
            Import CSV
          </button>
          <button
            onClick={openAddForm}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            Add Payment
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">
                {tab === 'outstanding' ? 'Outstanding Payments' : 'Cleared Payments'}
              </p>
              <p className="text-2xl font-bold text-gray-100 mt-1">{payments.length}</p>
            </div>
            <div className="p-2.5 rounded-lg bg-gray-700/50">
              <BanknotesIcon className="h-5 w-5 text-gray-400" />
            </div>
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl border border-amber-700/50 p-5 ring-1 ring-amber-500/20">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-amber-400">Total Outstanding</p>
              <p className="text-xs text-gray-500 mt-0.5">Not yet cleared by bank</p>
              <p className="text-2xl font-bold text-amber-400 mt-1">{fmt(totalOutstanding)}</p>
            </div>
            <div className="p-2.5 rounded-lg bg-amber-900/30">
              <BanknotesIcon className="h-5 w-5 text-amber-400" />
            </div>
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">
                {tab === 'outstanding' ? 'Total Paid Out' : 'Total Cleared'}
              </p>
              <p className="text-2xl font-bold text-orange-400 mt-1">{fmt(total)}</p>
            </div>
            <div className="p-2.5 rounded-lg bg-gray-700/50">
              <BanknotesIcon className="h-5 w-5 text-orange-400" />
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4">
        <button
          onClick={() => setTab('outstanding')}
          className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
            tab === 'outstanding' ? 'bg-amber-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}
        >
          Outstanding
        </button>
        <button
          onClick={() => setTab('history')}
          className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
            tab === 'history' ? 'bg-green-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}
        >
          Payment History
        </button>
      </div>

      {/* History Date Filters */}
      {tab === 'history' && (
        <div className="flex items-center gap-3 mb-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">From</label>
            <input
              type="date"
              value={historyStart}
              onChange={(e) => setHistoryStart(e.target.value)}
              className="px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-200 rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">To</label>
            <input
              type="date"
              value={historyEnd}
              onChange={(e) => setHistoryEnd(e.target.value)}
              className="px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-200 rounded-lg text-sm"
            />
          </div>
          {(historyStart || historyEnd) && (
            <button
              onClick={() => { setHistoryStart(''); setHistoryEnd('') }}
              className="mt-4 px-3 py-1.5 text-xs text-gray-400 hover:text-white"
            >
              Clear
            </button>
          )}
        </div>
      )}

      {/* Table */}
      <div className="bg-gray-800 rounded-xl border border-gray-700">
        <div className="p-6 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">
            {tab === 'outstanding' ? `Outstanding Payments (${payments.length})` : `Payment History (${payments.length})`}
          </h2>
          <div className="flex gap-2">
            {selectedPayments.size > 0 && tab === 'outstanding' && (
              <button
                onClick={handleBulkMarkCleared}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-900/50 hover:bg-green-800 text-green-300 rounded-lg transition-colors"
              >
                <CheckCircleIcon className="h-4 w-4" />
                Clear Selected ({selectedPayments.size})
              </button>
            )}
            {selectedPayments.size > 0 && (
              <button
                onClick={handleBulkDelete}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-red-900/50 hover:bg-red-800 text-red-300 rounded-lg transition-colors"
              >
                <TrashIcon className="h-4 w-4" />
                Delete Selected ({selectedPayments.size})
              </button>
            )}
          </div>
        </div>

        {payments.length === 0 ? (
          <p className="text-gray-500 text-sm text-center py-8">
            {tab === 'outstanding'
              ? 'No outstanding payments. Add a payment or import from CSV.'
              : 'No cleared payments found for this period.'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="px-6 pb-3 pt-4 pr-2">
                    <input
                      type="checkbox"
                      checked={sortedPayments.length > 0 && selectedPayments.size === sortedPayments.length}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                    />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('payment_method')}>
                    Method<SortIcon column="payment_method" />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('check_number')}>
                    Check/Ref #<SortIcon column="check_number" />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('vendor_name')}>
                    To Who<SortIcon column="vendor_name" />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('job_name')}>
                    For? Job?<SortIcon column="job_name" />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('payment_date')}>
                    Date<SortIcon column="payment_date" />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium text-right cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('amount')}>
                    Amount<SortIcon column="amount" />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium">Notes</th>
                  {tab === 'history' && <th className="px-4 pb-3 pt-4 font-medium">Cleared</th>}
                  <th className="px-6 pb-3 pt-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedPayments.map((payment) => (
                  <tr key={payment.id} className={`border-b border-gray-700/50 hover:bg-gray-700/30 ${selectedPayments.has(payment.id) ? 'bg-blue-900/20' : ''}`}>
                    <td className="px-6 py-3 pr-2">
                      <input
                        type="checkbox"
                        checked={selectedPayments.has(payment.id)}
                        onChange={() => toggleSelect(payment.id)}
                        className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        payment.payment_method === 'check' ? 'bg-blue-900/50 text-blue-300' :
                        payment.payment_method === 'ach' ? 'bg-purple-900/50 text-purple-300' :
                        payment.payment_method === 'online' ? 'bg-cyan-900/50 text-cyan-300' :
                        payment.payment_method === 'wire' ? 'bg-amber-900/50 text-amber-300' :
                        'bg-gray-700 text-gray-300'
                      }`}>
                        {payment.payment_method?.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-300 font-mono text-xs">
                      {payment.check_number || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-200">{payment.vendor_name}</p>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">
                      {payment.job_name || '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-300 text-xs">
                      {payment.payment_date}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-200">
                      {fmt(payment.amount)}
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs max-w-[150px] truncate">
                      {payment.notes || '—'}
                    </td>
                    {tab === 'history' && (
                      <td className="px-4 py-3 text-green-400 text-xs">
                        {payment.cleared_at ? new Date(payment.cleared_at).toLocaleDateString() : '—'}
                      </td>
                    )}
                    <td className="px-6 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {tab === 'outstanding' && (
                          <button
                            onClick={() => handleMarkCleared(payment.id)}
                            className="p-1.5 text-gray-400 hover:text-green-400 transition-colors"
                            title="Mark Cleared"
                          >
                            <CheckCircleIcon className="h-4 w-4" />
                          </button>
                        )}
                        <button
                          onClick={() => openEditForm(payment)}
                          className="p-1.5 text-gray-400 hover:text-blue-400 transition-colors"
                          title="Edit"
                        >
                          <PencilIcon className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(payment.id)}
                          className="p-1.5 text-gray-400 hover:text-red-400 transition-colors"
                          title="Delete"
                        >
                          <TrashIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-gray-600 bg-gray-800/80">
                  <td className="px-6 py-3" colSpan={6}>
                    <span className="font-semibold text-orange-400">Total Paid Out</span>
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-orange-400">
                    {fmt(total)}
                  </td>
                  <td colSpan={tab === 'history' ? 3 : 2}></td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {/* Add/Edit Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-100">
                {editingPayment ? 'Edit Payment' : 'Add Payment'}
              </h3>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-white">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Payment Method</label>
                  <select
                    value={form.payment_method}
                    onChange={(e) => setForm({ ...form, payment_method: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  >
                    {PAYMENT_METHODS.map(m => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Check/Ref #</label>
                  <input
                    value={form.check_number}
                    onChange={(e) => setForm({ ...form, check_number: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                    placeholder="e.g. 1234"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">To Who (Vendor)</label>
                <input
                  value={form.vendor_name}
                  onChange={(e) => setForm({ ...form, vendor_name: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  placeholder="e.g. ABC Supply"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">For? Job?</label>
                <input
                  value={form.job_name}
                  onChange={(e) => setForm({ ...form, job_name: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  placeholder="e.g. Smith Residence Roof"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Amount ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.amount}
                    onChange={(e) => setForm({ ...form, amount: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Date</label>
                  <input
                    type="date"
                    value={form.payment_date}
                    onChange={(e) => setForm({ ...form, payment_date: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Notes</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  rows={2}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  placeholder="Optional notes..."
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                >
                  {editingPayment ? 'Update' : 'Add Payment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {showImport && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-100">Import Payments</h3>
              <button onClick={() => setShowImport(false)} className="text-gray-400 hover:text-white">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <p className="text-sm text-gray-400">
                Upload a CSV with columns: <span className="text-gray-200">vendor_name</span>, <span className="text-gray-200">amount</span>, <span className="text-gray-200">payment_date</span>, <span className="text-gray-200">check_number</span>, <span className="text-gray-200">job_name</span>, <span className="text-gray-200">payment_method</span>
              </p>
              <p className="text-xs text-gray-500">
                Also supports column aliases: "to_who", "for_job", "date", "check_or_online"
              </p>
              <div>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setImportFile(e.target.files[0])}
                  className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-gray-700 file:text-gray-200 hover:file:bg-gray-600"
                />
              </div>
              <div className="flex justify-between items-center pt-2">
                <button
                  onClick={handleDownloadTemplate}
                  className="text-sm text-blue-400 hover:text-blue-300"
                >
                  Download Template CSV
                </button>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowImport(false)}
                    className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleImport}
                    disabled={importing || !importFile}
                    className="px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50"
                  >
                    {importing ? 'Importing...' : 'Import'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
