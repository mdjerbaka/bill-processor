import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { invoicesAPI, jobsAPI } from '../services/api'
import api from '../services/api'
import toast from 'react-hot-toast'

export default function InvoiceDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [invoice, setInvoice] = useState(null)
  const [jobs, setJobs] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({})
  const [loading, setLoading] = useState(true)
  const [docUrl, setDocUrl] = useState(null)

  useEffect(() => {
    loadInvoice()
    loadJobs()
    return () => {
      // Revoke blob URL on unmount to free memory
      if (docUrl) URL.revokeObjectURL(docUrl)
    }
  }, [id])

  async function loadInvoice() {
    setLoading(true)
    try {
      const res = await invoicesAPI.get(id)
      setInvoice(res.data)
      setForm(res.data)
      // Load document preview
      if (res.data.attachment_id) {
        try {
          const docRes = await api.get(`/attachments/${res.data.attachment_id}`, { responseType: 'blob' })
          const url = URL.createObjectURL(docRes.data)
          setDocUrl(url)
        } catch { /* attachment may be missing from disk */ }
      }
      // Load match suggestions
      try {
        const sugRes = await invoicesAPI.getMatchSuggestions(id)
        setSuggestions(sugRes.data)
      } catch {}
    } catch {
      toast.error('Invoice not found')
      navigate('/invoices')
    }
    setLoading(false)
  }

  async function loadJobs() {
    try {
      const res = await jobsAPI.list()
      setJobs(res.data.items)
    } catch {}
  }

  async function handleSave() {
    try {
      const res = await invoicesAPI.update(id, {
        vendor_name: form.vendor_name,
        invoice_number: form.invoice_number,
        invoice_date: form.invoice_date,
        due_date: form.due_date,
        total_amount: form.total_amount ? parseFloat(form.total_amount) : null,
        subtotal: form.subtotal ? parseFloat(form.subtotal) : null,
        tax_amount: form.tax_amount ? parseFloat(form.tax_amount) : null,
        job_id: form.job_id ? parseInt(form.job_id) : null,
      })
      setInvoice(res.data)
      setEditing(false)
      toast.success('Invoice updated')
    } catch (err) {
      toast.error('Failed to update')
    }
  }

  async function handleApprove() {
    try {
      const res = await invoicesAPI.approve(id)
      setInvoice(res.data)
      toast.success('Invoice approved and added to payables')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to approve')
    }
  }

  async function handleJunk() {
    if (!confirm('Send this invoice to the junk bin?')) return
    try {
      await invoicesAPI.junk(id)
      toast.success('Sent to junk')
      navigate('/invoices')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to junk')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  if (!invoice) return null

  const statusColors = {
    pending: 'bg-gray-700 text-gray-300',
    extracted: 'bg-blue-900/50 text-blue-400',
    needs_review: 'bg-yellow-900/50 text-yellow-400',
    auto_matched: 'bg-green-900/50 text-green-400',
    approved: 'bg-emerald-900/50 text-emerald-400',
    sent_to_qb: 'bg-purple-900/50 text-purple-400',
    paid: 'bg-gray-700 text-gray-400',
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button onClick={() => navigate('/invoices')} className="text-sm text-blue-400 hover:underline mb-1">
            ← Back to Invoices
          </button>
          <h1 className="text-2xl font-bold text-gray-100">{invoice.vendor_name || 'Unknown Vendor'}</h1>
          <p className="text-gray-400">Invoice #{invoice.invoice_number || 'N/A'}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1.5 rounded-full text-sm font-medium ${statusColors[invoice.status] || ''}`}>
            {invoice.status.replace(/_/g, ' ')}
          </span>
          {invoice.confidence_score != null && (
            <span className="text-sm text-gray-400">
              {Math.round(invoice.confidence_score * 100)}% confidence
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Document Preview */}
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-100">Document</h2>
          {invoice.error_message && (
            <div className="mb-4 p-3 bg-yellow-900/30 border border-yellow-700 rounded-lg">
              <p className="text-sm font-medium text-yellow-400">OCR extraction failed</p>
              <p className="text-xs text-yellow-500 mt-1">{invoice.error_message.slice(0, 200)}</p>
              <p className="text-xs text-gray-400 mt-1">Click "Edit" to enter invoice details manually.</p>
            </div>
          )}
          {invoice.attachment_id && docUrl ? (
            <div className="bg-gray-700 rounded-lg p-4 min-h-[400px] flex flex-col">
              <iframe
                src={docUrl}
                className="w-full h-[600px] rounded border border-gray-600 flex-1"
                title="Invoice document"
              />
              <button
                onClick={() => window.open(docUrl, '_blank')}
                className="mt-3 w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                View Bill in New Tab
              </button>
            </div>
          ) : invoice.attachment_id ? (
            <div className="bg-gray-700 rounded-lg p-4 min-h-[400px] flex flex-col items-center justify-center gap-3 text-gray-400">
              <p>Preview not available</p>
              <button
                onClick={async () => {
                  try {
                    const docRes = await api.get(`/attachments/${invoice.attachment_id}`, { responseType: 'blob' })
                    const url = URL.createObjectURL(docRes.data)
                    window.open(url, '_blank')
                  } catch {
                    toast.error('Could not load attachment')
                  }
                }}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                View Bill in New Tab
              </button>
            </div>
          ) : invoice.email_id ? (
            <div className="bg-gray-700 rounded-lg p-4 min-h-[400px] flex items-center justify-center text-gray-400">
              No attachment found for this email
            </div>
          ) : (
            <div className="bg-gray-700 rounded-lg p-4 min-h-[400px] flex items-center justify-center text-gray-400">
              No document attached
            </div>
          )}
        </div>

        {/* Right: Extracted Data */}
        <div className="space-y-6">
          {/* Invoice Details */}
          <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-100">Invoice Details</h2>
              {!editing && (
                <button
                  onClick={() => setEditing(true)}
                  className="text-sm text-blue-400 hover:underline"
                >
                  Edit
                </button>
              )}
            </div>

            <div className="space-y-3">
              {[
                { label: 'Vendor', key: 'vendor_name', type: 'text' },
                { label: 'Invoice #', key: 'invoice_number', type: 'text' },
                { label: 'Invoice Date', key: 'invoice_date', type: 'date' },
                { label: 'Due Date', key: 'due_date', type: 'date' },
                { label: 'Total Amount', key: 'total_amount', type: 'number', prefix: '$' },
                { label: 'Subtotal', key: 'subtotal', type: 'number', prefix: '$' },
                { label: 'Tax', key: 'tax_amount', type: 'number', prefix: '$' },
              ].map(({ label, key, type, prefix }) => (
                <div key={key} className="flex items-center justify-between py-2 border-b border-gray-700 last:border-0">
                  <span className="text-sm text-gray-400">{label}</span>
                  {editing ? (
                    <input
                      type={type === 'date' ? 'date' : type === 'number' ? 'number' : 'text'}
                      value={
                        type === 'date' && form[key]
                          ? new Date(form[key]).toISOString().split('T')[0]
                          : form[key] ?? ''
                      }
                      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                      className="px-2 py-1 border border-gray-600 bg-gray-700 text-gray-200 rounded text-sm w-48 text-right"
                      step={type === 'number' ? '0.01' : undefined}
                    />
                  ) : (
                    <span className="text-sm font-medium text-gray-200">
                      {type === 'number' && invoice[key] != null
                        ? `${prefix || ''}${parseFloat(invoice[key]).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
                        : type === 'date' && invoice[key]
                          ? new Date(invoice[key]).toLocaleDateString()
                          : invoice[key] || '—'
                      }
                    </span>
                  )}
                </div>
              ))}

              {/* Job assignment */}
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-gray-400">Job</span>
                {editing ? (
                  <select
                    value={form.job_id || ''}
                    onChange={(e) => setForm({ ...form, job_id: e.target.value })}
                    className="px-2 py-1 border border-gray-600 bg-gray-700 text-gray-200 rounded text-sm w-48"
                  >
                    <option value="">— Select Job —</option>
                    {jobs.map((j) => (
                      <option key={j.id} value={j.id}>{j.name}</option>
                    ))}
                  </select>
                ) : (
                  <span className="text-sm font-medium text-gray-200">{invoice.job_name || '—'}</span>
                )}
              </div>
            </div>

            {editing && (
              <div className="flex gap-3 mt-4">
                <button
                  onClick={handleSave}
                  className="flex-1 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
                >
                  Save Changes
                </button>
                <button
                  onClick={() => { setEditing(false); setForm(invoice) }}
                  className="flex-1 py-2 border border-gray-600 text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-700"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

          {/* Job Match Suggestions */}
          {suggestions.length > 0 && (
            <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6">
              <h2 className="text-lg font-semibold mb-4 text-gray-100">Suggested Jobs</h2>
              <div className="space-y-2">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setForm({ ...form, job_id: s.job_id })
                      setEditing(true)
                    }}
                    className="w-full flex items-center justify-between p-3 rounded-lg border border-gray-700 hover:border-blue-500 hover:bg-blue-900/30 transition-colors text-left"
                  >
                    <div>
                      <p className="font-medium text-sm text-gray-200">{s.job_name}</p>
                      <p className="text-xs text-gray-400">{s.reason}</p>
                    </div>
                    <span className={`text-sm font-medium ${
                      s.confidence >= 0.8 ? 'text-green-600' : 'text-yellow-600'
                    }`}>
                      {Math.round(s.confidence * 100)}%
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Line Items */}
          {invoice.line_items?.length > 0 && (
            <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6">
              <h2 className="text-lg font-semibold mb-4 text-gray-100">Line Items</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left py-2 text-gray-400 font-medium">Description</th>
                    <th className="text-right py-2 text-gray-400 font-medium">Qty</th>
                    <th className="text-right py-2 text-gray-400 font-medium">Price</th>
                    <th className="text-right py-2 text-gray-400 font-medium">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.line_items.map((li, i) => (
                    <tr key={i} className="border-b border-gray-700 last:border-0">
                      <td className="py-2 text-gray-300">{li.description || '—'}</td>
                      <td className="py-2 text-right text-gray-400">{li.quantity ?? '—'}</td>
                      <td className="py-2 text-right text-gray-400">{li.unit_price != null ? `$${li.unit_price.toFixed(2)}` : '—'}</td>
                      <td className="py-2 text-right font-medium text-gray-200">{li.amount != null ? `$${li.amount.toFixed(2)}` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            {['needs_review', 'extracted', 'auto_matched'].includes(invoice.status) && (
              <button
                onClick={handleApprove}
                className="flex-1 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700"
              >
                Approve & Add to Payables
              </button>
            )}
            <button
              onClick={handleJunk}
              className="py-2.5 px-4 bg-gray-700 text-red-400 border border-gray-600 rounded-lg font-medium hover:bg-gray-600"
            >
              Send to Junk
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
