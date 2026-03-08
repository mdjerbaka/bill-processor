import { useState, useEffect } from 'react'
import { payablesAPI } from '../services/api'
import { TrashIcon } from '@heroicons/react/24/outline'
import ContextMenu from '../components/ContextMenu'
import toast from 'react-hot-toast'

export default function PayablesPage() {
  const [payables, setPayables] = useState([])
  const [summary, setSummary] = useState({ total_outstanding: 0, total_overdue: 0 })
  const [bankBalance, setBankBalance] = useState(0)
  const [realBalance, setRealBalance] = useState(0)
  const [editingBalance, setEditingBalance] = useState(false)
  const [balanceInput, setBalanceInput] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [payRes, realRes] = await Promise.all([
        payablesAPI.list(),
        payablesAPI.getRealBalance(),
      ])
      setPayables(payRes.data.items)
      setSummary({ total_outstanding: payRes.data.total_outstanding, total_overdue: payRes.data.total_overdue })
      setBankBalance(realRes.data.bank_balance)
      setBalanceInput(realRes.data.bank_balance?.toString() || '0')
      setRealBalance(realRes.data.real_available)
    } catch {
      toast.error('Failed to load payables')
    }
    setLoading(false)
  }

  async function handleSaveBalance() {
    try {
      await payablesAPI.setBankBalance(parseFloat(balanceInput))
      const res = await payablesAPI.getRealBalance()
      setBankBalance(parseFloat(balanceInput))
      setRealBalance(res.data.real_available)
      setEditingBalance(false)
      toast.success('Bank balance updated')
    } catch {
      toast.error('Failed to update')
    }
  }

  async function handleMarkPaid(id) {
    try {
      await payablesAPI.markPaid(id)
      toast.success('Marked as paid')
      loadData()
    } catch {
      toast.error('Failed to mark as paid')
    }
  }

  async function handleJunk(id) {
    try {
      await payablesAPI.junk(id)
      toast.success('Sent to junk')
      loadData()
    } catch {
      toast.error('Failed to junk payable')
    }
  }

  const contextMenu = ContextMenu({
    items: [
      { label: 'Send to Junk', icon: TrashIcon, danger: true, onClick: (data) => handleJunk(data.id) },
    ],
  })

  async function handleExport() {
    try {
      const res = await payablesAPI.exportExcel()
      const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `payables_${new Date().toISOString().slice(0, 10)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Excel exported')
    } catch {
      toast.error('Export failed')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Payables Tracker</h1>
        <button
          onClick={handleExport}
          className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700"
        >
          Export Excel
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Outstanding</p>
          <p className="text-2xl font-bold text-gray-100">
            ${summary.total_outstanding?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Overdue</p>
          <p className="text-2xl font-bold text-red-600">
            ${summary.total_overdue?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Bank Balance</p>
          {editingBalance ? (
            <div className="flex gap-2 mt-1">
              <input
                type="number"
                step="0.01"
                value={balanceInput}
                onChange={(e) => setBalanceInput(e.target.value)}
                className="w-32 px-2 py-1 border border-gray-600 bg-gray-700 text-gray-200 rounded text-sm"
              />
              <button onClick={handleSaveBalance} className="px-2 py-1 bg-blue-600 text-white text-xs rounded">Save</button>
              <button onClick={() => setEditingBalance(false)} className="px-2 py-1 text-xs text-gray-400">Cancel</button>
            </div>
          ) : (
            <p className="text-2xl font-bold text-gray-100 cursor-pointer" onClick={() => setEditingBalance(true)}>
              ${bankBalance?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              <span className="text-xs text-blue-400 ml-2">edit</span>
            </p>
          )}
        </div>
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-5">
          <p className="text-sm text-gray-400">Real Available</p>
          <p className={`text-2xl font-bold ${realBalance < 0 ? 'text-red-600' : 'text-green-600'}`}>
            ${realBalance?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
        </div>
      </div>

      {/* Payables Table */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-900 border-b border-gray-700">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Vendor</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Invoice #</th>
              <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">Amount</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Due Date</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Status</th>
              <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {payables.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-10 text-gray-400">No payables yet</td>
              </tr>
            )}
            {payables.map((p) => {
              const isOverdue = p.status === 'overdue'
              const dueDate = p.due_date ? new Date(p.due_date) : null
              const daysUntil = dueDate ? Math.ceil((dueDate - new Date()) / 86400000) : null
              return (
                <tr key={p.id} className={`${isOverdue ? 'bg-red-900/20' : ''} cursor-context-menu`} onContextMenu={(e) => contextMenu.show(e, { id: p.id })}>
                  <td className="px-4 py-3 text-sm font-medium text-gray-200">{p.vendor_name}</td>
                  <td className="px-4 py-3 text-sm text-gray-400">{p.invoice_number || '—'}</td>
                  <td className="px-4 py-3 text-sm text-right font-medium text-gray-200">
                    ${parseFloat(p.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {dueDate ? (
                      <span>
                        {dueDate.toLocaleDateString()}
                        {daysUntil != null && (
                          <span className={`ml-2 text-xs ${daysUntil < 0 ? 'text-red-600' : daysUntil <= 7 ? 'text-yellow-600' : 'text-gray-400'}`}>
                            {daysUntil < 0 ? `${Math.abs(daysUntil)}d overdue` : `${daysUntil}d`}
                          </span>
                        )}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      isOverdue ? 'bg-red-900/50 text-red-400' : 'bg-yellow-900/50 text-yellow-400'
                    }`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleMarkPaid(p.id)}
                      className="text-sm text-blue-400 hover:underline"
                    >
                      Mark Paid
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {contextMenu.menu}
    </div>
  )
}
