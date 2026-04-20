import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Bell, Plus, Loader2, Trash2, Slack, Mail, Webhook } from 'lucide-react'
import apiClient from '@/api/client'
import toast from 'react-hot-toast'

const CHANNELS = [
  { id: 'slack', label: 'Slack', icon: '🔔', desc: 'Post to a Slack channel via webhook or bot token' },
  { id: 'email', label: 'Email', icon: '📧', desc: 'Send email notifications via SMTP' },
  { id: 'teams', label: 'Microsoft Teams', icon: '💬', desc: 'Post via Teams incoming webhook' },
  { id: 'webhook', label: 'Custom Webhook', icon: '🔗', desc: 'POST JSON payload to any HTTP endpoint' },
]

const TRIGGERS = [
  'critical_finding', 'scan_complete', 'fix_applied', 'merge_blocked', 'weekly_digest',
]

export default function NotificationsPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', channel: 'slack', triggers: ['critical_finding'], config: {} as any })

  const { data, isLoading } = useQuery({
    queryKey: ['notification-configs'],
    queryFn: () => apiClient.get('/notifications').then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (p: any) => apiClient.post('/notifications', p),
    onSuccess: () => { toast.success('Notification route created'); qc.invalidateQueries({ queryKey: ['notification-configs'] }); setShowForm(false) },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/notifications/${id}`),
    onSuccess: () => { toast.success('Deleted'); qc.invalidateQueries({ queryKey: ['notification-configs'] }) },
  })

  const configs: any[] = data?.configs || []

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div><h1 className="page-title">Notifications</h1><p className="text-muted mt-1">Route security alerts to Slack, email, Teams, or custom webhooks.</p></div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-sm"><Plus className="w-4 h-4"/>Add Route</button>
      </div>

      {showForm && (
        <div className="card p-5 space-y-4">
          <h3 className="section-title">New Notification Route</h3>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Name</label>
              <input value={form.name} onChange={e => setForm(p=>({...p,name:e.target.value}))} className="input" placeholder="e.g. Security team Slack" /></div>
            <div><label className="label">Channel</label>
              <select value={form.channel} onChange={e => setForm(p=>({...p,channel:e.target.value}))} className="input bg-white">
                {CHANNELS.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select></div>
          </div>
          <div><label className="label">Trigger on</label>
            <div className="flex flex-wrap gap-2 mt-1">
              {TRIGGERS.map(t => (
                <label key={t} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer text-sm transition-all ${form.triggers.includes(t)?'border-sentinel-500 bg-sentinel-50 text-sentinel-700':'border-gray-200 text-gray-600'}`}>
                  <input type="checkbox" checked={form.triggers.includes(t)} onChange={e => setForm(p=>({...p,triggers:e.target.checked?[...p.triggers,t]:p.triggers.filter(x=>x!==t)}))} className="hidden"/>
                  {t.replace(/_/g,' ')}
                </label>
              ))}
            </div>
          </div>
          {form.channel === 'slack' && (
            <div><label className="label">Slack Webhook URL</label>
              <input type="url" onChange={e => setForm(p=>({...p,config:{...p.config,webhook_url:e.target.value}}))} className="input" placeholder="https://hooks.slack.com/services/…" /></div>
          )}
          {form.channel === 'email' && (
            <div><label className="label">To Email Address</label>
              <input type="email" onChange={e => setForm(p=>({...p,config:{...p.config,to:e.target.value}}))} className="input" placeholder="security@company.com" /></div>
          )}
          {form.channel === 'webhook' && (
            <div><label className="label">Webhook URL</label>
              <input type="url" onChange={e => setForm(p=>({...p,config:{...p.config,url:e.target.value}}))} className="input" placeholder="https://your-endpoint.com/hook" /></div>
          )}
          <div className="flex gap-3">
            <button onClick={() => createMutation.mutate(form)} disabled={!form.name||createMutation.isPending} className="btn-primary text-sm">
              {createMutation.isPending?<Loader2 className="w-4 h-4 animate-spin"/>:'Create'}
            </button>
            <button onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        {isLoading ? <div className="p-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-400"/></div>
        : configs.length === 0 ? (
          <div className="p-12 text-center"><Bell className="w-10 h-10 mx-auto mb-3 text-gray-200"/><div className="text-gray-500">No notification routes configured</div></div>
        ) : (
          <div className="divide-y divide-gray-50">
            {configs.map((c: any) => (
              <div key={c.id} className="flex items-center gap-4 px-6 py-4">
                <div className="text-xl">{CHANNELS.find(ch=>ch.id===c.channel)?.icon||'🔔'}</div>
                <div className="flex-1"><div className="font-medium text-gray-900">{c.name}</div>
                  <div className="text-sm text-gray-500 mt-0.5 capitalize">{c.channel} · {(c.triggers||[]).join(', ')}</div></div>
                <button onClick={() => deleteMutation.mutate(c.id)} className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50"><Trash2 className="w-4 h-4"/></button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
