import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ClipboardList, Search, Loader2 } from 'lucide-react'
import apiClient from '@/api/client'
import { format, parseISO } from 'date-fns'
import clsx from 'clsx'

const ACTION_COLORS: Record<string, string> = {
  'user.login': 'bg-blue-100 text-blue-700',
  'user.login_failed': 'bg-red-100 text-red-700',
  'user.registered': 'bg-green-100 text-green-700',
  'user.logout': 'bg-gray-100 text-gray-600',
  'scan.triggered': 'bg-purple-100 text-purple-700',
  'fix.applied': 'bg-green-100 text-green-700',
  'repo.connected': 'bg-indigo-100 text-indigo-700',
  'policy.updated': 'bg-yellow-100 text-yellow-700',
}

export default function AuditLogsPage() {
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 50

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', { search, offset }],
    queryFn: () => apiClient.get('/audit', { params: { search: search || undefined, limit, offset } }).then(r => r.data),
  })

  const logs: any[] = data?.logs || []
  const total: number = data?.total || 0

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div>
        <h1 className="page-title">Audit Logs</h1>
        <p className="text-muted mt-1">Immutable record of all security-relevant actions. {total} total entries.</p>
      </div>

      <div className="card p-4">
        <div className="flex items-center gap-2">
          <Search className="w-4 h-4 text-gray-400" />
          <input value={search} onChange={e => { setSearch(e.target.value); setOffset(0) }}
            placeholder="Search actions, users, resources…"
            className="flex-1 text-sm outline-none text-gray-900 placeholder-gray-400" />
        </div>
      </div>

      <div className="card overflow-hidden">
        {isLoading ? <div className="p-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-400" /></div>
        : logs.length === 0 ? (
          <div className="p-12 text-center">
            <ClipboardList className="w-10 h-10 mx-auto mb-3 text-gray-200" />
            <div className="text-gray-500">No audit log entries yet</div>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-left">
                {['Action','Actor','Resource','Result','IP Address','Time'].map(h => (
                  <th key={h} className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {logs.map((log: any) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span className={`badge text-xs ${ACTION_COLORS[log.action] || 'bg-gray-100 text-gray-600'}`}>
                      {log.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-700 text-xs">{log.actor_email || '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {log.resource_type && <span className="capitalize">{log.resource_type}</span>}
                    {log.resource_name && <span className="text-gray-700 ml-1">{log.resource_name.slice(0, 30)}</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge text-xs ${log.result === 'success' ? 'badge-success' : 'badge-high'}`}>
                      {log.result}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{log.ip_address || '—'}</td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {format(parseISO(log.created_at), 'MMM d, h:mm:ss a')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {total > limit && (
          <div className="px-5 py-3 border-t border-gray-100 flex justify-between text-sm text-gray-500">
            <span>{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
            <div className="flex gap-2">
              <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))} className="btn-secondary text-sm px-3 py-1.5 disabled:opacity-40">Prev</button>
              <button disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)} className="btn-secondary text-sm px-3 py-1.5 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
