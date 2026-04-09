import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { recurringBillsAPI, payablesAPI, vendorAccountsAPI } from '../services/api'
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
  CurrencyDollarIcon,
} from '@heroicons/react/24/outline'

const FREQUENCY_OPTIONS = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'semi_annual', label: 'Semi-Annual' },
  { value: 'annual', label: 'Annual' },
  { value: 'biennial', label: 'Biennial (2 years)' },
  { value: 'custom', label: 'Custom Months' },
]

const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
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
  included_in_cashflow: true,
  alert_days_before: 7,
  custom_months: [],
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
  const [sortColumn, setSortColumn] = useState('due_date')
  const [sortDirection, setSortDirection] = useState('asc')
  const [selectedOccurrences, setSelectedOccurrences] = useState(new Set())
  const [collapsedWeeks, setCollapsedWeeks] = useState(new Set())
  const [lockedBills, setLockedBills] = useState([])
  const [vendorAccounts, setVendorAccounts] = useState([])
  const [showVendorForm, setShowVendorForm] = useState(false)
  const [editingVendor, setEditingVendor] = useState(null)
  const [vendorForm, setVendorForm] = useState({ vendor_name: '', account_info: '', as_of_date: '', due_date: '', amount: '', notes_due_dates: '', links: '' })

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

  // Group occurrences by week only (1-7, 8-14, 15-21, 22-31) — no month grouping
  function getWeekBucket(day) {
    if (day <= 7) return 1
    if (day <= 14) return 2
    if (day <= 21) return 3
    return 4
  }

  const groupedByWeek = (() => {
    const weeks = { 1: [], 2: [], 3: [], 4: [] }
    for (const occ of sortedOccurrences) {
      const d = new Date(occ.due_date)
      const week = getWeekBucket(d.getDate())
      weeks[week].push(occ)
    }
    const result = []
    for (const wk of [1, 2, 3, 4]) {
      if (weeks[wk].length > 0) {
        const items = weeks[wk]
        const subtotal = items.reduce((sum, o) => sum + (o.included_in_cashflow && o.status !== 'paid' && o.status !== 'skipped' ? (o.amount || 0) : 0), 0)
        const hasOverdue = items.some(o => o.status === 'overdue')
        result.push({ week: wk, items, subtotal, hasOverdue })
      }
    }
    return result
  })()

  function toggleWeekCollapse(key) {
    setCollapsedWeeks(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const loadData = useCallback(async () => {
    try {
      const [cfRes, occRes, billsRes, payablesRes, vendorRes] = await Promise.allSettled([
        recurringBillsAPI.getCashFlow(),
        recurringBillsAPI.listOccurrences({
          ...(filterStatus && { status: filterStatus }),
          ...(filterCategory && { category: filterCategory }),
        }),
        recurringBillsAPI.list(),
        payablesAPI.list(),
        vendorAccountsAPI.list(),
      ])
      if (cfRes.status === 'fulfilled') {
        setCashFlow(cfRes.value.data)
        setBankBalanceInput(cfRes.value.data.bank_balance?.toString() || '0')
      }
      if (occRes.status === 'fulfilled') setOccurrences(occRes.value.data.items || [])
      if (billsRes.status === 'fulfilled') setBills(billsRes.value.data.items || [])
      if (payablesRes.status === 'fulfilled') {
        const allPayables = payablesRes.value.data.items || []
        setLockedBills(allPayables.filter(p => p.is_permanent))
      }
      if (vendorRes.status === 'fulfilled') setVendorAccounts(vendorRes.value.data.items || [])
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

  // Sync outstanding checks display with loaded cash flow data
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
      included_in_cashflow: bill.included_in_cashflow ?? true,
      alert_days_before: bill.alert_days_before,
      custom_months: bill.custom_months || [],
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
      custom_months: form.frequency === 'custom' ? form.custom_months : null,
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

  const [showPaymentModal, setShowPaymentModal] = useState(false)
  const [paymentTarget, setPaymentTarget] = useState(null)
  const [paymentForm, setPaymentForm] = useState({ payment_method: 'check', check_number: '', job_name: '', notes: '' })

  function openPaymentModal(occurrence) {
    setPaymentTarget(occurrence)
    setPaymentForm({ payment_method: 'check', check_number: '', job_name: '', notes: '' })
    setShowPaymentModal(true)
  }

  async function handleMarkPaid(occurrenceId, paymentBody) {
    try {
      const res = await recurringBillsAPI.markPaid(occurrenceId, paymentBody)
      const nextDate = res.data?.next_due_date
      if (nextDate) {
        const formatted = new Date(nextDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
        toast.success(paymentBody ? `Marked as paid & recorded payment! Next due: ${formatted}` : `Marked as paid! Next due: ${formatted}`)
      } else {
        toast.success(paymentBody ? 'Marked as paid & recorded payment' : 'Marked as paid')
      }
      setShowPaymentModal(false)
      setPaymentTarget(null)
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

  async function handleToggleBillCashflow(billId) {
    try {
      const bill = bills.find(b => b.id === billId)
      if (!bill) return
      const res = await recurringBillsAPI.update(billId, { included_in_cashflow: !bill.included_in_cashflow })
      setBills(prev => prev.map(b => b.id === billId ? { ...b, included_in_cashflow: res.data.included_in_cashflow } : b))
      // Also update occurrences in-place
      setOccurrences(prev => prev.map(o =>
        o.recurring_bill_id === billId && (o.status === 'upcoming' || o.status === 'due_soon')
          ? { ...o, included_in_cashflow: res.data.included_in_cashflow } : o
      ))
      refreshCashFlow()
      toast.success(res.data.included_in_cashflow ? 'Bill included in cash flow' : 'Bill excluded from cash flow')
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

  function daysUntil(dateStr) {
    const diff = Math.ceil((new Date(dateStr) - new Date()) / (1000 * 60 * 60 * 24))
    if (diff < 0) return `${Math.abs(diff)}d overdue`
    if (diff === 0) return 'Today'
    return `${diff}d`
  }

  // Vendor Account handlers
  function openAddVendor() {
    setVendorForm({ vendor_name: '', account_info: '', as_of_date: '', due_date: '', amount: '', notes_due_dates: '', links: '' })
    setEditingVendor(null)
    setShowVendorForm(true)
  }

  function openEditVendor(v) {
    setVendorForm({
      vendor_name: v.vendor_name,
      account_info: v.account_info || '',
      as_of_date: v.as_of_date ? v.as_of_date.split('T')[0] : '',
      due_date: v.due_date ? v.due_date.split('T')[0] : '',
      amount: v.amount?.toString() || '',
      notes_due_dates: v.notes_due_dates || '',
      links: v.links || '',
    })
    setEditingVendor(v)
    setShowVendorForm(true)
  }

  async function handleVendorSubmit(e) {
    e.preventDefault()
    const payload = {
      ...vendorForm,
      amount: vendorForm.amount ? parseFloat(vendorForm.amount) : 0,
      as_of_date: vendorForm.as_of_date || null,
      due_date: vendorForm.due_date || null,
    }
    try {
      if (editingVendor) {
        await vendorAccountsAPI.update(editingVendor.id, payload)
        toast.success('Vendor account updated')
      } else {
        await vendorAccountsAPI.create(payload)
        toast.success('Vendor account added')
      }
      setShowVendorForm(false)
      loadData()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save vendor account')
    }
  }

  async function handleDeleteVendor(id) {
    if (!confirm('Delete this vendor account?')) return
    try {
      await vendorAccountsAPI.delete(id)
      toast.success('Vendor account deleted')
      loadData()
    } catch { toast.error('Failed to delete') }
  }

  const vendorTotal = vendorAccounts.reduce((sum, v) => sum + (v.amount || 0), 0)

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
        onMarkPaid={(id) => {
          const occ = occurrences.find(o => o.id === id)
          if (occ) openPaymentModal(occ)
          else handleMarkPaid(id)
        }}
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
          <div
            className="bg-gray-800 rounded-xl border border-gray-700 p-5 cursor-pointer hover:border-amber-700/50 transition-colors"
            onClick={() => navigate('/payments-out')}
            title="Click to manage payments out"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400">Outstanding Checks</p>
                <p className="text-xs text-gray-500 mt-0.5">Auto-calculated from Payments Out</p>
                <p className="text-2xl font-bold text-amber-400 mt-1">
                  ${(cashFlow.outstanding_checks || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </p>
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

      {/* Locked Bills (Permanent Payables) */}
      {lockedBills.length > 0 && (
        <div className="bg-gray-800 rounded-xl border border-gray-700 mb-6">
          <div className="p-4 border-b border-gray-700">
            <h2 className="text-lg font-semibold text-gray-100">Locked Bills</h2>
            <p className="text-xs text-gray-500 mt-0.5">Fixed recurring costs — always included</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="px-4 py-2 font-medium">Bill</th>
                  <th className="px-4 py-2 font-medium text-right">Amount</th>
                  <th className="px-4 py-2 font-medium">Due Date</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody>
                {lockedBills.map((lb) => (
                  <tr key={lb.id} className="border-b border-gray-700/30">
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-gray-200">{lb.vendor_name}</p>
                    </td>
                    <td className="px-4 py-2.5 text-right font-medium text-gray-200">{fmt(lb.amount)}</td>
                    <td className="px-4 py-2.5 text-gray-400 text-xs">{lb.due_date ? new Date(lb.due_date).toLocaleDateString() : '—'}</td>
                    <td className="px-4 py-2.5"><StatusBadge status={lb.status} /></td>
                    <td className="px-4 py-2.5 text-gray-400 text-xs max-w-[200px] truncate">{lb.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-gray-600">
                  <td className="px-4 py-2 font-semibold text-gray-300">Total</td>
                  <td className="px-4 py-2 text-right font-bold text-blue-400">{fmt(lockedBills.reduce((s, l) => s + (l.amount || 0), 0))}</td>
                  <td colSpan={3}></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Top Vendor Accounts */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 mb-6">
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Top Vendor Accounts</h2>
            <p className="text-xs text-gray-500 mt-0.5">Total: <span className="text-blue-400 font-medium">{fmt(vendorTotal)}</span></p>
          </div>
          <button onClick={openAddVendor} className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg">
            <PlusIcon className="h-4 w-4" /> Add Vendor
          </button>
        </div>
        {vendorAccounts.length === 0 ? (
          <p className="text-gray-500 text-sm text-center py-6">No vendor accounts yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-700">
                  <th className="px-4 py-2 font-medium">Vendor</th>
                  <th className="px-4 py-2 font-medium">As of Date</th>
                  <th className="px-4 py-2 font-medium">Due Date</th>
                  <th className="px-4 py-2 font-medium text-right">Amount</th>
                  <th className="px-4 py-2 font-medium">Notes / Due Dates</th>
                  <th className="px-4 py-2 font-medium">Links</th>
                  <th className="px-4 py-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {vendorAccounts.map((v) => (
                  <tr key={v.id} className="border-b border-gray-700/30 hover:bg-gray-700/20">
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-gray-200">{v.vendor_name}</p>
                      {v.account_info && <p className="text-xs text-gray-500">{v.account_info}</p>}
                    </td>
                    <td className="px-4 py-2.5 text-gray-400 text-xs">{v.as_of_date ? new Date(v.as_of_date).toLocaleDateString() : '—'}</td>
                    <td className="px-4 py-2.5 text-gray-400 text-xs">{v.due_date ? new Date(v.due_date).toLocaleDateString() : '—'}</td>
                    <td className={`px-4 py-2.5 text-right font-medium ${(v.amount || 0) > 0 ? 'text-red-400' : 'text-gray-200'}`}>{fmt(v.amount)}</td>
                    <td className="px-4 py-2.5 text-gray-400 text-xs max-w-[180px] truncate">{v.notes_due_dates || '—'}</td>
                    <td className="px-4 py-2.5 text-xs">
                      {v.links ? (
                        <a href={v.links} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">Login</a>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button onClick={() => openEditVendor(v)} className="p-1 text-gray-400 hover:text-blue-400"><PencilIcon className="h-3.5 w-3.5" /></button>
                        <button onClick={() => handleDeleteVendor(v.id)} className="p-1 text-gray-400 hover:text-red-400"><TrashIcon className="h-3.5 w-3.5" /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-gray-600">
                  <td colSpan={3} className="px-4 py-2 font-semibold text-gray-300">Total</td>
                  <td className="px-4 py-2 text-right font-bold text-blue-400">{fmt(vendorTotal)}</td>
                  <td colSpan={3}></td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

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
          <div className="space-y-4">
            {/* Select All + sort controls */}
            <div className="flex items-center gap-4 text-xs text-gray-400">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={sortedOccurrences.length > 0 && selectedOccurrences.size === sortedOccurrences.length}
                  onChange={toggleSelectAll}
                  className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                />
                Select All
              </label>
              <span className="text-gray-600">|</span>
              <span>Sort by:</span>
              {[{col: 'due_date', label: 'Date'}, {col: 'bill_name', label: 'Name'}, {col: 'amount', label: 'Amount'}, {col: 'status', label: 'Status'}].map(s => (
                <button key={s.col} onClick={() => handleSort(s.col)} className={`hover:text-gray-200 ${sortColumn === s.col ? 'text-blue-400 font-medium' : ''}`}>
                  {s.label}<SortIcon column={s.col} />
                </button>
              ))}
            </div>

            {groupedByWeek.map(({ week, items, subtotal, hasOverdue }) => {
              const weekKey = `W${week}`
              const isCollapsed = collapsedWeeks.has(weekKey)
              const weekRanges = { 1: '1st – 7th', 2: '8th – 14th', 3: '15th – 21st', 4: '22nd – 31st' }

                  return (
                    <div key={weekKey} className="mb-4">
                      {/* Week Header */}
                      <button
                        onClick={() => toggleWeekCollapse(weekKey)}
                        className="w-full flex items-center justify-between py-2 px-3 rounded-lg bg-gray-700/40 hover:bg-gray-700/60 transition-colors mb-1"
                      >
                        <div className="flex items-center gap-3">
                          {isCollapsed
                            ? <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                            : <ChevronUpIcon className="h-4 w-4 text-gray-400" />
                          }
                          <span className="text-sm font-bold text-gray-200 uppercase tracking-wider">Week {week}</span>
                          <span className="text-xs text-gray-500">{weekRanges[week]}</span>
                          {hasOverdue && (
                            <span className="text-xs font-bold text-red-400 uppercase">OVERDUE</span>
                          )}
                        </div>
                        <span className="text-sm font-semibold text-gray-300">{fmt(subtotal)}</span>
                      </button>

                      {!isCollapsed && (
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-left text-gray-500 text-xs">
                                <th className="pb-1 pr-2 w-8"></th>
                                <th className="pb-1 pr-2 w-8">{hasOverdue ? <span className="text-red-500 font-bold">!</span> : ''}</th>
                                <th className="pb-1 font-medium">Bill</th>
                                <th className="pb-1 font-medium text-center w-16">Day</th>
                                <th className="pb-1 font-medium text-right w-28">Amount</th>
                                <th className="pb-1 font-medium text-center w-16" title="Include in cash flow">$</th>
                                <th className="pb-1 font-medium text-center w-16">Auto</th>
                                <th className="pb-1 font-medium text-right w-48">Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {items.map((occ) => {
                                const isOverdue = occ.status === 'overdue'
                                const isPaid = occ.status === 'paid'
                                const isSkipped = occ.status === 'skipped'
                                const isDueSoon = occ.status === 'due_soon'
                                const isCreditDanger = isOverdue && occ.days_overdue >= 25
                                const nameColor = isCreditDanger ? 'text-red-500 font-bold animate-pulse'
                                  : isOverdue ? 'text-red-400 font-medium'
                                  : isPaid || isSkipped ? 'text-gray-600 line-through'
                                  : isDueSoon ? 'text-yellow-300'
                                  : 'text-gray-200'
                                const amountColor = isCreditDanger ? 'text-red-500 font-bold'
                                  : isOverdue ? 'text-red-400'
                                  : isPaid || isSkipped ? 'text-gray-600'
                                  : 'text-gray-100'

                                return (
                                  <tr key={occ.id} className={`border-b border-gray-700/30 hover:bg-gray-700/20 ${selectedOccurrences.has(occ.id) ? 'bg-blue-900/20' : ''}`}>
                                    <td className="py-2 pr-2">
                                      <input
                                        type="checkbox"
                                        checked={selectedOccurrences.has(occ.id)}
                                        onChange={() => toggleSelect(occ.id)}
                                        className="rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                                      />
                                    </td>
                                    <td className="py-2 pr-2 text-center">
                                      {isOverdue && <span className="text-red-500 font-bold text-xs">Y</span>}
                                    </td>
                                    <td className="py-2">
                                      <div className="flex items-center gap-2">
                                        <span className={nameColor}>{occ.bill_name}</span>
                                        {isCreditDanger && <span className="text-[10px] text-red-500 font-semibold bg-red-900/40 px-1.5 py-0.5 rounded">CREDIT DANGER</span>}
                                        <StatusBadge status={occ.status} />
                                      </div>
                                      <p className="text-gray-500 text-xs">{occ.vendor_name}{occ.notes ? ` — ${occ.notes}` : ''}</p>
                                    </td>
                                    <td className="py-2 text-center">
                                      <span className={`font-mono text-sm ${isOverdue ? 'text-red-400' : 'text-gray-300'}`}>
                                        {new Date(occ.due_date).getDate()}
                                      </span>
                                    </td>
                                    <td className={`py-2 text-right font-medium ${amountColor}`}>{fmt(occ.amount)}</td>
                                    <td className="py-2 text-center">
                                      {!isPaid && !isSkipped && (
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
                                    <td className="py-2 text-center">
                                      {occ.is_auto_pay && <span className="text-xs text-blue-400 font-medium">Y</span>}
                                    </td>
                                    <td className="py-2 text-right">
                                      <div className="flex items-center justify-end gap-2">
                                        {!isSkipped && !isPaid && (
                                          <button
                                            onClick={() => openPaymentModal(occ)}
                                            className="px-2 py-0.5 text-xs font-medium rounded bg-emerald-900/50 text-emerald-400 hover:bg-emerald-800 transition-colors"
                                            title="Mark as paid"
                                          >
                                            <CheckCircleIcon className="h-4 w-4 inline -mt-0.5 mr-0.5" />
                                            Paid
                                          </button>
                                        )}
                                        {!isSkipped && !isPaid && (
                                          <button
                                            onClick={() => handleSkip(occ.id)}
                                            className="px-2 py-0.5 text-xs font-medium rounded bg-yellow-900/50 text-yellow-400 hover:bg-yellow-800 transition-colors"
                                            title="Skip this occurrence"
                                          >
                                            <ForwardIcon className="h-4 w-4 inline -mt-0.5 mr-0.5" />
                                            Skip
                                          </button>
                                        )}
                                        <button
                                          onClick={() => {
                                            const parentBill = bills.find(b => b.id === occ.recurring_bill_id)
                                            if (parentBill) openEditForm(parentBill)
                                          }}
                                          className="p-1 text-gray-400 hover:text-blue-400 transition-colors"
                                          title="Edit recurring bill"
                                        >
                                          <PencilIcon className="h-3.5 w-3.5" />
                                        </button>
                                      </div>
                                    </td>
                                  </tr>
                                )
                              })}
                            </tbody>
                            <tfoot>
                              <tr className="border-t border-gray-600">
                                <td colSpan={4} className="py-2 text-right text-xs font-semibold text-gray-400 uppercase tracking-wide pr-2">Week {week} Total</td>
                                <td className="py-2 text-right font-bold text-gray-200">{fmt(subtotal)}</td>
                                <td colSpan={3}></td>
                              </tr>
                            </tfoot>
                          </table>
                        </div>
                      )}
                    </div>
                  )
                })}
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
                        {!bill.included_in_cashflow && (
                          <span className="text-xs bg-yellow-900/50 text-yellow-400 px-1.5 py-0.5 rounded">excluded from cash flow</span>
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
                      <button
                        onClick={() => handleToggleBillCashflow(bill.id)}
                        title={bill.included_in_cashflow ? 'Exclude from cash flow' : 'Include in cash flow'}
                        className={`p-1.5 transition-colors ${bill.included_in_cashflow ? 'text-green-400 hover:text-yellow-400' : 'text-yellow-400 hover:text-green-400'}`}
                      >
                        <CurrencyDollarIcon className="h-4 w-4" />
                      </button>
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
              {form.frequency === 'custom' && (
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Select Months</label>
                  <div className="grid grid-cols-6 gap-2">
                    {MONTH_NAMES.map((name, idx) => {
                      const monthNum = idx + 1
                      const isSelected = form.custom_months.includes(monthNum)
                      return (
                        <button
                          key={monthNum}
                          type="button"
                          onClick={() => {
                            const next = isSelected
                              ? form.custom_months.filter(m => m !== monthNum)
                              : [...form.custom_months, monthNum].sort((a, b) => a - b)
                            setForm({ ...form, custom_months: next })
                          }}
                          className={`px-2 py-1.5 text-xs rounded-lg font-medium transition-colors ${
                            isSelected
                              ? 'bg-blue-600 text-white'
                              : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                          }`}
                        >
                          {name}
                        </button>
                      )
                    })}
                  </div>
                  {form.custom_months.length > 0 && (
                    <p className="text-xs text-gray-500 mt-1">Selected: {form.custom_months.map(m => MONTH_NAMES[m - 1]).join(', ')}</p>
                  )}
                </div>
              )}
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
                <label className="flex items-center gap-2 text-sm text-gray-300">
                  <input
                    type="checkbox"
                    checked={form.included_in_cashflow}
                    onChange={(e) => setForm({ ...form, included_in_cashflow: e.target.checked })}
                    className="rounded bg-gray-700 border-gray-600"
                  />
                  Include in Cash Flow
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
            <p className="text-sm text-gray-400 mb-1">
              <span className="text-gray-200 font-medium">{paymentTarget.bill_name}</span>
            </p>
            <p className="text-sm text-gray-400 mb-4">
              <span className="text-gray-300">{paymentTarget.vendor_name}</span> &mdash; ${paymentTarget.amount?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
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

      {/* Vendor Account Modal */}
      {showVendorForm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-100">{editingVendor ? 'Edit Vendor Account' : 'Add Vendor Account'}</h3>
              <button onClick={() => setShowVendorForm(false)} className="text-gray-400 hover:text-white"><XMarkIcon className="h-5 w-5" /></button>
            </div>
            <form onSubmit={handleVendorSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Vendor Name</label>
                  <input value={vendorForm.vendor_name} onChange={(e) => setVendorForm({ ...vendorForm, vendor_name: e.target.value })} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" required />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Account Info</label>
                  <input value={vendorForm.account_info} onChange={(e) => setVendorForm({ ...vendorForm, account_info: e.target.value })} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g. Account #713046" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">As of Date</label>
                  <input type="date" value={vendorForm.as_of_date} onChange={(e) => setVendorForm({ ...vendorForm, as_of_date: e.target.value })} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Due Date</label>
                  <input type="date" value={vendorForm.due_date} onChange={(e) => setVendorForm({ ...vendorForm, due_date: e.target.value })} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Amount ($)</label>
                  <input type="number" step="0.01" value={vendorForm.amount} onChange={(e) => setVendorForm({ ...vendorForm, amount: e.target.value })} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Notes / Due Dates</label>
                <textarea value={vendorForm.notes_due_dates} onChange={(e) => setVendorForm({ ...vendorForm, notes_due_dates: e.target.value })} rows={2} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Login Link (URL)</label>
                <input type="url" value={vendorForm.links} onChange={(e) => setVendorForm({ ...vendorForm, links: e.target.value })} className="w-full bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm" placeholder="https://..." />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowVendorForm(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-white">Cancel</button>
                <button type="submit" className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg">{editingVendor ? 'Update' : 'Add'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
