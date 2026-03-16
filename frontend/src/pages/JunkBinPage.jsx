import { useState, useEffect } from 'react'
import { junkAPI, invoicesAPI, payablesAPI, jobsAPI } from '../services/api'
import { ArrowPathIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

const TABS = ['invoices', 'payables', 'jobs']

export default function JunkBinPage() {
  const [data, setData] = useState({ invoices: [], payables: [], jobs: [] })
  const [tab, setTab] = useState('invoices')
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadJunk() }, [])

  async function loadJunk() {
    setLoading(true)
    try {
      const res = await junkAPI.list()
      setData(res.data)
    } catch {
      toast.error('Failed to load junk bin')
    }
    setLoading(false)
  }

  async function handleRestore(type, id) {
    try {
      if (type === 'invoice') await invoicesAPI.restore(id)
      else if (type === 'payable') await payablesAPI.restore(id)
      else if (type === 'job') await jobsAPI.restore(id)
      toast.success('Restored successfully')
      loadJunk()
    } catch {
      toast.error('Failed to restore')
    }
  }

  const totalCount = data.invoices.length + data.payables.length + data.jobs.length

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
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Junk Bin</h1>
          <p className="text-sm text-gray-400 mt-1">{totalCount} item{totalCount !== 1 ? 's' : ''} in junk</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-800 rounded-lg p-1 w-fit">
        {TABS.map((t) => {
          const count = data[t]?.length || 0
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                tab === t
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)} ({count})
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 overflow-hidden overflow-x-auto">
        {tab === 'invoices' && (
          <table className="w-full">
            <thead className="bg-gray-900 border-b border-gray-700">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Vendor</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Invoice #</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase">Amount</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Junked</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {data.invoices.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-10 text-gray-500">No junked invoices</td></tr>
              ) : data.invoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-gray-700/50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-200">{inv.vendor_name || 'Unknown'}</td>
                  <td className="px-4 py-3 text-sm text-gray-400">{inv.invoice_number || '—'}</td>
                  <td className="px-4 py-3 text-sm text-right font-medium text-gray-200">
                    {inv.total_amount != null ? `$${parseFloat(inv.total_amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-400">{inv.status?.replace(/_/g, ' ')}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {inv.junked_at ? new Date(inv.junked_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleRestore('invoice', inv.id)}
                      className="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
                    >
                      <ArrowPathIcon className="h-4 w-4" />
                      Restore
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === 'payables' && (
          <table className="w-full">
            <thead className="bg-gray-900 border-b border-gray-700">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Vendor</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase">Amount</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Due Date</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Junked</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {data.payables.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-10 text-gray-500">No junked payables</td></tr>
              ) : data.payables.map((p) => (
                <tr key={p.id} className="hover:bg-gray-700/50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-200">{p.vendor_name}</td>
                  <td className="px-4 py-3 text-sm text-right font-medium text-gray-200">
                    ${parseFloat(p.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-400">
                    {p.due_date ? new Date(p.due_date).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-400">{p.status}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {p.junked_at ? new Date(p.junked_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleRestore('payable', p.id)}
                      className="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
                    >
                      <ArrowPathIcon className="h-4 w-4" />
                      Restore
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === 'jobs' && (
          <table className="w-full">
            <thead className="bg-gray-900 border-b border-gray-700">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Name</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Code</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Junked</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {data.jobs.length === 0 ? (
                <tr><td colSpan={4} className="text-center py-10 text-gray-500">No junked jobs</td></tr>
              ) : data.jobs.map((j) => (
                <tr key={j.id} className="hover:bg-gray-700/50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-200">{j.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-400">{j.code || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {j.junked_at ? new Date(j.junked_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleRestore('job', j.id)}
                      className="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
                    >
                      <ArrowPathIcon className="h-4 w-4" />
                      Restore
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
