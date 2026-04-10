import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { invoicesAPI } from '../services/api'
import { TrashIcon, PlusIcon, XMarkIcon } from '@heroicons/react/24/outline'
import ContextMenu from '../components/ContextMenu'
import toast from 'react-hot-toast'

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'needs_review', label: 'Needs Review' },
  { value: 'auto_matched', label: 'Auto Matched' },
  { value: 'approved', label: 'Approved' },
  { value: 'sent_to_qb', label: 'Sent to QB' },
  { value: 'paid', label: 'Paid' },
]

const statusColors = {
  pending: 'bg-gray-700 text-gray-300',
  extracted: 'bg-blue-900/50 text-blue-400',
  needs_review: 'bg-yellow-900/50 text-yellow-400',
  auto_matched: 'bg-green-900/50 text-green-400',
  approved: 'bg-emerald-900/50 text-emerald-400',
  sent_to_qb: 'bg-purple-900/50 text-purple-400',
  paid: 'bg-gray-700 text-gray-400',
  failed: 'bg-red-900/50 text-red-400',
}

export default function InvoiceListPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [invoices, setInvoices] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '')
  const [vendorFilter, setVendorFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [invoiceForm, setInvoiceForm] = useState({
    vendor_name: '', invoice_number: '', total_amount: '', due_date: '', notes: '', attachment: null,
  })
  const [editingNotesId, setEditingNotesId] = useState(null)
  const [notesInput, setNotesInput] = useState('')

  const handleUpdateNotes = async (id, notes) => {
    try {
      await invoicesAPI.update(id, { notes })
      setInvoices(prev => prev.map(i => i.id === id ? { ...i, notes } : i))
    } catch { toast.error('Failed to update notes') }
  }

  const loadInvoices = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const params = { page, page_size: 20 }
      if (statusFilter) params.status = statusFilter
      if (vendorFilter) params.vendor = vendorFilter
      const res = await invoicesAPI.list(params)
      setInvoices(res.data.items)
      setTotal(res.data.total)
    } catch {}
    if (!silent) setLoading(false)
  }, [page, statusFilter, vendorFilter])

  useEffect(() => {
    loadInvoices()
  }, [loadInvoices])

  // Auto-refresh every 10 seconds — silent so no loading flash
  useEffect(() => {
    const interval = setInterval(() => {
      loadInvoices(true)
    }, 10000)
    return () => clearInterval(interval)
  }, [loadInvoices])

  const totalPages = Math.ceil(total / 20)

  async function handleJunk(id) {
    try {
      await invoicesAPI.junk(id)
      toast.success('Sent to junk')
      loadInvoices()
    } catch {
      toast.error('Failed to junk invoice')
    }
  }

  const contextMenu = ContextMenu({
    items: [
      { label: 'Send to Junk', icon: TrashIcon, danger: true, onClick: (data) => handleJunk(data.id) },
    ],
  })

  async function handleCreateInvoice(e) {
    e.preventDefault()
    const payload = {
      vendor_name: invoiceForm.vendor_name,
      invoice_number: invoiceForm.invoice_number || null,
      total_amount: invoiceForm.total_amount ? parseFloat(invoiceForm.total_amount) : null,
      due_date: invoiceForm.due_date ? new Date(invoiceForm.due_date).toISOString() : null,
      notes: invoiceForm.notes || null,
    }
    try {
      const res = await invoicesAPI.create(payload)
      // Upload attachment if provided
      if (invoiceForm.attachment) {
        try {
          await invoicesAPI.uploadAttachment(res.data.id, invoiceForm.attachment)
        } catch {
          toast.error('Invoice created but attachment upload failed')
        }
      }
      toast.success('Invoice created')
      setShowForm(false)
      setInvoiceForm({ vendor_name: '', invoice_number: '', total_amount: '', due_date: '', notes: '', attachment: null })
      loadInvoices()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create invoice')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Invoices</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-1"
          >
            <PlusIcon className="h-4 w-4" />
            Add Invoice
          </button>
          <span className="text-sm text-gray-400">{total} total</span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          className="px-3 py-2 border border-gray-600 bg-gray-800 text-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Search vendor..."
          value={vendorFilter}
          onChange={(e) => { setVendorFilter(e.target.value); setPage(1) }}
          className="px-3 py-2 border border-gray-600 bg-gray-800 text-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 w-64"
        />
      </div>

      {/* Table */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 overflow-hidden overflow-x-auto">
        <table className="w-full min-w-[700px]">
          <thead className="bg-gray-900 border-b border-gray-700">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Vendor</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Invoice #</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Amount</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Due Date</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Job</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Notes</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Confidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {loading ? (
              <tr>
                <td colSpan={8} className="px-6 py-12 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : invoices.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-6 py-12 text-center text-gray-400">
                  No invoices found
                </td>
              </tr>
            ) : (
              invoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-gray-700/50 transition-colors cursor-context-menu" onContextMenu={(e) => contextMenu.show(e, { id: inv.id })}>
                  <td className="px-6 py-4">
                    <Link to={`/invoices/${inv.id}`} className="text-blue-400 hover:underline font-medium text-sm">
                      {inv.vendor_name || 'Unknown'}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">{inv.invoice_number || '—'}</td>
                  <td className="px-6 py-4 text-sm font-medium text-gray-200">
                    {inv.total_amount != null ? `$${inv.total_amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {inv.due_date ? new Date(inv.due_date).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">{inv.job_name || '—'}</td>
                  <td className="px-6 py-4 text-sm text-gray-400 max-w-[200px]">
                    {editingNotesId === inv.id ? (
                      <div className="flex items-center gap-1">
                        <input autoFocus value={notesInput} onChange={(e) => setNotesInput(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') { handleUpdateNotes(inv.id, notesInput); setEditingNotesId(null) } if (e.key === 'Escape') setEditingNotesId(null) }}
                          className="w-full bg-gray-700 border border-blue-500 text-gray-200 rounded px-2 py-0.5 text-xs" />
                        <button onClick={() => { handleUpdateNotes(inv.id, notesInput); setEditingNotesId(null) }} className="text-green-400 text-xs px-1">✓</button>
                        <button onClick={() => setEditingNotesId(null)} className="text-gray-500 text-xs px-1">✕</button>
                      </div>
                    ) : (
                      <span className="cursor-pointer hover:text-blue-400 truncate block" onClick={() => { setEditingNotesId(inv.id); setNotesInput(inv.notes || '') }} title="Click to edit notes">{inv.notes || '—'}</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[inv.status] || ''}`}>
                      {inv.status.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {inv.confidence_score != null ? (
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-600 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${
                              inv.confidence_score >= 0.8 ? 'bg-green-500' :
                              inv.confidence_score >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${inv.confidence_score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-400">{Math.round(inv.confidence_score * 100)}%</span>
                      </div>
                    ) : '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-6 py-3 border-t border-gray-700 bg-gray-900">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 text-sm border border-gray-600 text-gray-300 rounded disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-gray-400">Page {page} of {totalPages}</span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1 text-sm border border-gray-600 text-gray-300 rounded disabled:opacity-50"
            >
              Next
            </button>
          </div>
        )}
      </div>
      {contextMenu.menu}

      {/* Add Invoice Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-100">Add Invoice</h3>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-white">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleCreateInvoice} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Vendor Name</label>
                <input
                  value={invoiceForm.vendor_name}
                  onChange={(e) => setInvoiceForm({ ...invoiceForm, vendor_name: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Invoice # (optional)</label>
                <input
                  value={invoiceForm.invoice_number}
                  onChange={(e) => setInvoiceForm({ ...invoiceForm, invoice_number: e.target.value })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Amount</label>
                  <input
                    type="number"
                    step="0.01"
                    value={invoiceForm.total_amount}
                    onChange={(e) => setInvoiceForm({ ...invoiceForm, total_amount: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Due Date</label>
                  <input
                    type="date"
                    value={invoiceForm.due_date}
                    onChange={(e) => setInvoiceForm({ ...invoiceForm, due_date: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Notes (optional)</label>
                <textarea
                  value={invoiceForm.notes}
                  onChange={(e) => setInvoiceForm({ ...invoiceForm, notes: e.target.value })}
                  rows={2}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  placeholder="Follow-up notes, payment instructions, etc."
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Invoice Attachment (optional)</label>
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.bmp,.xlsx,.xls,.csv"
                  onChange={(e) => setInvoiceForm({ ...invoiceForm, attachment: e.target.files[0] || null })}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:bg-blue-600 file:text-white hover:file:bg-blue-700"
                />
                {invoiceForm.attachment && (
                  <p className="text-xs text-gray-500 mt-1">{invoiceForm.attachment.name}</p>
                )}
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
                  Add Invoice
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
