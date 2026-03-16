import { useState, useEffect, useRef } from 'react'
import { jobsAPI } from '../services/api'
import { TrashIcon } from '@heroicons/react/24/outline'
import ContextMenu from '../components/ContextMenu'
import toast from 'react-hot-toast'

export default function JobsPage() {
  const [jobs, setJobs] = useState([])
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingJob, setEditingJob] = useState(null)
  const [form, setForm] = useState({ name: '', code: '', address: '', source: 'manual' })
  const [mappings, setMappings] = useState({})
  const [expandedJob, setExpandedJob] = useState(null)
  const [mappingForm, setMappingForm] = useState({ vendor_name: '' })
  const fileRef = useRef()
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadJobs() }, [])

  async function loadJobs() {
    setLoading(true)
    try {
      const res = await jobsAPI.list()
      setJobs(res.data.items)
    } catch {
      toast.error('Failed to load jobs')
    }
    setLoading(false)
  }

  async function loadMappings(jobId) {
    try {
      const res = await jobsAPI.listVendorMappings()
      const jobMappings = (res.data || []).filter(m => m.job_id === jobId)
      setMappings((prev) => ({ ...prev, [jobId]: jobMappings }))
    } catch {}
  }

  async function handleSaveJob() {
    try {
      if (editingJob) {
        await jobsAPI.update(editingJob.id, form)
        toast.success('Job updated')
      } else {
        await jobsAPI.create(form)
        toast.success('Job created')
      }
      setShowForm(false)
      setEditingJob(null)
      setForm({ name: '', code: '', address: '', source: 'manual' })
      loadJobs()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save')
    }
  }

  async function handleJunk(id) {
    try {
      await jobsAPI.junk(id)
      toast.success('Sent to junk')
      loadJobs()
    } catch {
      toast.error('Failed to junk job')
    }
  }

  const contextMenu = ContextMenu({
    items: [
      { label: 'Send to Junk', icon: TrashIcon, danger: true, onClick: (data) => handleJunk(data.id) },
    ],
  })

  async function handleCSVImport(e) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const res = await jobsAPI.importCSV(file)
      toast.success(`Imported ${res.data.imported} jobs (${res.data.skipped} skipped)`)
      loadJobs()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Import failed')
    }
    if (fileRef.current) fileRef.current.value = ''
  }

  async function handleAddMapping(jobId) {
    if (!mappingForm.vendor_name.trim()) return
    try {
      await jobsAPI.createVendorMapping({ vendor_name_pattern: mappingForm.vendor_name.trim(), job_id: jobId })
      setMappingForm({ vendor_name: '' })
      loadMappings(jobId)
      toast.success('Mapping added')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed')
    }
  }

  async function handleDeleteMapping(jobId, mappingId) {
    try {
      await jobsAPI.deleteVendorMapping(mappingId)
      loadMappings(jobId)
      toast.success('Mapping removed')
    } catch {
      toast.error('Failed')
    }
  }

  function toggleExpand(jobId) {
    if (expandedJob === jobId) {
      setExpandedJob(null)
    } else {
      setExpandedJob(jobId)
      if (!mappings[jobId]) loadMappings(jobId)
    }
  }

  const filtered = jobs.filter((j) =>
    j.name.toLowerCase().includes(search.toLowerCase()) ||
    (j.code && j.code.toLowerCase().includes(search.toLowerCase()))
  )

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
        <h1 className="text-2xl font-bold">Jobs</h1>
        <div className="flex gap-3">
          <button
            onClick={async () => {
              if (!window.confirm('Delete all imported jobs? Manually created jobs will be kept.')) return
              try {
                const res = await jobsAPI.deleteImported()
                toast.success(`Deleted ${res.data.deleted} imported jobs`)
                loadJobs()
              } catch { toast.error('Failed to delete imported jobs') }
            }}
            className="px-4 py-2 bg-red-900/50 border border-red-700 rounded-lg text-sm font-medium text-red-400 hover:bg-red-900"
          >
            Clear Imported
          </button>
          <label className="px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm font-medium text-gray-300 cursor-pointer hover:bg-gray-600">
            Import CSV / Excel
            <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" onChange={handleCSVImport} className="hidden" />
          </label>
          <button
            onClick={() => { setShowForm(true); setEditingJob(null); setForm({ name: '', code: '', address: '', source: 'manual' }) }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            Add Job
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="mb-4">
        <input
          type="text"
          placeholder="Search jobs..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full md:w-80 px-4 py-2 border border-gray-600 bg-gray-800 text-gray-200 rounded-lg text-sm"
        />
      </div>

      {/* New/Edit Form */}
      {showForm && (
        <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-100">{editingJob ? 'Edit Job' : 'New Job'}</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Job Name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Job Code</label>
              <input
                type="text"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Address</label>
              <input
                type="text"
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg text-sm"
              />
            </div>
          </div>
          <div className="flex gap-3 mt-4">
            <button onClick={handleSaveJob} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
              {editingJob ? 'Update' : 'Create'}
            </button>
            <button onClick={() => { setShowForm(false); setEditingJob(null) }} className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Jobs List */}
      <div className="bg-gray-800 rounded-xl shadow-sm border border-gray-700 overflow-hidden overflow-x-auto">
        <table className="w-full min-w-[500px]">
          <thead className="bg-gray-900 border-b border-gray-700">
            <tr>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Name</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Code</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Address</th>
              <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Source</th>
              <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center py-10 text-gray-400">No jobs found</td>
              </tr>
            )}
            {filtered.map((j) => (
              <>
                <tr key={j.id} className="hover:bg-gray-700/50 cursor-context-menu" onContextMenu={(e) => contextMenu.show(e, { id: j.id })}>
                  <td className="px-4 py-3 text-sm font-medium text-gray-200">{j.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-400">{j.code || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-400">{j.address || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      j.source === 'buildertrend' ? 'bg-purple-900/50 text-purple-400' : 'bg-gray-700 text-gray-300'
                    }`}>
                      {j.source}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => toggleExpand(j.id)} className="text-sm text-gray-400 hover:text-gray-200 mr-3">
                      {expandedJob === j.id ? 'Hide' : 'Mappings'}
                    </button>
                    <button
                      onClick={() => { setEditingJob(j); setForm({ name: j.name, code: j.code || '', address: j.address || '', source: j.source }); setShowForm(true) }}
                      className="text-sm text-blue-400 hover:underline"
                    >
                      Edit
                    </button>
                  </td>
                </tr>
                {expandedJob === j.id && (
                  <tr key={`${j.id}-mappings`}>
                    <td colSpan={5} className="bg-gray-900 px-6 py-4">
                      <h4 className="text-sm font-medium mb-2 text-gray-200">Vendor → Job Mappings</h4>
                      <p className="text-xs text-gray-400 mb-3">When a bill from this vendor arrives, auto-assign it to this job.</p>
                      <div className="flex gap-2 mb-3">
                        <input
                          type="text"
                          placeholder="Vendor name..."
                          value={mappingForm.vendor_name}
                          onChange={(e) => setMappingForm({ vendor_name: e.target.value })}
                          className="px-3 py-1.5 border border-gray-600 bg-gray-800 text-gray-200 rounded text-sm w-64"
                        />
                        <button onClick={() => handleAddMapping(j.id)} className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm">
                          Add
                        </button>
                      </div>
                      {(mappings[j.id] || []).length === 0 ? (
                        <p className="text-xs text-gray-500">No mappings yet</p>
                      ) : (
                        <div className="space-y-1">
                          {(mappings[j.id] || []).map((m) => (
                            <div key={m.id} className="flex items-center justify-between bg-gray-800 px-3 py-2 rounded border border-gray-700 text-sm text-gray-300">
                              <span>{m.vendor_name_pattern}</span>
                              <button onClick={() => handleDeleteMapping(j.id, m.id)} className="text-red-500 text-xs hover:underline">Remove</button>
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
      {contextMenu.menu}
    </div>
  )
}
