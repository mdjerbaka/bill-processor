import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { recurringBillsAPI, payablesAPI } from '../services/api'
import toast from 'react-hot-toast'
import OverdueAlertBanner from '../components/OverdueAlertBanner'
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  XMarkIcon,
  ArrowPathIcon,
  CalendarDaysIcon,
  BanknotesIcon,
  ExclamationTriangleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ArrowUpTrayIcon,
  ForwardIcon,
  CheckCircleIcon,
  ChevronUpDownIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline'

const FREQUENCY_OPTIONS = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'semi_annual', label: 'Semi-Annual' },
  { value: 'annual', label: 'Annual' },
  { value: 'biennial', label: 'Biennial (2 years)' },
]

const CATEGORY_OPTIONS = [
  { value: 'mortgage', label: 'Mortgage' },
  { value: 'vehicle', label: 'Vehicle' },
  { value: 'electric', label: 'Electric' },
  { value: 'water', label: 'Water' },
  { value: 'sewer', label: 'Sewer' },
  { value: 'internet', label: 'Internet' },
  { value: 'vehicle_insurance', label: 'Vehicle Insurance' },
  { value: 'health_insurance', label: 'Health Insurance' },
  { value: 'liability_insurance', label: 'Liability Insurance' },
  { value: 'life_insurance', label: 'Life Insurance' },
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'bookkeeper', label: 'Bookkeeper' },
  { value: 'loan', label: 'Loan' },
  { value: 'subscription', label: 'Subscription' },
  { value: 'trash', label: 'Trash' },
  { value: 'phone', label: 'Phone' },
  { value: 'workers_comp', label: "Workers' Comp" },
  { value: 'cpa', label: 'CPA' },
  { value: 'taxes', label: 'Taxes' },
  { value: 'registration', label: 'Registration' },
  { value: 'license', label: 'License' },
  { value: 'payroll', label: 'Payroll' },
  { value: 'subcontractor', label: 'Subcontractor' },
  { value: 'other', label: 'Other' },
]

const STATUS_COLORS = {
  upcoming: 'bg-green-900/50 text-green-400',
  due_soon: 'bg-yellow-900/50 text-yellow-400',
  overdue: 'bg-red-900/50 text-red-400',
  skipped: 'bg-gray-700 text-gray-400',
  paid: 'bg-emerald-900/50 text-emerald-400',
}

function StatusBadge({ status }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[status] || 'bg-gray-700 text-gray-400'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function SummaryCard({ title, value, color, icon: Icon, tooltip }) {
  const [showTooltip, setShowTooltip] = useState(false)
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-1">
            <p className="text-sm text-gray-400">{title}</p>
            {tooltip && (
              <div className="relative">
                <InformationCircleIcon
                  className="h-4 w-4 text-gray-500 hover:text-gray-300 cursor-help"
                  onMouseEnter={() => setShowTooltip(true)}
                  onMouseLeave={() => setShowTooltip(false)}
                />
                {showTooltip && (
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2 bg-gray-900 border border-gray-600 rounded-lg text-xs text-gray-300 shadow-lg z-50 whitespace-pre-line">
                    {tooltip}
                  </div>
                )}
              </div>
            )}
          </div>
          <p className={`text-xl font-bold mt-1 ${color || 'text-gray-100'}`}>{value}</p>
        </div>
        {Icon && (
          <div className="p-2.5 rounded-lg bg-gray-700/50">
            <Icon className={`h-5 w-5 ${color || 'text-gray-400'}`} />
          </div>
        )}
      </div>
    </div>
  )
}

const emptyForm = {
  name: '',
  vendor_name: '',
  amount: '',
  frequency: 'monthly',
  due_day_of_month: '',
  due_month: '',
  category: 'other',
  notes: '',
  is_auto_pay: false,
  alert_days_before: 7,
}

export default function BillsPage() {
  const navigate = useNavigate()
  const [cashFlow, setCashFlow] = useState(null)
  const [occurrences, setOccurrences] = useState([])
  const [bills, setBills] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingBill, setEditingBill] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [managementOpen, setManagementOpen] = useState(false)
  const [upcomingOpen, setUpcomingOpen] = useState(true)
  const [filterStatus, setFilterStatus] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [importFile, setImportFile] = useState(null)
  const [importing, setImporting] = useState(false)
  const [outstandingChecksInput, setOutstandingChecksInput] = useState('')
  const [bankBalanceInput, setBankBalanceInput] = useState('')
  const [editingBankBalance, setEditingBankBalance] = useState(false)
  const [editingOutstandingChecks, setEditingOutstandingChecks] = useState(false)
  const [sortColumn, setSortColumn] = useState('due_date')
  const [sortDirection, setSortDirection] = useState('asc')
  const [selectedOccurrences, setSelectedOccurrences] = useState(new Set())

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

  const sortedOccurrences = [...occurrences].sort((a, b) => {
    const dir = sortDirection === 'asc' ? 1 : -1
    switch (sortColumn) {
      case 'bill_name': return dir * (a.bill_name || '').localeCompare(b.bill_name || '')
      case 'category': return dir * (a.category || '').localeCompare(b.category || '')
      case 'amount': return dir * ((a.amount || 0) - (b.amount || 0))
      case 'due_date': return dir * (new Date(a.due_date) - new Date(b.due_date))
      case 'status': {
        const order = { overdue: 0, due_soon: 1, upcoming: 2, paid: 3, skipped: 4 }
        return dir * ((order[a.status] ?? 5) - (order[b.status] ?? 5))
      }
      default: return 0
    }
  })

  const loadData = useCallback(async () => {
    try {
      const [cfRes, occRes, billsRes] = await Promise.allSettled([
        recurringBillsAPI.getCashFlow(),
        recurringBillsAPI.listOccurrences({
          ...(filterStatus && { status: filterStatus }),
          ...(filterCategory && { category: filterCategory }),
        }),
        recurringBillsAPI.list(),
      ])
      if (cfRes.status === 'fulfilled') {
        setCashFlow(cfRes.value.data)
        setBankBalanceInput(cfRes.value.data.bank_balance?.toString() || '0')
      }
      if (occRes.status === 'fulfilled') setOccurrences(occRes.value.data.items || [])
      if (billsRes.status === 'fulfilled') setBills(billsRes.value.data.items || [])
    } catch {
      toast.error('Failed to load bills data')
    } finally {
      setLoading(false)
    }
  }, [filterStatus, filterCategory])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [loadData])

  // Sync outstanding checks input with loaded cash flow data
  useEffect(() => {
    if (cashFlow?.outstanding_checks != null) {
      setOutstandingChecksInput(cashFlow.outstanding_checks.toString())
    }
  }, [cashFlow])

  function openAddForm() {
    setForm(emptyForm)
    setEditingBill(null)
    setShowForm(true)
  }

  function openEditForm(bill) {
    setForm({
      name: bill.name,
      vendor_name: bill.vendor_name,
      amount: bill.amount.toString(),
      frequency: bill.frequency,
      due_day_of_month: bill.due_day_of_month.toString(),
      due_month: bill.due_month ? bill.due_month.toString() : '',
      category: bill.category,
      notes: bill.notes || '',
      is_auto_pay: bill.is_auto_pay,
      alert_days_before: bill.alert_days_before,
    })
    setEditingBill(bill)
    setShowForm(true)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const payload = {
      ...form,
      amount: parseFloat(form.amount),
      due_day_of_month: parseInt(form.due_day_of_month),
      due_month: form.due_month ? parseInt(form.due_month) : null,
      alert_days_before: parseInt(form.alert_days_before),
    }
    try {
      if (editingBill) {
        await recurringBillsAPI.update(editingBill.id, payload)
        toast.success('Bill updated')
      } else {
        await recurringBillsAPI.create(payload)
        toast.success('Bill created')
      }
      setShowForm(false)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save bill')
    }
  }

  async function handleDelete(id) {
    if (!confirm('Deactivate this recurring bill?')) return
    try {
      await recurringBillsAPI.delete(id)
      toast.success('Bill deactivated')
      loadData()
    } catch {
      toast.error('Failed to deactivate bill')
    }
  }

  async function handleDeleteAll() {
    if (!confirm('Delete ALL recurring bills and their occurrences? This cannot be undone.')) return
    try {
      const res = await recurringBillsAPI.deleteAll()
      toast.success(res.data.detail)
      loadData()
    } catch {
      toast.error('Failed to delete all bills')
    }
  }

  // Refresh only the cash flow summary without re-fetching occurrences
  const refreshCashFlow = useCallback(async () => {
    try {
      const res = await recurringBillsAPI.getCashFlow()
      setCashFlow(res.data)
      setBankBalanceInput(res.data.bank_balance?.toString() || '0')
    } catch { /* ignore */ }
  }, [])

  async function handleSkip(occurrenceId) {
    try {
      await recurringBillsAPI.skip(occurrenceId)
      toast.success('Occurrence skipped')
      // Update in-place so the bill doesn't jump
      setOccurrences(prev => prev.map(o =>
        o.id === occurrenceId ? { ...o, status: 'skipped' } : o
      ))
      refreshCashFlow()
    } catch {
      toast.error('Failed to skip occurrence')
    }
  }

  async function handleMarkPaid(occurrenceId) {
    try {
      const res = await recurringBillsAPI.markPaid(occurrenceId)
      const nextDate = res.data?.next_due_date
      if (nextDate) {
        const formatted = new Date(nextDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
        toast.success(`Marked as paid! Next due: ${formatted}`)
      } else {
        toast.success('Marked as paid')
      }
      // Update in-place so the bill doesn't jump
      setOccurrences(prev => prev.map(o =>
        o.id === occurrenceId ? { ...o, status: 'paid', paid_at: new Date().toISOString(), included_in_cashflow: false } : o
      ))
      refreshCashFlow()
    } catch {
      toast.error('Failed to mark as paid')
    }
  }

  async function handleToggleCashflow(occurrenceId) {
    try {
      const res = await recurringBillsAPI.toggleCashflow(occurrenceId)
      // Update in-place so the bill doesn't jump
      setOccurrences(prev => prev.map(o =>
        o.id === occurrenceId ? { ...o, included_in_cashflow: res.data.included_in_cashflow } : o
      ))
      refreshCashFlow()
    } catch {
      toast.error('Failed to toggle cash flow inclusion')
    }
  }

  async function handleDeleteSelected() {
    if (selectedOccurrences.size === 0) return
    if (!confirm(`Delete ${selectedOccurrences.size} selected bill(s) and all their occurrences? This cannot be undone.`)) return
    try {
      const res = await recurringBillsAPI.bulkDeleteOccurrences([...selectedOccurrences])
      toast.success(res.data.detail)
      setSelectedOccurrences(new Set())
      loadData()
    } catch {
      toast.error('Failed to delete selected occurrences')
    }
  }

  function toggleSelectAll() {
    if (selectedOccurrences.size === sortedOccurrences.length) {
      setSelectedOccurrences(new Set())
    } else {
      setSelectedOccurrences(new Set(sortedOccurrences.map(o => o.id)))
    }
  }

  function toggleSelect(id) {
    setSelectedOccurrences(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleImport() {
    if (!importFile) {
      toast.error('Please select a CSV file')
      return
    }
    setImporting(true)
    try {
      const res = await recurringBillsAPI.importCSV(importFile)
      const data = res.data
      toast.success(`Imported ${data.count} bills`)
      if (data.warnings?.length) {
        toast(data.warnings.join('\n'), { icon: '⚠️', duration: 8000 })
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
      const res = await recurringBillsAPI.downloadTemplate()
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'recurring_bills_template.csv'
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      toast.error('Failed to download template')
    }
  }

  async function handleBankBalance(e) {
    e.preventDefault()
    const amount = parseFloat(bankBalanceInput)
    if (isNaN(amount) || amount < 0) {
      toast.error('Enter a valid amount')
      return
    }
    try {
      await payablesAPI.setBankBalance(amount)
      toast.success('Bank balance updated')
      setEditingBankBalance(false)
      loadData()
    } catch {
      toast.error('Failed to update bank balance')
    }
  }

  async function handleOutstandingChecks(e) {
    e.preventDefault()
    const amount = parseFloat(outstandingChecksInput)
    if (isNaN(amount) || amount < 0) {
      toast.error('Enter a valid amount')
      return
    }
    try {
      await recurringBillsAPI.setOutstandingChecks(amount)
      toast.success('Outstanding checks updated')
      setEditingOutstandingChecks(false)
      loadData()
    } catch {
      toast.error('Failed to update outstanding checks')
    }
  }

  function daysUntil(dateStr) {
    const diff = Math.ceil((new Date(dateStr) - new Date()) / (1000 * 60 * 60 * 24))
    if (diff < 0) return `${Math.abs(diff)}d overdue`
    if (diff === 0) return 'Today'
    return `${diff}d`
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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Recurring Bills & Cash Flow</h1>
        <div className="flex gap-2">
          {bills.length > 0 && (
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
            Import
          </button>
          <button
            onClick={openAddForm}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            Add Bill
          </button>
        </div>
      </div>

      {/* Overdue Alert Banner */}
      <OverdueAlertBanner
        overdueBills={cashFlow?.overdue_bills || []}
        onMarkPaid={handleMarkPaid}
      />

      {/* Cash Flow Summary */}
      {cashFlow && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-sm text-gray-400">Bank Balance</p>
                {editingBankBalance ? (
                  <form onSubmit={handleBankBalance} className="flex items-center gap-2 mt-1">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={bankBalanceInput}
                      onChange={(e) => setBankBalanceInput(e.target.value)}
                      className="w-32 px-2 py-1 border border-gray-600 bg-gray-700 text-gray-200 rounded text-sm"
                      autoFocus
                    />
                    <button type="submit" className="px-2 py-1 bg-blue-600 text-white text-xs rounded">Save</button>
                    <button type="button" onClick={() => setEditingBankBalance(false)} className="px-2 py-1 text-xs text-gray-400">Cancel</button>
                  </form>
                ) : (
                  <p className="text-2xl font-bold text-blue-400 cursor-pointer mt-1" onClick={() => setEditingBankBalance(true)}>
                    ${(cashFlow.bank_balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    <span className="text-xs text-blue-400/60 ml-2">edit</span>
                  </p>
                )}
              </div>
              <div className="p-2.5 rounded-lg bg-gray-700/50">
                <BanknotesIcon className="h-5 w-5 text-blue-400" />
              </div>
            </div>
          </div>
          <SummaryCard title="Due in 7 Days" value={fmt(cashFlow.total_upcoming_7d)} icon={CalendarDaysIcon} color="text-yellow-400" />
          <SummaryCard title="Due in 30 Days" value={fmt(cashFlow.total_upcoming_30d)} icon={CalendarDaysIcon} color="text-orange-400" />
          <SummaryCard
            title="Overdue"
            value={fmt(cashFlow.total_overdue)}
            icon={ExclamationTriangleIcon}
            color={cashFlow.total_overdue > 0 ? 'text-red-400' : 'text-gray-400'}
          />
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-sm text-gray-400">Outstanding Checks</p>
                {editingOutstandingChecks ? (
                  <form onSubmit={handleOutstandingChecks} className="flex items-center gap-2 mt-1">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={outstandingChecksInput}
                      onChange={(e) => setOutstandingChecksInput(e.target.value)}
                      className="w-32 px-2 py-1 border border-gray-600 bg-gray-700 text-gray-200 rounded text-sm"
                      autoFocus
                    />
                    <button type="submit" className="px-2 py-1 bg-blue-600 text-white text-xs rounded">Save</button>
                    <button type="button" onClick={() => setEditingOutstandingChecks(false)} className="px-2 py-1 text-xs text-gray-400">Cancel</button>
                  </form>
                ) : (
                  <p className="text-2xl font-bold text-amber-400 cursor-pointer mt-1" onClick={() => setEditingOutstandingChecks(true)}>
                    ${(cashFlow.outstanding_checks || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    <span className="text-xs text-amber-400/60 ml-2">edit</span>
                  </p>
                )}
              </div>
              <div className="p-2.5 rounded-lg bg-gray-700/50">
                <BanknotesIcon className="h-5 w-5 text-amber-400" />
              </div>
            </div>
          </div>
          <div
            className="bg-gray-800 rounded-xl border border-gray-700 p-5 cursor-pointer hover:border-green-700/50 transition-colors"
            onClick={() => navigate('/receivables')}
            title="Click to manage receivable checks"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Expected Receivables</p>
                <p className="text-xs text-gray-500 mt-0.5">From receivable checks</p>
                <p className="text-2xl font-bold text-green-400 mt-1">
                  ${(cashFlow.expected_receivables || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  <span className="text-xs text-green-400/60 ml-2">view &rarr;</span>
                </p>
              </div>
              <div className="p-2.5 rounded-lg bg-gray-700/50">
                <BanknotesIcon className="h-5 w-5 text-green-400" />
              </div>
            </div>
          </div>
          <div
            className="bg-gray-800 rounded-xl border border-gray-700 p-5 cursor-pointer hover:border-red-700/50 transition-colors"
            onClick={() => navigate('/payables')}
            title="Click to manage payables"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Outstanding Payables</p>
                <p className="text-xs text-gray-500 mt-0.5">Invoices to pay</p>
                <p className="text-2xl font-bold text-red-400 mt-1">
                  ${(cashFlow.total_payables || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  <span className="text-xs text-red-400/60 ml-2">view &rarr;</span>
                </p>
              </div>
              <div className="p-2.5 rounded-lg bg-gray-700/50">
                <BanknotesIcon className="h-5 w-5 text-red-400" />
              </div>
            </div>
          </div>
          <SummaryCard
            title="Real Available"
            value={fmt(cashFlow.real_available)}
            icon={BanknotesIcon}
            color={cashFlow.real_available >= 0 ? 'text-green-400' : 'text-red-400'}
            tooltip={`Bank Balance\n+ Expected Receivables\n− Outstanding Checks\n− Outstanding Payables\n− Toggled bills (30 days)\n− All overdue bills\n\n${fmt(cashFlow.bank_balance)} + ${fmt(cashFlow.expected_receivables || 0)} − ${fmt(cashFlow.outstanding_checks)} − ${fmt(cashFlow.total_payables || 0)} − ${fmt(cashFlow.total_upcoming_30d)} − ${fmt(cashFlow.total_overdue)} = ${fmt(cashFlow.real_available)}`}
          />
        </div>
      )}

      {/* Upcoming Bills */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 mb-6">
        <button
          onClick={() => setUpcomingOpen(!upcomingOpen)}
          className="w-full flex items-center justify-between p-6 text-left"
        >
          <h2 className="text-lg font-semibold text-gray-100">Upcoming Bills</h2>
          <div className="flex items-center gap-2">
            {upcomingOpen ? (
              <ChevronUpIcon className="h-5 w-5 text-gray-400" />
            ) : (
              <ChevronDownIcon className="h-5 w-5 text-gray-400" />
            )}
          </div>
        </button>

        {upcomingOpen && (
          <div className="px-6 pb-6">
          <div className="flex gap-2 mb-4 items-center">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="bg-gray-700 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-1.5"
            >
              <option value="">All Statuses</option>
              <option value="upcoming">Upcoming</option>
              <option value="due_soon">Due Soon</option>
              <option value="overdue">Overdue</option>
              <option value="skipped">Skipped</option>
              <option value="paid">Paid</option>
            </select>
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="bg-gray-700 border border-gray-600 text-gray-200 text-sm rounded-lg px-3 py-1.5"
            >
              <option value="">All Categories</option>
              {CATEGORY_OPTIONS.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
            {selectedOccurrences.size > 0 && (
              <button
                onClick={handleDeleteSelected}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-red-900/50 hover:bg-red-800 text-red-300 rounded-lg transition-colors ml-auto"
              >
                <TrashIcon className="h-4 w-4" />
                Delete Selected ({selectedOccurrences.size})
              </button>
            )}
          </div>

        {occurrences.length === 0 ? (
          <p className="text-gray-500 text-sm text-center py-8">
            No upcoming bill occurrences. Add some recurring bills to get started.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="pb-3 pr-2">
                    <input
                      type="checkbox"
                      checked={sortedOccurrences.length > 0 && selectedOccurrences.size === sortedOccurrences.length}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                    />
                  </th>
                  <th className="pb-3 font-medium cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('bill_name')}>Bill<SortIcon column="bill_name" /></th>
                  <th className="pb-3 font-medium cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('category')}>Category<SortIcon column="category" /></th>
                  <th className="pb-3 font-medium text-right cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('amount')}>Amount<SortIcon column="amount" /></th>
                  <th className="pb-3 font-medium cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('due_date')}>Due Date<SortIcon column="due_date" /></th>
                  <th className="pb-3 font-medium">Days</th>
                  <th className="pb-3 font-medium cursor-pointer select-none hover:text-gray-200" onClick={() => handleSort('status')}>Status<SortIcon column="status" /></th>
                  <th className="pb-3 font-medium text-center" title="Include in cash flow calculation">$</th>
                  <th className="pb-3 font-medium">Auto-Pay</th>
                  <th className="pb-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedOccurrences.map((occ) => (
                  <tr key={occ.id} className={`border-b border-gray-700/50 hover:bg-gray-700/30 ${selectedOccurrences.has(occ.id) ? 'bg-blue-900/20' : ''}`}>
                    <td className="py-3 pr-2">
                      <input
                        type="checkbox"
                        checked={selectedOccurrences.has(occ.id)}
                        onChange={() => toggleSelect(occ.id)}
                        className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                      />
                    </td>
                    <td className="py-3">
                      <p className="font-medium text-gray-200">{occ.bill_name}</p>
                      <p className="text-gray-500 text-xs">{occ.vendor_name}</p>
                    </td>
                    <td className="py-3">
                      <span className="text-xs text-gray-400 capitalize">{(occ.category || '').replace(/_/g, ' ')}</span>
                    </td>
                    <td className="py-3 text-right font-medium">{fmt(occ.amount)}</td>
                    <td className="py-3 text-gray-300">
                      {new Date(occ.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </td>
                    <td className="py-3">
                      <span className={
                        occ.status === 'overdue'
                          ? (occ.days_overdue >= 25 ? 'text-red-500 font-bold animate-pulse' :
                             occ.days_overdue >= 15 ? 'text-orange-400 font-semibold' :
                             'text-red-400 font-medium')
                          : occ.status === 'due_soon' ? 'text-yellow-400' : 'text-gray-400'
                      }>
                        {daysUntil(occ.due_date)}
                      </span>
                      {occ.days_overdue >= 25 && (
                        <span className="block text-[10px] text-red-500 font-semibold">CREDIT DANGER</span>
                      )}
                    </td>
                    <td className="py-3"><StatusBadge status={occ.status} /></td>
                    <td className="py-3 text-center">
                      {occ.status !== 'paid' && occ.status !== 'skipped' && (
                        <button
                          onClick={() => handleToggleCashflow(occ.id)}
                          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                            occ.included_in_cashflow ? 'bg-blue-600' : 'bg-gray-600'
                          }`}
                          title={occ.included_in_cashflow ? 'Included in cash flow — click to exclude' : 'Excluded from cash flow — click to include'}
                        >
                          <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                            occ.included_in_cashflow ? 'translate-x-[18px]' : 'translate-x-[2px]'
                          }`} />
                        </button>
                      )}
                    </td>
                    <td className="py-3 text-center">
                      {occ.is_auto_pay && (
                        <span className="text-xs bg-blue-900/50 text-blue-400 px-2 py-0.5 rounded-full">auto</span>
                      )}
                      {occ.matched_invoice_id && (
                        <span className="text-xs bg-purple-900/50 text-purple-400 px-2 py-0.5 rounded-full ml-1" title={`Matched to invoice #${occ.matched_invoice_id}`}>linked</span>
                      )}
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex items-center justify-end gap-3">
                        {occ.status !== 'skipped' && occ.status !== 'paid' && (
                          <button
                            onClick={() => handleMarkPaid(occ.id)}
                            className="px-2.5 py-1 text-xs font-medium rounded-lg bg-emerald-900/50 text-emerald-400 hover:bg-emerald-800 transition-colors"
                            title="Mark as paid"
                          >
                            <CheckCircleIcon className="h-5 w-5 inline -mt-0.5 mr-1" />
                            Paid
                          </button>
                        )}
                        {occ.status !== 'skipped' && occ.status !== 'paid' && (
                          <button
                            onClick={() => handleSkip(occ.id)}
                            className="px-2.5 py-1 text-xs font-medium rounded-lg bg-yellow-900/50 text-yellow-400 hover:bg-yellow-800 transition-colors"
                            title="Skip this occurrence"
                          >
                            <ForwardIcon className="h-5 w-5 inline -mt-0.5 mr-1" />
                            Skip
                          </button>
                        )}
                        <button
                          onClick={() => {
                            const parentBill = bills.find(b => b.id === occ.recurring_bill_id)
                            if (parentBill) openEditForm(parentBill)
                          }}
                          className="p-1.5 text-gray-400 hover:text-blue-400 transition-colors"
                          title="Edit recurring bill"
                        >
                          <PencilIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        </div>
        )}
      </div>

      {/* Recurring Bills Management */}
      <div className="bg-gray-800 rounded-xl border border-gray-700">
        <button
          onClick={() => setManagementOpen(!managementOpen)}
          className="w-full flex items-center justify-between p-6 text-left"
        >
          <h2 className="text-lg font-semibold text-gray-100">Manage Recurring Bills ({bills.length})</h2>
          {managementOpen ? (
            <ChevronUpIcon className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronDownIcon className="h-5 w-5 text-gray-400" />
          )}
        </button>

        {managementOpen && (
          <div className="px-6 pb-6">
            {bills.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-4">No recurring bills yet.</p>
            ) : (
              <div className="space-y-2">
                {bills.map((bill) => (
                  <div key={bill.id} className="flex items-center justify-between p-3 rounded-lg bg-gray-700/30 hover:bg-gray-700/50">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-gray-200">{bill.name}</p>
                        {bill.is_auto_pay && (
                          <span className="text-xs bg-blue-900/50 text-blue-400 px-1.5 py-0.5 rounded">auto</span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500">
                        {bill.vendor_name} · {fmt(bill.amount)} · {bill.frequency.replace(/_/g, ' ')} · Day {bill.due_day_of_month}
                        {bill.due_month ? ` · Month ${bill.due_month}` : ''}
                        {' · '}<span className="capitalize">{bill.category.replace(/_/g, ' ')}</span>
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {bill.next_due_date && (
                        <span className="text-xs text-gray-400">
                          Next: {new Date(bill.next_due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        </span>
                      )}
                      <button onClick={() => openEditForm(bill)} className="p-1.5 text-gray-400 hover:text-blue-400 transition-colors">
                        <PencilIcon className="h-4 w-4" />
                      </button>
                      <button onClick={() => handleDelete(bill.id)} className="p-1.5 text-gray-400 hover:text-red-400 transition-colors">
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Add/Edit Bill Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-100">
                {editingBill ? 'Edit Bill' : 'Add Recurring Bill'}
              </h3>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-white">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Bill Name</label>
                  <input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Vendor</label>
                  <input
                    value={form.vendor_name}
                    onChange={(e) => setForm({ ...form, vendor_name: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Amount ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={form.amount}
                    onChange={(e) => setForm({ ...form, amount: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Due Day (1-31)</label>
                  <input
                    type="number"
                    min="1"
                    max="31"
                    value={form.due_day_of_month}
                    onChange={(e) => setForm({ ...form, due_day_of_month: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Due Month</label>
                  <input
                    type="number"
                    min="1"
                    max="12"
                    value={form.due_month}
                    onChange={(e) => setForm({ ...form, due_month: e.target.value })}
                    placeholder="For quarterly/annual"
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Frequency</label>
                  <select
                    value={form.frequency}
                    onChange={(e) => setForm({ ...form, frequency: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  >
                    {FREQUENCY_OPTIONS.map((f) => (
                      <option key={f.value} value={f.value}>{f.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Category</label>
                  <select
                    value={form.category}
                    onChange={(e) => setForm({ ...form, category: e.target.value })}
                    className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                  >
                    {CATEGORY_OPTIONS.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Notes</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  rows={2}
                  className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 text-sm text-gray-300">
                  <input
                    type="checkbox"
                    checked={form.is_auto_pay}
                    onChange={(e) => setForm({ ...form, is_auto_pay: e.target.checked })}
                    className="rounded bg-gray-700 border-gray-600"
                  />
                  Auto-Pay (auto-withdrawal)
                </label>
                <div className="flex items-center gap-2">
                  <label className="text-sm text-gray-400">Alert</label>
                  <input
                    type="number"
                    min="1"
                    max="90"
                    value={form.alert_days_before}
                    onChange={(e) => setForm({ ...form, alert_days_before: parseInt(e.target.value) || 7 })}
                    className="w-16 bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-2 py-1 text-sm"
                  />
                  <span className="text-sm text-gray-400">days before</span>
                </div>
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
                  {editingBill ? 'Update Bill' : 'Add Bill'}
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
              <h3 className="text-lg font-semibold text-gray-100">Import Recurring Bills</h3>
              <button onClick={() => setShowImport(false)} className="text-gray-400 hover:text-white">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-sm text-gray-400 mb-2">
                  Upload a CSV file with your recurring bills. Need a starting point?
                </p>
                <button
                  onClick={handleDownloadTemplate}
                  className="text-sm text-blue-400 hover:text-blue-300 underline transition-colors"
                >
                  Download template CSV (pre-filled with common bill types)
                </button>
              </div>

              <p className="text-xs text-gray-500">
                The template includes all 54+ common bill types. Open it in Excel or Google Sheets,
                update the vendor names and amounts to match your actual bills, delete any rows you
                don't need, then upload.
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
