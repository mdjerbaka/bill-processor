import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { invoicesAPI, payablesAPI, healthAPI, settingsAPI, recurringBillsAPI } from '../services/api'
import toast from 'react-hot-toast'
import OverdueAlertBanner from '../components/OverdueAlertBanner'
import {
  InboxIcon,
  CurrencyDollarIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'

function StatCard({ title, value, icon: Icon, color, link }) {
  const content = (
    <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className="text-2xl font-bold mt-1 text-gray-100">{value}</p>
        </div>
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
      </div>
    </div>
  )

  return link ? <Link to={link}>{content}</Link> : content
}

export default function DashboardPage() {
  const [stats, setStats] = useState({
    totalInvoices: 0,
    needsReview: 0,
    outstanding: 0,
    overdue: 0,
    realBalance: null,
    billsDueSoon: 0,
    billsOverdue: 0,
    nextBill: null,
    overdueBills: [],
  })
  const [health, setHealth] = useState(null)
  const [recentInvoices, setRecentInvoices] = useState([])
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
      const [invoicesRes, payablesRes, balanceRes, healthRes, cashFlowRes] = await Promise.allSettled([
        invoicesAPI.list({ page: 1, page_size: 15 }),
        payablesAPI.list(),
        payablesAPI.getRealBalance(),
        healthAPI.check(),
        recurringBillsAPI.getCashFlow(),
      ])

      if (invoicesRes.status === 'fulfilled') {
        const data = invoicesRes.value.data
        setRecentInvoices(data.items)
        setStats((s) => ({ ...s, totalInvoices: data.total }))
      }

      if (payablesRes.status === 'fulfilled') {
        const data = payablesRes.value.data
        setStats((s) => ({
          ...s,
          outstanding: data.total_outstanding,
          overdue: data.total_overdue,
        }))
      }

      if (balanceRes.status === 'fulfilled') {
        setStats((s) => ({ ...s, realBalance: balanceRes.value.data }))
      }

      if (healthRes.status === 'fulfilled') {
        setHealth(healthRes.value.data)
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

  function formatPollTime(isoString) {
    if (!isoString) return 'Never'
    try {
      return new Date(isoString).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
      })
    } catch {
      return isoString
    }
  }

  const statusBadge = (status) => {
    const map = {
      pending: 'bg-gray-700 text-gray-300',
      extracted: 'bg-blue-900/50 text-blue-400',
      needs_review: 'bg-yellow-900/50 text-yellow-400',
      auto_matched: 'bg-green-900/50 text-green-400',
      approved: 'bg-emerald-900/50 text-emerald-400',
      sent_to_qb: 'bg-purple-900/50 text-purple-400',
      paid: 'bg-gray-700 text-gray-400',
    }
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${map[status] || 'bg-gray-700'}`}>
        {status.replace(/_/g, ' ')}
      </span>
    )
  }

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

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          title="Total Invoices"
          value={stats.totalInvoices}
          icon={InboxIcon}
          color="bg-blue-500"
          link="/invoices"
        />
        <StatCard
          title="Needs Review"
          value={stats.needsReview}
          icon={ExclamationTriangleIcon}
          color="bg-yellow-500"
          link="/invoices?status=needs_review"
        />
        <StatCard
          title="Outstanding Payables"
          value={`$${stats.outstanding.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          icon={CurrencyDollarIcon}
          color="bg-red-500"
          link="/payables"
        />
        <StatCard
          title="Real Available Funds"
          value={stats.realBalance
            ? `$${stats.realBalance.real_available.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
            : '—'
          }
          icon={CheckCircleIcon}
          color="bg-green-500"
          link="/payables"
        />
      </div>

      {/* Bills Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <StatCard
          title="Bills Due This Week"
          value={stats.billsDueSoon}
          icon={ClockIcon}
          color="bg-yellow-500"
          link="/bills"
        />
        {stats.billsOverdue > 0 && (
          <StatCard
            title="Overdue Bills"
            value={stats.billsOverdue}
            icon={ExclamationTriangleIcon}
            color="bg-red-600"
            link="/bills"
          />
        )}
        <StatCard
          title="Next Bill Due"
          value={stats.nextBill
            ? `${stats.nextBill.bill_name} — ${new Date(stats.nextBill.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
            : 'None'
          }
          icon={ClockIcon}
          color="bg-blue-500"
          link="/bills"
        />
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
                    {statusBadge(inv.status)}
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
                <span className="text-sm text-gray-400">Version</span>
                <span className="text-sm font-medium">{health.version}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Last Email Poll</span>
                <span className="text-sm font-medium">
                  {formatPollTime(health.last_email_poll)}
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
