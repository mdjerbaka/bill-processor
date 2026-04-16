import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { invoicesAPI, payablesAPI, healthAPI, settingsAPI, recurringBillsAPI, quickbooksAPI, receivablesAPI, vendorAccountsAPI, paymentsOutAPI } from '../services/api'
import toast from 'react-hot-toast'
import OverdueAlertBanner from '../components/OverdueAlertBanner'
import {
  InboxIcon,
  CurrencyDollarIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  BanknotesIcon,
} from '@heroicons/react/24/outline'

const fmt = (v) => parseFloat(v || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })

export default function DashboardPage() {
  const [stats, setStats] = useState({
    needsReview: 0,
    combinedOutstanding: 0,
    totalReceivables: 0,
    realBalance: null,
    billsDueSoon: 0,
    billsOverdue: 0,
    nextBill: null,
    overdueBills: [],
    paymentsOutTotal: 0,
  })
  const [health, setHealth] = useState(null)
  const [qbStatus, setQbStatus] = useState(null)
  const [recentInvoices, setRecentInvoices] = useState([])
  const [topVendors, setTopVendors] = useState([])
  const [polling, setPolling] = useState(false)

  useEffect(() => {
    loadDashboard()
  }, [])

  // Auto-refresh dashboard every 15 seconds
  useEffect(() => {
    const interval = setInterval(loadDashboard, 15000)
    return () => clearInterval(interval)
  }, [])

  async function loadDashboard() {
    try {
      const [invoicesRes, balanceRes, healthRes, cashFlowRes, qbRes, combinedRes, receivablesTotalsRes, vendorsRes, paymentsOutRes] = await Promise.allSettled([
        invoicesAPI.list({ page: 1, page_size: 15 }),
        payablesAPI.getRealBalance(),
        healthAPI.check(),
        recurringBillsAPI.getCashFlow(),
        quickbooksAPI.status(),
        payablesAPI.getCombinedTotal(),
        receivablesAPI.getTotals(),
        vendorAccountsAPI.list(),
        paymentsOutAPI.totalOutstanding(),
      ])

      if (invoicesRes.status === 'fulfilled') {
        const data = invoicesRes.value.data
        setRecentInvoices(data.items)
      }

      if (combinedRes.status === 'fulfilled') {
        setStats((s) => ({
          ...s,
          combinedOutstanding: combinedRes.value.data.combined_total || 0,
        }))
      }

      if (receivablesTotalsRes.status === 'fulfilled') {
        setStats((s) => ({
          ...s,
          totalReceivables: receivablesTotalsRes.value.data.total_receivables || 0,
        }))
      }

      if (balanceRes.status === 'fulfilled') {
        setStats((s) => ({ ...s, realBalance: balanceRes.value.data }))
      }

      if (healthRes.status === 'fulfilled') {
        setHealth(healthRes.value.data)
      }

      if (qbRes.status === 'fulfilled') {
        setQbStatus(qbRes.value.data)
      }

      if (cashFlowRes.status === 'fulfilled') {
        const cf = cashFlowRes.value.data
        setStats((s) => ({
          ...s,
          billsDueSoon: (cf.bills_due_soon || []).length,
          billsOverdue: (cf.overdue_bills || []).length,
          nextBill: (cf.bills_due_soon || [])[0] || null,
          overdueBills: cf.overdue_bills || [],
        }))
      }

      if (vendorsRes.status === 'fulfilled') {
        const items = vendorsRes.value.data.items || []
        // Top 8 vendors by amount (descending)
        const sorted = [...items].sort((a, b) => (b.amount || 0) - (a.amount || 0)).slice(0, 8)
        setTopVendors(sorted)
      }

      if (paymentsOutRes.status === 'fulfilled') {
        setStats((s) => ({
          ...s,
          paymentsOutTotal: paymentsOutRes.value.data.total_outstanding || 0,
        }))
      }

      // Count needs_review
      try {
        const reviewRes = await invoicesAPI.list({ status: 'needs_review', page_size: 1 })
        setStats((s) => ({ ...s, needsReview: reviewRes.data.total }))
      } catch {}
    } catch {}
  }

  async function handlePollNow() {
    setPolling(true)
    try {
      const res = await settingsAPI.pollEmails()
      const count = res.data?.new_emails ?? 0
      toast.success(count > 0 ? `Found ${count} new email(s)` : 'No new emails')
      loadDashboard()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Poll failed')
    } finally {
      setPolling(false)
    }
  }

  const rb = stats.realBalance || {}

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      {/* Overdue Alert Banner */}
      <OverdueAlertBanner
        overdueBills={stats.overdueBills}
        onMarkPaid={async (occId) => {
          try {
            await recurringBillsAPI.markPaid(occId)
            toast.success('Marked as paid')
            loadDashboard()
          } catch {
            toast.error('Failed to mark as paid')
          }
        }}
      />

      {/* Real Balance Breakdown + Summary Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Real Balance Breakdown */}
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-100">Real Balance</h2>
            <p className={`text-2xl font-bold ${(rb.real_available || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${fmt(rb.real_available)}
            </p>
          </div>
          <div className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Bank</span>
              <span className="text-gray-200 font-medium">${fmt(rb.bank_balance)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-green-400">+ Receivables to be Collected</span>
              <span className="text-green-400 font-medium">${fmt(rb.total_receivables)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-red-400">- Payments Out</span>
              <span className="text-red-400 font-medium">${fmt(rb.total_payments_out)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-red-400">- Recurring Bills Turned On</span>
              <span className="text-red-400 font-medium">${fmt(rb.total_included_bills)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-red-400">- Payables/Invoices Turned On</span>
              <span className="text-red-400 font-medium">${fmt(rb.total_included_payables)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-red-400">- Locked Bills</span>
              <span className="text-red-400 font-medium">${fmt(rb.total_locked_bills)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-red-400">- Vendor Accounts</span>
              <span className="text-red-400 font-medium">${fmt(rb.total_included_vendors)}</span>
            </div>
          </div>
        </div>

        {/* Summary Cards Column */}
        <div className="lg:col-span-2 grid grid-cols-2 gap-4">
          <Link to="/invoices-review" className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5 hover:shadow-md transition-shadow">
            <p className="text-sm text-gray-400">Invoices to Review</p>
            <p className="text-2xl font-bold mt-1 text-yellow-400">{stats.needsReview}</p>
          </Link>
          <Link to="/payments-out" className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5 hover:shadow-md transition-shadow">
            <p className="text-sm text-gray-400">Payments Out</p>
            <p className="text-2xl font-bold mt-1 text-orange-400">${fmt(stats.paymentsOutTotal)}</p>
          </Link>
          <Link to="/payables" className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5 hover:shadow-md transition-shadow">
            <p className="text-sm text-gray-400">Total Invoices/Payables</p>
            <p className="text-2xl font-bold mt-1 text-red-400">${fmt(stats.combinedOutstanding)}</p>
          </Link>
          <Link to="/payables" className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5 hover:shadow-md transition-shadow">
            <p className="text-sm text-gray-400">Invoices/Payables Turned On</p>
            <p className="text-2xl font-bold mt-1 text-purple-400">${fmt(rb.total_included_payables)}</p>
          </Link>
        </div>
      </div>

      {/* Top Vendor Balances */}
      {topVendors.length > 0 && (
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-100">Top Vendor Balances</h2>
            <Link to="/bills" className="text-blue-400 text-sm hover:underline">View All</Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {topVendors.map((v) => (
              <div key={v.id} className="flex justify-between items-center bg-gray-900 rounded-lg px-4 py-3">
                <span className="text-sm text-gray-300 font-medium truncate mr-2">{v.vendor_name}</span>
                <span className="text-sm text-gray-100 font-bold whitespace-nowrap">${fmt(v.amount)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bills Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Bills Due This Week</p>
              <p className="text-2xl font-bold mt-1 text-gray-100">{stats.billsDueSoon}</p>
            </div>
            <div className="p-3 rounded-lg bg-yellow-500">
              <ClockIcon className="h-6 w-6 text-white" />
            </div>
          </div>
        </div>
        {stats.billsOverdue > 0 && (
          <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Overdue Bills</p>
                <p className="text-2xl font-bold mt-1 text-gray-100">{stats.billsOverdue}</p>
              </div>
              <div className="p-3 rounded-lg bg-red-600">
                <ExclamationTriangleIcon className="h-6 w-6 text-white" />
              </div>
            </div>
          </div>
        )}
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Next Bill Due</p>
              <p className="text-2xl font-bold mt-1 text-gray-100">
                {stats.nextBill
                  ? `${stats.nextBill.bill_name} — ${new Date(stats.nextBill.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
                  : 'None'
                }
              </p>
            </div>
            <div className="p-3 rounded-lg bg-blue-500">
              <ClockIcon className="h-6 w-6 text-white" />
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Invoices */}
        <div className="lg:col-span-2 bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-100">Recent Invoices</h2>
            <Link to="/invoices" className="text-blue-400 text-sm hover:underline">View All</Link>
          </div>
          {recentInvoices.length === 0 ? (
            <p className="text-gray-400 text-sm py-8 text-center">
              No invoices yet. Configure your email in Settings to start receiving bills.
            </p>
          ) : (
            <div className="space-y-3">
              {recentInvoices.map((inv) => (
                <Link
                  key={inv.id}
                  to={`/invoices/${inv.id}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-700 transition-colors"
                >
                  <div>
                    <p className="font-medium text-sm text-gray-200">{inv.vendor_name || 'Unknown Vendor'}</p>
                    <p className="text-gray-400 text-xs">{inv.invoice_number || 'No invoice #'}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-sm">
                      {inv.total_amount ? `$${inv.total_amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      {
                        pending: 'bg-gray-700 text-gray-300',
                        extracted: 'bg-blue-900/50 text-blue-400',
                        needs_review: 'bg-yellow-900/50 text-yellow-400',
                        auto_matched: 'bg-green-900/50 text-green-400',
                        approved: 'bg-emerald-900/50 text-emerald-400',
                        sent_to_qb: 'bg-purple-900/50 text-purple-400',
                        paid: 'bg-gray-700 text-gray-400',
                      }[inv.status] || 'bg-gray-700'
                    }`}>
                      {inv.status.replace(/_/g, ' ')}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* System Status */}
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-100">System Status</h2>
          {health ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">API</span>
                <span className={`text-sm font-medium ${health.status === 'healthy' ? 'text-green-600' : 'text-yellow-600'}`}>
                  {health.status}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Database</span>
                <span className={`text-sm font-medium ${health.db_connected ? 'text-green-600' : 'text-red-600'}`}>
                  {health.db_connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Redis</span>
                <span className={`text-sm font-medium ${health.redis_connected ? 'text-green-600' : 'text-red-600'}`}>
                  {health.redis_connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">QuickBooks</span>
                <span className={`text-sm font-medium ${qbStatus?.connected ? 'text-green-600' : 'text-red-600'}`}>
                  {qbStatus ? (qbStatus.connected ? 'Connected' : 'Not Connected') : '...'}
                </span>
              </div>
              <button
                onClick={handlePollNow}
                disabled={polling}
                className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
              >
                <ArrowPathIcon className={`h-4 w-4 ${polling ? 'animate-spin' : ''}`} />
                {polling ? 'Polling...' : 'Poll Now'}
              </button>
            </div>
          ) : (
            <p className="text-gray-400 text-sm">Loading...</p>
          )}
        </div>
      </div>
    </div>
  )
}
