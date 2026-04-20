import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plug, Plus, Loader2, Trash2, ExternalLink, CheckCircle } from 'lucide-react'
import apiClient from '@/api/client'
import toast from 'react-hot-toast'

const INTEGRATION_TYPES = [
  { id: 'jira', label: 'Jira', icon: '🎯', desc: 'Auto-create Jira issues for findings', fields: [
    { key: 'base_url', label: 'Jira Base URL', type: 'url', placeholder: 'https://yourorg.atlassian.net' },
    { key: 'api_token', label: 'API Token', type: 'password', placeholder: 'your_jira_api_token' },
    { key: 'email', label: 'Account Email', type: 'email', placeholder: 'you@company.com' },
    { key: 'project_key', label: 'Project Key', type: 'text', placeholder: 'SEC' },
  ]},
  { id: 'linear', label: 'Linear', icon: '⚡', desc: 'Create Linear issues for high/critical findings', fields: [
    { key: 'api_key', label: 'Linear API Key', type: 'password', placeholder: 'lin_api_…' },
    { key: 'team_id', label: 'Team ID', type: 'text', placeholder: 'your_team_id' },
  ]},
  { id: 'github_issues', label: 'GitHub Issues', icon: '🐙', desc: 'Open GitHub Issues directly on your repos', fields: [
    { key: 'note', label: 'Note', type: 'text', placeholder: 'Uses your connected GitHub App credentials automatically' },
  ]},
  { id: 'pagerduty', label: 'PagerDuty', icon: '🚨', desc: 'Page on-call for critical vulnerabilities', fields: [
    { key: 'integration_key', label: 'Integration Key', type: 'password', placeholder: 'your_pagerduty_key' },
  ]},
]

export default function IntegrationsPage() {
  const qc = useQueryClient()
  const [active, setActive] = useState<string | null>(null)
  const [configs, setConfigs] = useState<Record<string, Record<string, string>>>({})

  const { data, isLoading } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => apiClient.get('/integrations').then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: ({ type, cfg }: { type: string; cfg: any }) =>
      apiClient.post('/integrations', { integration_type: type, name: `${type} integration`, config: cfg }),
    onSuccess: () => { toast.success('Integration connected'); qc.invalidateQueries({ queryKey: ['integrations'] }); setActive(null) },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/integrations/${id}`),
    onSuccess: () => { toast.success('Integration removed'); qc.invalidateQueries({ queryKey: ['integrations'] }) },
  })

  const connectedIntegrations: any[] = data?.integrations || []
  const connectedTypes = new Set(connectedIntegrations.map((i: any) => i.integration_type))

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div><h1 className="page-title">Integrations</h1><p className="text-muted mt-1">Connect issue trackers and alerting tools. Findings are automatically routed based on your configuration.</p></div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {INTEGRATION_TYPES.map(it => {
          const isConnected = connectedTypes.has(it.id)
          const isOpen = active === it.id
          return (
            <div key={it.id} className="card overflow-hidden">
              <div className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{it.icon}</span>
                    <div>
                      <div className="font-semibold text-gray-900">{it.label}</div>
                      <div className="text-sm text-gray-500">{it.desc}</div>
                    </div>
                  </div>
                  {isConnected ? (
                    <span className="flex items-center gap-1 text-xs text-green-700"><CheckCircle className="w-3.5 h-3.5"/>Connected</span>
                  ) : (
                    <button onClick={() => setActive(isOpen ? null : it.id)} className="btn-secondary text-sm">
                      <Plus className="w-3.5 h-3.5"/>Connect
                    </button>
                  )}
                </div>

                {isOpen && !isConnected && (
                  <div className="space-y-3 mt-4 pt-4 border-t border-gray-100">
                    {it.fields.map(f => (
                      <div key={f.key}>
                        <label className="label text-xs">{f.label}</label>
                        <input type={f.type} placeholder={f.placeholder}
                          onChange={e => setConfigs(prev => ({ ...prev, [it.id]: { ...prev[it.id], [f.key]: e.target.value } }))}
                          className="input text-sm" />
                      </div>
                    ))}
                    <div className="flex gap-2">
                      <button onClick={() => createMutation.mutate({ type: it.id, cfg: configs[it.id] || {} })}
                        disabled={createMutation.isPending} className="btn-primary text-sm">
                        {createMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin"/> : 'Save Integration'}
                      </button>
                      <button onClick={() => setActive(null)} className="btn-secondary text-sm">Cancel</button>
                    </div>
                  </div>
                )}
              </div>

              {isConnected && connectedIntegrations.filter((i: any) => i.integration_type === it.id).map((ci: any) => (
                <div key={ci.id} className="px-5 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
                  <span className="text-xs text-gray-600">{ci.name}</span>
                  <button onClick={() => deleteMutation.mutate(ci.id)} className="text-xs text-red-600 hover:underline flex items-center gap-1">
                    <Trash2 className="w-3 h-3"/>Remove
                  </button>
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
