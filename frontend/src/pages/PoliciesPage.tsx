import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { BookOpen, Plus, Loader2, CheckCircle, XCircle, Trash2 } from 'lucide-react'
import apiClient from '@/api/client'
import toast from 'react-hot-toast'
import clsx from 'clsx'

const POLICY_TYPES = [
  { id: 'block_merge', label: 'Block Merge', desc: 'Block PR merge when findings exceed threshold' },
  { id: 'require_review', label: 'Require Review', desc: 'Flag PR for human review' },
  { id: 'create_ticket', label: 'Create Ticket', desc: 'Auto-create Jira/Linear ticket for findings' },
  { id: 'notify', label: 'Notify', desc: 'Send alert to configured channels' },
  { id: 'auto_fix', label: 'Auto-Fix', desc: 'Automatically apply verified fixes' },
]

export default function PoliciesPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', policy_type: 'block_merge', severity_threshold: 'critical', description: '' })

  const { data, isLoading } = useQuery({
    queryKey: ['policies'],
    queryFn: () => apiClient.get('/policies').then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (p: any) => apiClient.post('/policies', p),
    onSuccess: () => { toast.success('Policy created'); qc.invalidateQueries({ queryKey: ['policies'] }); setShowForm(false) },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to create policy'),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => apiClient.patch(`/policies/${id}`, { is_active: active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['policies'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/policies/${id}`),
    onSuccess: () => { toast.success('Policy deleted'); qc.invalidateQueries({ queryKey: ['policies'] }) },
  })

  const policies: any[] = data?.policies || []

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div><h1 className="page-title">Policies</h1><p className="text-muted mt-1">Policy-as-code rules enforced on every scan. {policies.length} policies configured.</p></div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-sm"><Plus className="w-4 h-4"/>New Policy</button>
      </div>

      {showForm && (
        <div className="card p-5 space-y-4">
          <h3 className="section-title">Create Policy</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Policy name</label>
              <input value={form.name} onChange={e => setForm(p => ({...p, name: e.target.value}))} className="input" placeholder="e.g. Block critical findings" />
            </div>
            <div>
              <label className="label">Type</label>
              <select value={form.policy_type} onChange={e => setForm(p => ({...p, policy_type: e.target.value}))} className="input bg-white">
                {POLICY_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Severity threshold</label>
              <select value={form.severity_threshold} onChange={e => setForm(p => ({...p, severity_threshold: e.target.value}))} className="input bg-white">
                {['critical','high','medium','low'].map(s => <option key={s} value={s} className="capitalize">{s.charAt(0).toUpperCase()+s.slice(1)}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Description</label>
              <input value={form.description} onChange={e => setForm(p => ({...p, description: e.target.value}))} className="input" placeholder="Optional description" />
            </div>
          </div>
          <div className="flex gap-3">
            <button onClick={() => createMutation.mutate(form)} disabled={!form.name || createMutation.isPending} className="btn-primary text-sm">
              {createMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin"/> : 'Create Policy'}
            </button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        {isLoading ? <div className="p-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-400"/></div>
        : policies.length === 0 ? (
          <div className="p-12 text-center">
            <BookOpen className="w-10 h-10 mx-auto mb-3 text-gray-200"/>
            <div className="text-gray-500 font-medium">No policies yet</div>
            <div className="text-sm text-gray-400 mt-1">Create a policy to enforce security rules on every scan</div>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {policies.map((p: any) => (
              <div key={p.id} className="flex items-center gap-4 px-6 py-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">{p.name}</span>
                    <span className="badge badge-info text-xs">{p.policy_type.replace('_',' ')}</span>
                    <span className={clsx('badge text-xs', p.severity_threshold==='critical'?'badge-critical':p.severity_threshold==='high'?'badge-high':'badge-medium')}>
                      {p.severity_threshold}+
                    </span>
                  </div>
                  {p.description && <div className="text-sm text-gray-500 mt-0.5">{p.description}</div>}
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={() => toggleMutation.mutate({ id: p.id, active: !p.is_active })}
                    className={clsx('relative w-10 h-5 rounded-full transition-colors', p.is_active ? 'bg-sentinel-600' : 'bg-gray-300')}>
                    <span className={clsx('absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow', p.is_active ? 'translate-x-5' : 'translate-x-0.5')} />
                  </button>
                  <button onClick={() => deleteMutation.mutate(p.id)} className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50 transition-colors">
                    <Trash2 className="w-4 h-4"/>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
