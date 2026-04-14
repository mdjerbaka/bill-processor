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
  CheckIcon,
  XCircleIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  BanknotesIcon,
} from '@heroicons/react/24/outline'

export default function ReceivablesPage() {
  const [checks, setChecks] = useState([])
  const [agingData, setAgingData] = useState(null)
  const [totalInvoiced, setTotalInvoiced] = useState(0)
  const [totalReceivables, setTotalReceivables] = useState(0)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingCheck, setEditingCheck] = useState(null)
  const [form, setForm] = useState({ job_name: '', invoiced_amount: '', collect: false, sent_date: '', due_date: '', notes: '' })
  const [showImport, setShowImport] = useState(false)
  const [importFile, setImportFile] = useState(null)
  const [importing, setImporting] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [expandedCustomers, setExpandedCustomers] = useState(new Set())
  const [showPaid, setShowPaid] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [listRes, agingRes] = await Promise.all([
        receivablesAPI.list(),
        receivablesAPI.getAgingSummary(),
      ])
      setChecks(listRes.data.items || [])
      setTotalInvoiced(listRes.data.total_invoiced || 0)
      setTotalReceivables(listRes.data.total_receivables || 0)
      setAgingData(agingRes.data)
      // Auto-expand all customers
      if (agingRes.data?.customers) {
        setExpandedCustomers(new Set(agingRes.data.customers.map(c => c.customer_name)))
      }
    } catch {
      toast.error('Failed to load receivables')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  function toggleCustomer(name) {
    setExpandedCustomers(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  function openAddForm() {
    setForm({ job_name: '', invoiced_amount: '', collect: false, sent_date: '', due_date: '', notes: '' })
    setEditingCheck(null)
    setShowForm(true)
  }

  function openEditForm(check) {
    setForm({
      job_name: check.job_name,
      invoiced_amount: check.invoiced_amount.toString(),
      collect: check.collect,
      sent_date: check.sent_date ? check.sent_date.split('T')[0] : '',
      due_date: check.due_date ? check.due_date.split('T')[0] : '',
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
      sent_date: form.sent_date ? new Date(form.sent_date).toISOString() : null,
      due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
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
    if (!confirm('Delete this receivable?')) return
    try {
      await receivablesAPI.delete(id)
      toast.success('Deleted')
      loadData()
    } catch { toast.error('Failed to delete') }
  }

  async function handleDeleteAll() {
    if (!confirm('Delete ALL receivable checks? This cannot be undone.')) return
    try {
      const res = await receivablesAPI.deleteAll()
      toast.success(res.data.detail)
      loadData()
    } catch { toast.error('Failed to delete all') }
  }

  async function handleToggleCollect(id) {
    try {
      const res = await receivablesAPI.toggleCollect(id)
      setChecks(prev => prev.map(c => c.id === id ? { ...c, collect: res.data.collect } : c))
      loadData()
    } catch { toast.error('Failed to toggle collect') }
  }

  async function handleMarkPaid(id) {
    try {
      await receivablesAPI.markPaid(id)
      toast.success('Marked as paid')
      loadData()
    } catch { toast.error('Failed to mark as paid') }
  }

  async function handleMarkUnpaid(id) {
    try {
      await receivablesAPI.markUnpaid(id)
      toast.success('Marked as outstanding')
      loadData()
    } catch { toast.error('Failed to mark as outstanding') }
  }

  async function handleUpdateNotes(id, notes) {
    try {
      await receivablesAPI.update(id, { notes })
      loadData()
    } catch { toast.error('Failed to update notes') }
  }

  async function handleImport() {
    if (!importFile) { toast.error('Please select a CSV file'); return }
    setImporting(true)
    try {
      const res = await receivablesAPI.importCSV(importFile)
      toast.success(res.data.detail)
      setShowImport(false)
      setImportFile(null)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Import failed')
    } finally { setImporting(false) }
  }

  async function handleSyncQuickbooks() {
    setSyncing(true)
    try {
      const res = await receivablesAPI.syncQuickbooks()
      const { created, updated, skipped } = res.data
      toast.success(`QB Sync: ${created} added, ${updated} updated, ${skipped} unchanged`)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'QuickBooks sync failed')
    } finally { setSyncing(false) }
  }

  const fmt = (n) => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`

  // Filter aging data to hide/show paid items
  const filteredAgingData = agingData ? {
    ...agingData,
    customers: agingData.customers.map(c => ({
      ...c,
      invoices: showPaid ? c.invoices : c.invoices.filter(inv => inv.status !== 'paid'),
      total: showPaid ? c.total : c.invoices.filter(inv => inv.status !== 'paid').reduce((s, inv) => s + inv.invoiced_amount, 0),
    })).filter(c => c.invoices.length > 0),
    grand_total: showPaid ? agingData.grand_total : agingData.customers.reduce((s, c) => s + c.invoices.filter(inv => inv.status !== 'paid').reduce((s2, inv) => s2 + inv.invoiced_amount, 0), 0),
  } : null

  const paidCount = agingData ? agingData.customers.reduce((s, c) => s + c.invoices.filter(inv => inv.status === 'paid').length, 0) : 0

  // Parse invoice number from job_name (everything after #)
  function parseInvoiceNum(jobName) {
    if (!jobName || !jobName.includes('#')) return null
    return '#' + jobName.split('#').slice(1).join('#')
  }

  // Parse job description (everything before #)
  function parseJobDesc(jobName) {
    if (!jobName) return '—'
    if (!jobName.includes('#')) return jobName
    return jobName.split('#')[0].trim() || jobName
  }

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
        <h1 className="text-2xl font-bold">A/R Aging Summary</h1>
        <div className="flex gap-2">
          {paidCount > 0 && (
            <button onClick={() => setShowPaid(!showPaid)} className={`flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg transition-colors ${showPaid ? 'bg-green-900/50 text-green-300 hover:bg-green-800' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'}`}>
              <BanknotesIcon className="h-4 w-4" /> {showPaid ? 'Hide' : 'Show'} Paid ({paidCount})
            </button>
          )}
          {checks.length > 0 && (
            <button onClick={handleDeleteAll} className="flex items-center gap-1.5 px-3 py-2 text-sm bg-red-900/50 hover:bg-red-800 text-red-300 rounded-lg transition-colors">
              <TrashIcon className="h-4 w-4" /> Delete All
            </button>
          )}
          <button onClick={handleSyncQuickbooks} disabled={syncing} className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 flex items-center gap-1 disabled:opacity-50">
            <ArrowPathIcon className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Syncing...' : 'Sync from QuickBooks'}
          </button>
          <button onClick={() => setShowImport(true)} className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 flex items-center gap-1">
            <ArrowUpTrayIcon className="h-4 w-4" /> Import CSV
          </button>
          <button onClick={openAddForm} className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
            <PlusIcon className="h-4 w-4" /> Add Entry
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Customers</p>
          <p className="text-2xl font-bold text-gray-100 mt-1">{agingData?.customers?.length || 0}</p>
        </div>
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Total Invoiced</p>
          <p className="text-2xl font-bold text-blue-400 mt-1">{fmt(totalInvoiced)}</p>
        </div>
        <div className="bg-gray-800 rounded-xl border border-green-700/50 p-5 ring-1 ring-green-500/20">
          <p className="text-sm text-green-400">Total Receivables</p>
          <p className="text-xs text-gray-500 mt-0.5">Sum of "Collect" entries</p>
          <p className="text-2xl font-bold text-green-400 mt-1">{fmt(totalReceivables)}</p>
        </div>
      </div>

      {/* A/R Aging Table */}
      <div className="bg-gray-800 rounded-xl border border-gray-700">
        <div className="p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-gray-100">A/R Aging Summary</h2>
        </div>
        {!filteredAgingData?.customers?.length ? (
          <p className="text-gray-500 text-sm text-center py-8">No receivables yet. Sync from QuickBooks or add manually.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="px-4 py-3 font-medium w-8"></th>
                  <th className="px-4 py-3 font-medium">Customer / Invoice</th>
                  <th className="px-4 py-3 font-medium">Invoice #</th>
                  <th className="px-4 py-3 font-medium text-right">Amount</th>
                  <th className="px-4 py-3 font-medium text-center">Status</th>
                  <th className="px-4 py-3 font-medium text-center">Collect</th>
                  <th className="px-4 py-3 font-medium">Sent Date</th>
                  <th className="px-4 py-3 font-medium">Due Date</th>
                  <th className="px-4 py-3 font-medium">Notes</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredAgingData.customers.map((customer) => (
                  <CustomerGroup
                    key={customer.customer_name}
                    customer={customer}
                    expanded={expandedCustomers.has(customer.customer_name)}
                    onToggle={() => toggleCustomer(customer.customer_name)}
                    onEdit={openEditForm}
                    onDelete={handleDelete}
                    onToggleCollect={handleToggleCollect}
                    onUpdateNotes={handleUpdateNotes}
                    onMarkPaid={handleMarkPaid}
                    onMarkUnpaid={handleMarkUnpaid}
                    fmt={fmt}
                    parseInvoiceNum={parseInvoiceNum}
                    parseJobDesc={parseJobDesc}
                  />
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-gray-600 bg-gray-900/50">
                  <td colSpan={3} className="px-4 py-3 font-bold text-gray-200">Grand Total</td>
                  <td className="px-4 py-3 text-right font-bold text-blue-400">{fmt(filteredAgingData.grand_total)}</td>
                  <td colSpan={6}></td>
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
              <h3 className="text-lg font-semibold text-gray-100">{editingCheck ? 'Edit Receivable' : 'Add Receivable'}</h3>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-white"><XMarkIcon className="h-5 w-5" /></button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Customer / Job Name</label>
                <input value={form.job_name} onChange={(e) => setForm({ ...form, job_name: e.target.value })} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g. Ashley Holdback #1234" required />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Amount ($)</label>
                <input type="number" step="0.01" min="0" value={form.invoiced_amount} onChange={(e) => setForm({ ...form, invoiced_amount: e.target.value })} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" required />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Sent Date</label>
                  <input type="date" value={form.sent_date} onChange={(e) => setForm({ ...form, sent_date: e.target.value })} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Due Date</label>
                  <input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Notes</label>
                <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" />
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input type="checkbox" checked={form.collect} onChange={(e) => setForm({ ...form, collect: e.target.checked })} className="rounded bg-gray-700 border-gray-600" />
                Collect (include in Total Receivables)
              </label>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
                <button type="submit" className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg">{editingCheck ? 'Update' : 'Add'}</button>
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
              <h3 className="text-lg font-semibold text-gray-100">Import Receivables</h3>
              <button onClick={() => setShowImport(false)} className="text-gray-400 hover:text-white"><XMarkIcon className="h-5 w-5" /></button>
            </div>
            <div className="space-y-4">
              <p className="text-sm text-gray-400">Upload a CSV with columns: job_name, invoiced_amount, collect (yes/no), notes</p>
              <input type="file" accept=".csv" onChange={(e) => setImportFile(e.target.files[0] || null)} className="w-full text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-600 file:text-white hover:file:bg-blue-700" />
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => { setShowImport(false); setImportFile(null) }} className="px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
              <button onClick={handleImport} disabled={!importFile || importing} className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg">{importing ? 'Importing...' : 'Import'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function CustomerGroup({ customer, expanded, onToggle, onEdit, onDelete, onToggleCollect, onUpdateNotes, onMarkPaid, onMarkUnpaid, fmt, parseInvoiceNum, parseJobDesc }) {
  const isOverdue = (dateStr) => dateStr && new Date(dateStr) < new Date()
  const [editingNotesId, setEditingNotesId] = useState(null)
  const [notesInput, setNotesInput] = useState('')

  return (
    <>
      {/* Customer header row */}
      <tr className="bg-gray-900/60 cursor-pointer hover:bg-gray-900/80" onClick={onToggle}>
        <td className="px-4 py-2.5">
          {expanded
            ? <ChevronDownIcon className="h-4 w-4 text-gray-400" />
            : <ChevronRightIcon className="h-4 w-4 text-gray-400" />
          }
        </td>
        <td className="px-4 py-2.5 font-semibold text-gray-200" colSpan={2}>
          {customer.customer_name}
          <span className="text-xs text-gray-500 ml-2">({customer.invoices.length} invoice{customer.invoices.length !== 1 ? 's' : ''})</span>
        </td>
        <td className="px-4 py-2.5 text-right font-semibold text-gray-200">{fmt(customer.total)}</td>
        <td colSpan={6}></td>
      </tr>
      {/* Invoice rows */}
      {expanded && customer.invoices.map((inv) => {
        const isPaid = inv.status === 'paid'
        return (
        <tr key={inv.id} className={`border-b border-gray-700/30 hover:bg-gray-700/20 ${isPaid ? 'opacity-60' : ''}`}>
          <td className="px-4 py-2"></td>
          <td className={`px-4 py-2 pl-10 ${isPaid ? 'text-gray-500 line-through' : 'text-gray-300'}`}>{parseJobDesc(inv.job_name)}</td>
          <td className={`px-4 py-2 text-xs ${isPaid ? 'text-gray-500 line-through' : 'text-gray-400'}`}>{parseInvoiceNum(inv.job_name) || '—'}</td>
          <td className={`px-4 py-2 text-right ${isPaid ? 'text-gray-500 line-through' : 'text-gray-200'}`}>{fmt(inv.invoiced_amount)}</td>
          <td className="px-4 py-2 text-center">
            {isPaid ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-900/50 text-green-400">
                <CheckIcon className="h-3 w-3" /> Paid
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-900/50 text-yellow-400">
                Open
              </span>
            )}
          </td>
          <td className="px-4 py-2 text-center">
            <button
              onClick={(e) => { e.stopPropagation(); onToggleCollect(inv.id) }}
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors ${
                inv.collect ? 'bg-green-900/50 text-green-400 hover:bg-green-800/60' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              {inv.collect ? <><CheckIcon className="h-3 w-3" /> Yes</> : <><XCircleIcon className="h-3 w-3" /> No</>}
            </button>
          </td>
          <td className="px-4 py-2 text-gray-400 text-xs">{inv.sent_date ? new Date(inv.sent_date).toLocaleDateString() : '—'}</td>
          <td className={`px-4 py-2 text-xs ${!isPaid && isOverdue(inv.due_date) ? 'text-red-400 font-medium' : 'text-gray-400'}`}>
            {inv.due_date ? new Date(inv.due_date).toLocaleDateString() : '—'}
          </td>
          <td className="px-4 py-2 text-gray-400 text-xs max-w-[200px]">
            {editingNotesId === inv.id ? (
              <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                <input
                  autoFocus
                  value={notesInput}
                  onChange={(e) => setNotesInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { onUpdateNotes(inv.id, notesInput); setEditingNotesId(null) }
                    if (e.key === 'Escape') setEditingNotesId(null)
                  }}
                  className="w-full bg-gray-700 border border-blue-500 text-gray-200 rounded px-2 py-0.5 text-xs"
                />
                <button onClick={() => { onUpdateNotes(inv.id, notesInput); setEditingNotesId(null) }} className="text-green-400 hover:text-green-300 text-xs px-1">✓</button>
                <button onClick={() => setEditingNotesId(null)} className="text-gray-500 hover:text-gray-300 text-xs px-1">✕</button>
              </div>
            ) : (
              <span
                className="cursor-pointer hover:text-blue-400 truncate block"
                onClick={(e) => { e.stopPropagation(); setEditingNotesId(inv.id); setNotesInput(inv.notes || '') }}
                title="Click to edit notes"
              >
                {inv.notes || '—'}
              </span>
            )}
          </td>
          <td className="px-4 py-2 text-right">
            <div className="flex items-center justify-end gap-1.5">
              {isPaid ? (
                <button onClick={() => onMarkUnpaid(inv.id)} className="p-1 text-gray-400 hover:text-yellow-400" title="Mark as outstanding">
                  <XCircleIcon className="h-3.5 w-3.5" />
                </button>
              ) : (
                <button onClick={() => onMarkPaid(inv.id)} className="p-1 text-gray-400 hover:text-green-400" title="Mark as paid">
                  <BanknotesIcon className="h-3.5 w-3.5" />
                </button>
              )}
              <button onClick={() => onEdit(inv)} className="p-1 text-gray-400 hover:text-blue-400"><PencilIcon className="h-3.5 w-3.5" /></button>
              <button onClick={() => onDelete(inv.id)} className="p-1 text-gray-400 hover:text-red-400"><TrashIcon className="h-3.5 w-3.5" /></button>
            </div>
          </td>
        </tr>
        )
      })}
    </>
  )
}
