import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { invoicesAPI } from '../services/api'
import { TrashIcon } from '@heroicons/react/24/outline'
import ContextMenu from '../components/ContextMenu'
import toast from 'react-hot-toast'

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

export default function InvoicesReviewPage() {
  const [invoices, setInvoices] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  const loadInvoices = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const res = await invoicesAPI.list({ page, page_size: 50, status: 'needs_review' })
      setInvoices(res.data.items)
      setTotal(res.data.total)
    } catch {}
    if (!silent) setLoading(false)
  }, [page])

  useEffect(() => { loadInvoices() }, [loadInvoices])
  useEffect(() => {
    const interval = setInterval(() => loadInvoices(true), 10000)
    return () => clearInterval(interval)
  }, [loadInvoices])

  const totalPages = Math.ceil(total / 50)

  async function handleJunk(id) {
    try {
      await invoicesAPI.junk(id)
      toast.success('Sent to junk')
      loadInvoices()
    } catch { toast.error('Failed to junk invoice') }
  }

  const contextMenu = ContextMenu({
    items: [
      { label: 'Send to Junk', icon: TrashIcon, danger: true, onClick: (data) => handleJunk(data.id) },
    ],
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Invoices to be Reviewed</h1>
        <span className="text-sm text-gray-400">{total} pending review</span>
      </div>

      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 overflow-hidden overflow-x-auto">
        <table className="w-full min-w-[700px]">
          <thead className="bg-gray-900 border-b border-gray-700">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Vendor</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Invoice #</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Amount</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Due Date</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Notes</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">Confidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {loading ? (
              <tr><td colSpan={7} className="px-6 py-12 text-center text-gray-400">Loading...</td></tr>
            ) : invoices.length === 0 ? (
              <tr><td colSpan={7} className="px-6 py-12 text-center text-gray-400">No invoices need review</td></tr>
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
                  <td className="px-6 py-4 text-sm text-gray-400 max-w-xs truncate">{inv.notes || '—'}</td>
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

        {totalPages > 1 && (
          <div className="flex items-center justify-between px-6 py-3 border-t border-gray-700 bg-gray-900">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1 text-sm border border-gray-600 text-gray-300 rounded disabled:opacity-50">Previous</button>
            <span className="text-sm text-gray-400">Page {page} of {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="px-3 py-1 text-sm border border-gray-600 text-gray-300 rounded disabled:opacity-50">Next</button>
          </div>
        )}
      </div>
      {contextMenu.menu}
    </div>
  )
}
