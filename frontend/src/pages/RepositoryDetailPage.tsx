import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ArrowLeft, Settings, Play, Loader2, Unplug } from 'lucide-react'
import apiClient from '@/api/client'
import type { Repository, Scan } from '@/types'
import { format, parseISO } from 'date-fns'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function RepositoryDetailPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const qc = useQueryClient()
  const [triggerLoading, setTriggerLoading] = useState(false)

  const { data: repo, isLoading } = useQuery({
    queryKey: ['repo', repoId],
    queryFn: () => apiClient.get(`/repos/${repoId}`).then(r => r.data as Repository),
  })
  const { data: scansData } = useQuery({
    queryKey: ['repo-scans', repoId],
    queryFn: () => apiClient.get(`/repos/${repoId}/scans`, { params: { limit: 10 } }).then(r => r.data),
    enabled: !!repoId,
    refetchInterval: 10000,
  })

  const configMutation = useMutation({
    mutationFn: (update: Partial<Repository>) => apiClient.patch(`/repos/${repoId}`, update),
    onSuccess: () => { toast.success('Repository settings saved'); qc.invalidateQueries({ queryKey: ['repo', repoId] }) },
  })

  const disconnectMutation = useMutation({
    mutationFn: () => apiClient.delete(`/repos/${repoId}`),
    onSuccess: () => {
      toast.success('Repository disconnected')
      qc.invalidateQueries({ queryKey: ['repos'] })
      window.location.href = '/app/repositories'
    },
    onError: (e: any) => {
      toast.error(e?.response?.data?.detail || 'Failed to disconnect repository')
    },
  })

  const triggerScan = async () => {
    setTriggerLoading(true)
    try {
      const { data } = await apiClient.post('/scans/manual', { repository_id: repoId, scope: 'full' })
      const wait = Math.max(0, Math.round((data?.estimated_wait_seconds || 0) / 60))
      const total = Math.max(1, Math.round((data?.estimated_total_seconds || 0) / 60))
      toast.success(`Manual scan queued. Estimated start in ~${wait} min, completion in ~${total} min.`)
      qc.invalidateQueries({ queryKey: ['repo-scans', repoId] })
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Failed to trigger scan')
    } finally { setTriggerLoading(false) }
  }

  if (isLoading) return <div className="p-6 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-sentinel-600" /></div>
  if (!repo) return <div className="p-6 text-center text-gray-500">Repository not found.</div>

  const scans: Scan[] = scansData?.scans || []

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-start gap-3">
        <Link to="/app/repositories" className="p-2 rounded-lg hover:bg-gray-100 mt-1">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="page-title">{repo.name}</h1>
            <span className={clsx('badge', repo.connection_status === 'connected' ? 'badge-success' : 'badge-high')}>
              {repo.connection_status}
            </span>
          </div>
          <div className="text-gray-500 text-sm mt-1">{repo.full_name} · {repo.language || 'Unknown language'} · {repo.default_branch}</div>
        </div>
        <button onClick={triggerScan} disabled={triggerLoading} className="btn-primary text-sm">
          {triggerLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Trigger Scan
        </button>
        <button
          type="button"
          className="btn-secondary text-sm"
          onClick={() => {
            if (!window.confirm(`Disconnect ${repo.full_name}?`)) return
            disconnectMutation.mutate()
          }}
        >
          <Unplug className="w-4 h-4" />
          Disconnect
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Risk Score', value: repo.last_scan_risk_score != null ? `${repo.last_scan_risk_score}/100` : '—', color: repo.last_scan_risk_score && repo.last_scan_risk_score >= 50 ? 'text-red-600' : 'text-green-600' },
          { label: 'Total Scans', value: repo.total_scans, color: 'text-gray-900' },
          { label: 'Open Findings', value: repo.open_findings, color: repo.open_findings > 0 ? 'text-red-600' : 'text-green-600' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card p-5 text-center">
            <div className={`text-3xl font-black ${color}`}>{value}</div>
            <div className="text-sm text-gray-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Config */}
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-5">
            <Settings className="w-4 h-4 text-gray-500" />
            <h3 className="section-title">Scan Settings</h3>
          </div>
          <div className="space-y-4">
            {[
              { label: 'Scan on PR', field: 'scan_on_pr' as keyof Repository, value: repo.scan_on_pr },
              { label: 'Scan on push', field: 'scan_on_push' as keyof Repository, value: repo.scan_on_push },
              { label: 'Auto-fix enabled', field: 'auto_fix_enabled' as keyof Repository, value: repo.auto_fix_enabled },
              { label: 'Block on critical', field: 'block_on_critical' as keyof Repository, value: repo.block_on_critical },
              { label: 'Block on secrets', field: 'block_on_secret' as keyof Repository, value: repo.block_on_secret },
            ].map(({ label, field, value }) => (
              <div key={field} className="flex items-center justify-between">
                <span className="text-sm text-gray-700">{label}</span>
                <button
                  onClick={() => configMutation.mutate({ [field]: !value })}
                  title={`Toggle ${label}`}
                  aria-label={`Toggle ${label}`}
                  className={clsx('relative w-10 h-5 rounded-full transition-colors', value ? 'bg-sentinel-600' : 'bg-gray-300')}
                >
                  <span className={clsx('absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow', value ? 'translate-x-5' : 'translate-x-0.5')} />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Recent scans */}
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="section-title">Recent Scans</h3>
          </div>
          {scans.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">No scans yet — trigger one above</div>
          ) : (
            <div className="divide-y divide-gray-50">
              {scans.map(scan => (
                <Link key={scan.id} to={`/app/scans/${scan.id}`}
                  className="flex items-center gap-3 px-5 py-3 hover:bg-gray-50 transition-colors">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm text-gray-900 truncate">
                      {scan.pr_title || scan.branch || scan.id.slice(0, 8)}
                    </div>
                    <div className="text-xs text-gray-500">{format(parseISO(scan.created_at), 'MMM d, h:mm a')}</div>
                  </div>
                  <span className={clsx('badge text-xs', scan.status === 'completed' ? 'badge-success' : scan.status === 'blocked' ? 'badge-critical' : scan.status === 'running' ? 'bg-blue-100 text-blue-700 border border-blue-200' : 'badge-info')}>
                    {scan.status}
                  </span>
                  {scan.risk_score != null && (
                    <span className={clsx('font-bold text-sm', scan.risk_score >= 50 ? 'text-red-600' : 'text-green-600')}>
                      {scan.risk_score}
                    </span>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
