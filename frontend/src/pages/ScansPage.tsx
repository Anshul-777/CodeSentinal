import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { Activity, ArrowRight, CheckCircle, XCircle, Loader2, Clock, Lock, Play } from 'lucide-react'
import apiClient from '@/api/client'
import type { Scan } from '@/types'
import { format, parseISO } from 'date-fns'
import clsx from 'clsx'

export default function ScansPage() {
  const [status, setStatus] = useState('')
  const [repositoryId, setRepositoryId] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 25

  const { data: reposData } = useQuery({
    queryKey: ['repos'],
    queryFn: () => apiClient.get('/repos').then(r => r.data),
  })
  const repos = reposData?.repositories || []

  const { data, isLoading } = useQuery({
    queryKey: ['scans', { status, repositoryId, offset }],
    queryFn: () => apiClient.get('/scans', { params: { status: status || undefined, repository_id: repositoryId || undefined, limit, offset } }).then(r => r.data),
    refetchInterval: 10000,
  })

  const scans: Scan[] = data?.scans || []
  const total: number = data?.total || 0

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div><h1 className="page-title">Scans</h1><p className="text-muted mt-1">{total} total scans</p></div>
        <div className="flex items-center gap-2">
          <select
            value={repositoryId}
            onChange={e => { setRepositoryId(e.target.value); setOffset(0) }}
            className="input w-auto text-sm"
            aria-label="Repository filter"
            title="Repository filter"
          >
            <option value="">All repositories</option>
            {repos.map((r: any) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
          </select>
          <select value={status} onChange={e => { setStatus(e.target.value); setOffset(0) }} className="input w-auto text-sm" aria-label="Status filter" title="Status filter">
            <option value="">All statuses</option>
            {['queued','running','completed','blocked','failed','cancelled'].map(s => <option key={s} value={s} className="capitalize">{s}</option>)}
          </select>
        </div>
      </div>
      <div className="card overflow-hidden">
        {isLoading ? <div className="p-12 text-center text-gray-400"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div> :
        scans.length === 0 ? <div className="p-16 text-center"><Activity className="w-12 h-12 mx-auto mb-3 text-gray-200"/><p className="text-gray-500">No scans found</p></div> : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100 bg-gray-50 text-left">
              {['Status','Trigger','Branch / PR','Risk','Findings','Duration','Date',''].map(h => <th key={h} className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-gray-50">
              {scans.map(scan => (
                <tr key={scan.id} className="hover:bg-gray-50 group">
                  <td className="px-4 py-3.5">
                    <span className={clsx('badge', scan.status==='completed'&&'badge-success', scan.status==='blocked'&&'badge-critical', scan.status==='running'&&'bg-blue-100 text-blue-700 border border-blue-200', scan.status==='failed'&&'badge-high', scan.status==='queued'&&'badge-info', scan.status==='cancelled'&&'badge-info')}>
                      {scan.status==='running'&&<Loader2 className="w-3 h-3 animate-spin"/>}{scan.status}
                    </span>
                    {scan.merge_blocked && <Lock className="w-3 h-3 text-red-500 ml-1 inline"/>}
                  </td>
                  <td className="px-4 py-3.5"><span className="badge badge-info text-[10px]">{scan.trigger.toUpperCase()}</span></td>
                  <td className="px-4 py-3.5 max-w-[200px]">
                    <div className="text-gray-900 font-medium truncate">{scan.pr_title || scan.branch || '—'}</div>
                    {scan.pr_number && <div className="text-xs text-gray-500">PR #{scan.pr_number}</div>}
                  </td>
                  <td className="px-4 py-3.5">
                    {scan.risk_score != null ? <span className={clsx('font-bold text-sm', scan.risk_score>=80?'text-red-600':scan.risk_score>=50?'text-orange-600':scan.risk_score>=20?'text-yellow-600':'text-green-600')}>{scan.risk_score}</span> : <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-1">
                      {scan.findings_critical > 0 && <span className="badge badge-critical">{scan.findings_critical}</span>}
                      {scan.findings_high > 0 && <span className="badge badge-high">{scan.findings_high}</span>}
                      {scan.findings_medium > 0 && <span className="badge badge-medium">{scan.findings_medium}</span>}
                      {scan.findings_total === 0 && <span className="text-gray-400 text-xs">0</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3.5 text-xs text-gray-500">{scan.duration_seconds ? `${scan.duration_seconds.toFixed(1)}s` : '—'}</td>
                  <td className="px-4 py-3.5 text-xs text-gray-500">{format(parseISO(scan.created_at), 'MMM d, h:mm a')}</td>
                  <td className="px-4 py-3.5"><Link to={`/app/scans/${scan.id}`} className="opacity-0 group-hover:opacity-100 transition-opacity"><ArrowRight className="w-4 h-4 text-gray-400"/></Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {total > limit && (
          <div className="px-5 py-3 border-t border-gray-100 flex justify-between text-sm text-gray-500">
            <span>Showing {offset+1}–{Math.min(offset+limit, total)} of {total}</span>
            <div className="flex gap-2">
              <button disabled={offset===0} onClick={() => setOffset(Math.max(0,offset-limit))} className="btn-secondary text-sm px-3 py-1.5 disabled:opacity-40">Prev</button>
              <button disabled={offset+limit>=total} onClick={() => setOffset(offset+limit)} className="btn-secondary text-sm px-3 py-1.5 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
