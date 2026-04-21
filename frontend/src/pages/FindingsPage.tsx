import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Bug, Filter, Search, ArrowRight, Shield, AlertTriangle, Package, Code2, CheckSquare, ChevronDown } from 'lucide-react'
import apiClient from '@/api/client'
import type { Finding } from '@/types'
import { format, parseISO } from 'date-fns'
import clsx from 'clsx'

const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info']
const AGENT_TYPES = ['static', 'dependency', 'business_logic', 'compliance', 'secret']
const STATUSES = ['open', 'fixed', 'ignored', 'false_positive', 'accepted_risk']

function SevBadge({ s }: { s: string }) {
  const cls: Record<string, string> = { critical: 'badge-critical', high: 'badge-high', medium: 'badge-medium', low: 'badge-low', info: 'badge-info' }
  return <span className={`badge ${cls[s] || 'badge-info'}`}>{s.toUpperCase()}</span>
}

function AgentIcon({ type }: { type: string }) {
  const map: Record<string, { Icon: any; color: string }> = {
    static: { Icon: Bug, color: 'text-red-500' },
    dependency: { Icon: Package, color: 'text-orange-500' },
    business_logic: { Icon: Code2, color: 'text-blue-500' },
    compliance: { Icon: CheckSquare, color: 'text-purple-500' },
    secret: { Icon: Shield, color: 'text-pink-500' },
  }
  const { Icon, color } = map[type] || { Icon: Bug, color: 'text-gray-400' }
  return <Icon className={`w-4 h-4 ${color}`} />
}

export default function FindingsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [severity, setSeverity] = useState(searchParams.get('severity') || '')
  const [agentType, setAgentType] = useState(searchParams.get('agent_type') || '')
  const [status, setStatus] = useState(searchParams.get('status') || 'open')
  const [repositoryId, setRepositoryId] = useState(searchParams.get('repository_id') || '')
  const [offset, setOffset] = useState(0)
  const limit = 50

  const { data: reposData } = useQuery({
    queryKey: ['repos'],
    queryFn: () => apiClient.get('/repos').then((r) => r.data),
  })
  const repos = reposData?.repositories || []

  const { data, isLoading } = useQuery({
    queryKey: ['findings', { search, severity, agentType, status, repositoryId, offset }],
    queryFn: () => apiClient.get('/findings', {
      params: { search: search || undefined, severity: severity || undefined, agent_type: agentType || undefined, status: status || undefined, repository_id: repositoryId || undefined, limit, offset },
    }).then((r) => r.data),
  })

  const findings: Finding[] = data?.findings || []
  const total: number = data?.total || 0

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">Findings</h1>
          <p className="text-muted mt-1">{total} total findings</p>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-[200px]">
            <Search className="w-4 h-4 text-gray-400" />
            <input value={search} onChange={(e) => { setSearch(e.target.value); setOffset(0) }}
              placeholder="Search title, file, description…" className="flex-1 text-sm outline-none text-gray-900 placeholder-gray-400" />
          </div>
          <select value={severity} onChange={(e) => { setSeverity(e.target.value); setOffset(0) }} className="input w-auto text-sm" aria-label="Severity filter" title="Severity filter">
            <option value="">All severities</option>
            {SEVERITIES.map((s) => <option key={s} value={s} className="capitalize">{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
          </select>
          <select value={agentType} onChange={(e) => { setAgentType(e.target.value); setOffset(0) }} className="input w-auto text-sm" aria-label="Agent filter" title="Agent filter">
            <option value="">All agents</option>
            {AGENT_TYPES.map((a) => <option key={a} value={a}>{a.replace('_', ' ')}</option>)}
          </select>
          <select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0) }} className="input w-auto text-sm" aria-label="Status filter" title="Status filter">
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select>
          <select value={repositoryId} onChange={(e) => { setRepositoryId(e.target.value); setOffset(0) }} className="input w-auto text-sm min-w-[240px]" aria-label="Repository filter" title="Repository filter">
            <option value="">All repositories</option>
            {repos.map((r: any) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
          </select>
          {(severity || agentType || search || status !== 'open') && (
            <button onClick={() => { setSearch(''); setSeverity(''); setAgentType(''); setStatus('open'); setRepositoryId(''); setOffset(0) }}
              className="text-sm text-gray-500 hover:text-gray-900 underline">Clear filters</button>
          )}
        </div>
      </div>

      {/* Findings table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-gray-400">Loading findings…</div>
        ) : findings.length === 0 ? (
          <div className="p-16 text-center">
            <Bug className="w-12 h-12 mx-auto mb-4 text-gray-200" />
            <div className="text-gray-500 font-medium">No findings match your filters</div>
            <div className="text-sm text-gray-400 mt-1">Try adjusting the filters above</div>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50 text-left">
                    <th className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Severity</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Title</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Location</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Agent</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                    <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Found</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {findings.map((f) => (
                    <tr key={f.id} className="hover:bg-gray-50 transition-colors group">
                      <td className="px-5 py-3.5"><SevBadge s={f.severity} /></td>
                      <td className="px-4 py-3.5 max-w-xs">
                        <div className="font-medium text-gray-900 truncate">{f.title}</div>
                        {f.cve_id && <div className="text-xs text-red-600 font-mono mt-0.5">{f.cve_id}</div>}
                        {f.fix_available && <span className="text-xs text-green-600 font-medium">✓ Fix available</span>}
                      </td>
                      <td className="px-4 py-3.5 max-w-[200px]">
                        {f.file_path ? (
                          <div className="font-mono text-xs text-gray-600 truncate">{f.file_path}:{f.line_start || ''}</div>
                        ) : f.dependency_name ? (
                          <div className="text-xs text-gray-600">{f.dependency_name}@{f.dependency_version}</div>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-1.5">
                          <AgentIcon type={f.agent_type} />
                          <span className="text-xs text-gray-600 capitalize">{f.agent_type.replace('_', ' ')}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={clsx('badge text-xs capitalize', {
                          'badge-success': f.status === 'fixed',
                          'bg-gray-100 text-gray-500 border border-gray-200': f.status === 'ignored' || f.status === 'false_positive',
                          'badge-info': f.status === 'open',
                        })}>{f.status.replace('_', ' ')}</span>
                      </td>
                      <td className="px-4 py-3.5 text-xs text-gray-500">
                        {f.first_seen_at ? format(parseISO(f.first_seen_at), 'MMM d') : '—'}
                      </td>
                      <td className="px-4 py-3.5">
                        <Link to={`/app/findings/${f.id}`} className="opacity-0 group-hover:opacity-100 transition-opacity">
                          <ArrowRight className="w-4 h-4 text-gray-400" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {total > limit && (
              <div className="px-5 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-500">
                <span>Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
                <div className="flex gap-2">
                  <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))} className="btn-secondary text-sm px-3 py-1.5 disabled:opacity-40">Previous</button>
                  <button disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)} className="btn-secondary text-sm px-3 py-1.5 disabled:opacity-40">Next</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
