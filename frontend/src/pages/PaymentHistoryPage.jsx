import { useState, useEffect, useCallback } from 'react'
import { paymentsOutAPI } from '../services/api'
import toast from 'react-hot-toast'
import {
  ArrowPathIcon,
  MagnifyingGlassIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'

const TYPE_BADGES = {
  payment_out: { label: 'Payment Out', color: 'bg-blue-900/50 text-blue-300' },
  payable: { label: 'Payable', color: 'bg-green-900/50 text-green-300' },
  bill: { label: 'Bill', color: 'bg-purple-900/50 text-purple-300' },
}

export default function PaymentHistoryPage() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [totalAmount, setTotalAmount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [page, setPage] = useState(1)
  const perPage = 50

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, per_page: perPage }
      if (search) params.search = search
      if (startDate) params.start_date = startDate
      if (endDate) params.end_date = endDate
      const res = await paymentsOutAPI.allHistory(params)
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
      setTotalAmount(res.data.total_amount || 0)
    } catch {
      toast.error('Failed to load payment history')
    } finally {
      setLoading(false)
    }
  }, [search, startDate, endDate, page])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1)
  }, [search, startDate, endDate])

  const fmt = (n) => `$${(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
  const totalPages = Math.ceil(total / perPage)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Payment History</h1>
        <div className="text-sm text-gray-400">
          {total} payments &middot; {fmt(totalAmount)} total
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px]">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search vendor, reference, job, notes..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <ArrowPathIcon className="h-8 w-8 animate-spin text-gray-500" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 text-gray-500">No payments found</div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-gray-700">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/50 text-gray-400 text-left">
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">Vendor</th>
                  <th className="px-4 py-3 font-medium text-right">Amount</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Method</th>
                  <th className="px-4 py-3 font-medium">Reference</th>
                  <th className="px-4 py-3 font-medium">Job</th>
                  <th className="px-4 py-3 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {items.map((item, idx) => {
                  const badge = TYPE_BADGES[item.type] || TYPE_BADGES.payment_out
                  return (
                    <tr key={`${item.type}-${item.id}-${idx}`} className="hover:bg-gray-800/30">
                      <td className="px-4 py-3 whitespace-nowrap text-gray-300">
                        {item.date ? new Date(item.date).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3 text-gray-200 font-medium">{item.vendor}</td>
                      <td className="px-4 py-3 text-right text-gray-200 font-mono">
                        {fmt(item.amount)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${badge.color}`}>
                          {badge.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-400 capitalize">{item.method || '—'}</td>
                      <td className="px-4 py-3 text-gray-400">{item.reference || '—'}</td>
                      <td className="px-4 py-3 text-gray-400">{item.job_name || '—'}</td>
                      <td className="px-4 py-3 text-gray-500 max-w-[200px] truncate">{item.notes || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-gray-500">
                Page {page} of {totalPages}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                >
                  <ChevronLeftIcon className="h-4 w-4" /> Prev
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                >
                  Next <ChevronRightIcon className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
