import { useState, useEffect, useCallback } from 'react'
import { receivablesAPI } from '../services/api'
import toast from 'react-hot-toast'
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  XMarkIcon,
  ArrowPathIcon,
  ArrowUpTrayIcon,
  BanknotesIcon,
  CheckIcon,
  XCircleIcon,
  ChevronUpDownIcon,
  ChevronUpIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline'

export default function ReceivablesPage() {
  const [checks, setChecks] = useState([])
  const [totalInvoiced, setTotalInvoiced] = useState(0)
  const [totalReceivables, setTotalReceivables] = useState(0)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingCheck, setEditingCheck] = useState(null)
  const [form, setForm] = useState({ job_name: '', invoiced_amount: '', collect: false, notes: '' })
  const [showImport, setShowImport] = useState(false)
  const [importFile, setImportFile] = useState(null)
  const [importing, setImporting] = useState(false)
  const [sortColumn, setSortColumn] = useState('job_name')
  const [sortDirection, setSortDirection] = useState('asc')
  const [selectedChecks, setSelectedChecks] = useState(new Set())

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

  const sortedChecks = [...checks].sort((a, b) => {
    const dir = sortDirection === 'asc' ? 1 : -1
    switch (sortColumn) {
      case 'job_name': return dir * (a.job_name || '').localeCompare(b.job_name || '')
      case 'invoiced_amount': return dir * ((a.invoiced_amount || 0) - (b.invoiced_amount || 0))
      case 'collect': return dir * ((a.collect ? 1 : 0) - (b.collect ? 1 : 0))
      default: return 0
    }
  })

  const loadData = useCallback(async () => {
    try {
      const res = await receivablesAPI.list()
      setChecks(res.data.items || [])
      setTotalInvoiced(res.data.total_invoiced || 0)
      setTotalReceivables(res.data.total_receivables || 0)
    } catch {
      toast.error('Failed to load receivable checks')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  function openAddForm() {
    setForm({ job_name: '', invoiced_amount: '', collect: false, notes: '' })
    setEditingCheck(null)
    setShowForm(true)
  }

  function openEditForm(check) {
    setForm({
      job_name: check.job_name,
      invoiced_amount: check.invoiced_amount.toString(),
      collect: check.collect,
      notes: check.notes || '',
    })
    setEditingCheck(check)
    setShowForm(true)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const payload = {
      ...form,
      invoiced_amount: parseFloat(form.invoiced_amount),
    }
    try {
      if (editingCheck) {
        await receivablesAPI.update(editingCheck.id, payload)
        toast.success('Receivable updated')
      } else {
        await receivablesAPI.create(payload)
        toast.success('Receivable added')
      }
      setShowForm(false)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save')
    }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this receivable check?')) return
    try {
      await receivablesAPI.delete(id)
      toast.success('Deleted')
      loadData()
    } catch {
      toast.error('Failed to delete')
    }
  }

  async function handleDeleteAll() {
    if (!confirm('Delete ALL receivable checks? This cannot be undone.')) return
    try {
      const res = await receivablesAPI.deleteAll()
      toast.success(res.data.detail)
      loadData()
    } catch {
      toast.error('Failed to delete all')
    }
  }

  async function handleToggleCollect(id) {
    try {
      const res = await receivablesAPI.toggleCollect(id)
      setChecks(prev => prev.map(c =>
        c.id === id ? { ...c, collect: res.data.collect } : c
      ))
      loadData()
    } catch {
      toast.error('Failed to toggle collect')
    }
  }

  async function handleImport() {
    if (!importFile) {
      toast.error('Please select a CSV file')
      return
    }
    setImporting(true)
    try {
      const res = await receivablesAPI.importCSV(importFile)
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

  async function handleBulkDelete() {
    if (selectedChecks.size === 0) return
    if (!confirm(`Delete ${selectedChecks.size} selected receivable(s)?`)) return
    try {
      await Promise.all([...selectedChecks].map(id => receivablesAPI.delete(id)))
      toast.success(`Deleted ${selectedChecks.size} receivables`)
      setSelectedChecks(new Set())
      loadData()
    } catch {
      toast.error('Failed to delete selected')
    }
  }

  function toggleSelectAll() {
    if (selectedChecks.size === sortedChecks.length) {
      setSelectedChecks(new Set())
    } else {
      setSelectedChecks(new Set(sortedChecks.map(c => c.id)))
    }
  }

  function toggleSelect(id) {
    setSelectedChecks(prev => {
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
        <h1 className="text-2xl font-bold">Receivable Checks</h1>
        <div className="flex gap-2">
          {checks.length > 0 && (
            <button
              onClick={handleDeleteAll}
              className="flex items-center gap-1.5 px-3 py-2 text-sm bg-red-900/50 hover:bg-red-800 text-red-300 rounded-lg transition-colors"
            >
              <TrashIcon className="h-4 w-4" />
              Delete All
            </button>
          )}
          <button
            onClick={() => setShowImport(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors"
          >
            <ArrowUpTrayIcon className="h-4 w-4" />
            Import CSV
          </button>
          <button
            onClick={openAddForm}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            Add Job
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Open Jobs</p>
              <p className="text-2xl font-bold text-gray-100 mt-1">{checks.length}</p>
            </div>
            <div className="p-2.5 rounded-lg bg-gray-700/50">
              <BanknotesIcon className="h-5 w-5 text-gray-400" />
            </div>
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Total Invoiced</p>
              <p className="text-2xl font-bold text-blue-400 mt-1">{fmt(totalInvoiced)}</p>
            </div>
            <div className="p-2.5 rounded-lg bg-gray-700/50">
              <BanknotesIcon className="h-5 w-5 text-blue-400" />
            </div>
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl border border-green-700/50 p-5 ring-1 ring-green-500/20">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-green-400">Total Receivables</p>
              <p className="text-xs text-gray-500 mt-0.5">Sum of "Collect Yes" entries</p>
              <p className="text-2xl font-bold text-green-400 mt-1">{fmt(totalReceivables)}</p>
            </div>
            <div className="p-2.5 rounded-lg bg-green-900/30">
              <BanknotesIcon className="h-5 w-5 text-green-400" />
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-gray-800 rounded-xl border border-gray-700">
        <div className="p-6 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">Open Jobs ({checks.length})</h2>
          {selectedChecks.size > 0 && (
            <button
              onClick={handleBulkDelete}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-red-900/50 hover:bg-red-800 text-red-300 rounded-lg transition-colors"
            >
              <TrashIcon className="h-4 w-4" />
              Delete Selected ({selectedChecks.size})
            </button>
          )}
        </div>

        {checks.length === 0 ? (
          <p className="text-gray-500 text-sm text-center py-8">
            No receivable checks yet. Add open jobs or import from CSV.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="px-6 pb-3 pt-4 pr-2">
                    <input
                      type="checkbox"
                      checked={sortedChecks.length > 0 && selectedChecks.size === sortedChecks.length}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                    />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('job_name')}>
                    Open Jobs<SortIcon column="job_name" />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium text-right cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('invoiced_amount')}>
                    Current Invoiced Amount<SortIcon column="invoiced_amount" />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium text-center cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('collect')}>
                    Collect<SortIcon column="collect" />
                  </th>
                  <th className="px-4 pb-3 pt-4 font-medium">Notes</th>
                  <th className="px-6 pb-3 pt-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedChecks.map((check) => (
                  <tr key={check.id} className={`border-b border-gray-700/50 hover:bg-gray-700/30 ${selectedChecks.has(check.id) ? 'bg-blue-900/20' : ''}`}>
                    <td className="px-6 py-3 pr-2">
                      <input
                        type="checkbox"
                        checked={selectedChecks.has(check.id)}
                        onChange={() => toggleSelect(check.id)}
                        className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-200">{check.job_name}</p>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-200">
                      {fmt(check.invoiced_amount)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => handleToggleCollect(check.id)}
                        className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                          check.collect
                            ? 'bg-green-900/50 text-green-400 hover:bg-green-800/60'
                            : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                        }`}
                      >
                        {check.collect ? (
                          <>
                            <CheckIcon className="h-3.5 w-3.5" />
                            Yes
                          </>
                        ) : (
                          <>
                            <XCircleIcon className="h-3.5 w-3.5" />
                            No
                          </>
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs max-w-[200px] truncate">
                      {check.notes || '—'}
                    </td>
                    <td className="px-6 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => openEditForm(check)}
                          className="p-1.5 text-gray-400 hover:text-blue-400 transition-colors"
                          title="Edit"
                        >
                          <PencilIcon className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(check.id)}
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
                  <td className="px-6 py-3" colSpan={2}>
                    <span className="font-semibold text-gray-300">Totals</span>
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-blue-400">
                    {fmt(totalInvoiced)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="font-bold text-green-400">{fmt(totalReceivables)}</span>
                  </td>
                  <td colSpan={2}></td>
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
                {editingCheck ? 'Edit Receivable' : 'Add Receivable Check'}
              </h3>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-white">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Job Name</label>
                <input
                  value={form.job_name}
                  onChange={(e) => setForm({ ...form, job_name: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  placeholder="e.g. Ashley Holdback valley repair"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Invoiced Amount ($)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.invoiced_amount}
                  onChange={(e) => setForm({ ...form, invoiced_amount: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  required
                />
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
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input
                  type="checkbox"
                  checked={form.collect}
                  onChange={(e) => setForm({ ...form, collect: e.target.checked })}
                  className="rounded bg-gray-700 border-gray-600"
                />
                Collect Yes (include in Total Receivables)
              </label>
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
                  {editingCheck ? 'Update' : 'Add'}
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
              <h3 className="text-lg font-semibold text-gray-100">Import Receivable Checks</h3>
              <button onClick={() => setShowImport(false)} className="text-gray-400 hover:text-white">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <p className="text-sm text-gray-400">
                Upload a CSV with columns: <span className="text-gray-200">job_name</span>, <span className="text-gray-200">invoiced_amount</span>, <span className="text-gray-200">collect</span> (yes/no), <span className="text-gray-200">notes</span>
              </p>
              <p className="text-xs text-gray-500">
                Also supports column names from the spreadsheet: "Open Jobs", "Current Invoiced Amount", "Collect Yes"
              </p>
              <div>
                <label className="block text-sm text-gray-400 mb-2">Select CSV File</label>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setImportFile(e.target.files[0] || null)}
                  className="w-full text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-600 file:text-white hover:file:bg-blue-700 file:cursor-pointer file:transition-colors"
                />
              </div>
              {importFile && (
                <p className="text-xs text-gray-400">
                  Selected: <span className="text-gray-200">{importFile.name}</span> ({(importFile.size / 1024).toFixed(1)} KB)
                </p>
              )}
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => { setShowImport(false); setImportFile(null) }}
                className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleImport}
                disabled={!importFile || importing}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
              >
                {importing ? 'Importing...' : 'Import'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
