import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bug, Package, Code2, Wrench, CheckSquare, ArrowLeft, Shield,
  Clock, CheckCircle, XCircle, Loader2, AlertTriangle, GitBranch,
  ArrowRight, ExternalLink, Lock, Activity, ChevronDown, ChevronUp,
  FileText, Cpu,
} from 'lucide-react'
import apiClient from '@/api/client'
import { format, parseISO } from 'date-fns'
import { useState } from 'react'
import type { Scan, Finding, AgentState } from '@/types'
import clsx from 'clsx'

const AGENTS = [
  { key: 'static', label: 'Static Analysis', icon: Bug, description: 'Bandit · AST patterns · Secret scanning · LLM semantic analysis', color: 'red' },
  { key: 'dependency', label: 'Dependency Intelligence', icon: Package, description: 'OSV.dev CVE lookup · License risk · SBOM generation', color: 'orange' },
  { key: 'business_logic', label: 'Business Logic Review', icon: Code2, description: 'IDOR · Auth bypass · Race conditions · API contract violations', color: 'blue' },
  { key: 'autofix', label: 'Auto-Fix Agent', icon: Wrench, description: 'Patch generation · Sandbox validation · Test verification', color: 'green' },
  { key: 'compliance', label: 'Compliance Enforcement', icon: CheckSquare, description: 'SOC2 · HIPAA · PCI-DSS 4.0 · GDPR Article 32', color: 'purple' },
]

const COLOR_MAP: Record<string, Record<string, string>> = {
  red: { bg: 'bg-red-50', icon: 'bg-red-500', ring: 'ring-red-200', text: 'text-red-700', border: 'border-red-200' },
  orange: { bg: 'bg-orange-50', icon: 'bg-orange-500', ring: 'ring-orange-200', text: 'text-orange-700', border: 'border-orange-200' },
  blue: { bg: 'bg-blue-50', icon: 'bg-blue-500', ring: 'ring-blue-200', text: 'text-blue-700', border: 'border-blue-200' },
  green: { bg: 'bg-green-50', icon: 'bg-green-500', ring: 'ring-green-200', text: 'text-green-700', border: 'border-green-200' },
  purple: { bg: 'bg-purple-50', icon: 'bg-purple-500', ring: 'ring-purple-200', text: 'text-purple-700', border: 'border-purple-200' },
}

function AgentStateIcon({ state }: { state: AgentState }) {
  if (state === 'running') return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
  if (state === 'completed') return <CheckCircle className="w-4 h-4 text-green-500" />
  if (state === 'failed') return <XCircle className="w-4 h-4 text-red-500" />
  if (state === 'skipped') return <Clock className="w-4 h-4 text-gray-400" />
  return <Clock className="w-4 h-4 text-gray-300" />
}

function AgentStatePill({ state }: { state: AgentState }) {
  const map: Record<AgentState, string> = {
    waiting: 'bg-gray-100 text-gray-500',
    running: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    skipped: 'bg-gray-100 text-gray-500',
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold capitalize ${map[state] || map.waiting}`}>
      <AgentStateIcon state={state} />
      {state}
    </span>
  )
}

function SeverityBadge({ severity }: { severity: string }) {
  const cls: Record<string, string> = {
    critical: 'badge-critical', high: 'badge-high', medium: 'badge-medium', low: 'badge-low', info: 'badge-info',
  }
  return <span className={`badge ${cls[severity] || 'badge-info'}`}>{severity.toUpperCase()}</span>
}

function RiskScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? '#ef4444' : score >= 50 ? '#f97316' : score >= 20 ? '#eab308' : '#22c55e'
  const r = 36, circ = 2 * Math.PI * r
  const dash = ((100 - score) / 100) * circ
  return (
    <div className="relative w-24 h-24 flex items-center justify-center">
      <svg width="96" height="96" className="-rotate-90">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#f3f4f6" strokeWidth="8" />
        <circle cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={circ} strokeDashoffset={dash} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease' }} />
      </svg>
      <div className="absolute text-center">
        <div className="text-2xl font-black" style={{ color }}>{score}</div>
        <div className="text-[10px] text-gray-500 font-medium">/ 100</div>
      </div>
    </div>
  )
}

export default function ScanDetailPage() {
  const { scanId } = useParams<{ scanId: string }>()
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)

  const { data: scan, isLoading } = useQuery({
    queryKey: ['scan', scanId],
    queryFn: () => apiClient.get(`/scans/${scanId}`).then((r) => r.data as Scan),
    refetchInterval: (query) => {
      const data = query.state.data
      return (!data || ['queued', 'running'].includes(data.status)) ? 3000 : false
    },
  })

  const { data: findingsData } = useQuery({
    queryKey: ['scan-findings', scanId],
    queryFn: () => apiClient.get('/findings', { params: { scan_id: scanId, limit: 50 } }).then((r) => r.data),
    enabled: !!scanId && scan?.status === 'completed' || scan?.status === 'blocked',
  })

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-sentinel-600" />
      </div>
    )
  }

  if (!scan) {
    return <div className="p-6 text-center text-gray-500">Scan not found.</div>
  }

  const findings: Finding[] = findingsData?.findings || []
  const isActive = ['queued', 'running'].includes(scan.status)
  const isDone = ['completed', 'blocked', 'failed'].includes(scan.status)
  const isRiskPending = scan.risk_score == null && ['queued', 'running'].includes(scan.status)
  const riskLabel =
    scan.status === 'failed'
      ? 'Failed'
      : scan.status === 'cancelled'
        ? 'Cancelled'
        : scan.risk_level || (isRiskPending ? 'Calculating…' : 'None')

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Back + header */}
      <div className="flex items-start gap-4">
        <Link to="/app/scans" className="p-2 rounded-lg hover:bg-gray-100 mt-1 flex-shrink-0">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="page-title truncate">
              {scan.pr_title || scan.branch || `Scan ${scan.id.slice(0, 8)}`}
            </h1>
            <span className={clsx(
              'badge',
              scan.status === 'completed' && 'badge-success',
              scan.status === 'blocked' && 'badge-critical',
              scan.status === 'running' && 'bg-blue-100 text-blue-700 border border-blue-200',
              scan.status === 'failed' && 'badge-high',
              scan.status === 'queued' && 'badge-info',
            )}>
              {scan.status === 'running' && <Loader2 className="w-3 h-3 animate-spin" />}
              {scan.status.charAt(0).toUpperCase() + scan.status.slice(1)}
            </span>
            {scan.merge_blocked && (
              <span className="flex items-center gap-1 badge badge-critical">
                <Lock className="w-3 h-3" />Merge Blocked
              </span>
            )}
          </div>
          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500 flex-wrap">
            <span className="flex items-center gap-1.5">
              <GitBranch className="w-3.5 h-3.5" />
              {scan.trigger.toUpperCase()} · {scan.branch || scan.base_branch || '—'}
            </span>
            {scan.pr_number && (
              <span>PR #{scan.pr_number}</span>
            )}
            {scan.commit_sha && (
              <span className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">{scan.commit_sha.slice(0, 7)}</span>
            )}
            <span>{format(parseISO(scan.created_at), 'MMM d, yyyy · h:mm a')}</span>
            {scan.duration_seconds && (
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                {scan.duration_seconds.toFixed(1)}s
              </span>
            )}
            {scan.check_run_url && (
              <a href={scan.check_run_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-sentinel-600 hover:underline">
                <ExternalLink className="w-3.5 h-3.5" />GitHub Check
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Merge block alert */}
      {scan.merge_blocked && scan.merge_block_reason && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="card border-l-4 border-l-red-500 bg-red-50 p-5">
          <div className="flex items-start gap-3">
            <Lock className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-red-900 mb-1">Pull Request Merge Blocked</div>
              <div className="text-sm text-red-700">{scan.merge_block_reason}</div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Risk + summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Risk score */}
        <div className="card p-6 flex items-center gap-6">
          {scan.risk_score != null ? (
            <RiskScoreRing score={scan.risk_score} />
          ) : isRiskPending ? (
            <div className="w-24 h-24 rounded-full bg-gray-100 flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : (
            <div className="w-24 h-24 rounded-full bg-gray-100 flex items-center justify-center">
              <span className="text-xl font-black text-gray-400">-</span>
            </div>
          )}
          <div>
            <div className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-1">Risk Score</div>
            <div className="text-2xl font-bold text-gray-900 capitalize">{riskLabel}</div>
            <div className="text-sm text-gray-500 mt-1">
              {scan.files_scanned_count} files · {scan.ai_model || 'AI'} analysis
            </div>
            {scan.ai_provider && (
              <div className="flex items-center gap-1 mt-1 text-xs text-gray-400">
                <Cpu className="w-3 h-3" />{scan.ai_provider}/{scan.ai_model}
              </div>
            )}
          </div>
        </div>

        {/* Findings breakdown */}
        <div className="card p-6">
          <div className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Findings</div>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Critical', value: scan.findings_critical, color: 'text-red-600 bg-red-50' },
              { label: 'High', value: scan.findings_high, color: 'text-orange-600 bg-orange-50' },
              { label: 'Medium', value: scan.findings_medium, color: 'text-yellow-600 bg-yellow-50' },
              { label: 'Low', value: scan.findings_low, color: 'text-blue-600 bg-blue-50' },
              { label: 'Secrets', value: scan.secrets_found, color: 'text-purple-600 bg-purple-50' },
              { label: 'Dep. CVEs', value: scan.dependencies_vulnerable, color: 'text-rose-600 bg-rose-50' },
            ].map((item) => (
              <div key={item.label} className={`rounded-xl p-3 text-center ${item.color}`}>
                <div className="text-xl font-black">{item.value}</div>
                <div className="text-[10px] font-medium mt-0.5">{item.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Compliance + fixes */}
        <div className="card p-6">
          <div className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Compliance & Fixes</div>
          {scan.compliance_results && Object.keys(scan.compliance_results).length > 0 ? (
            <div className="space-y-3">
              {Object.entries(scan.compliance_results).map(([framework, result]: any) => (
                <div key={framework} className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700 uppercase">{framework.replace('_', '-')}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-sentinel-500 rounded-full" style={{ width: `${result.score || 0}%` }} />
                    </div>
                    <span className="text-xs font-bold text-gray-700 w-8 text-right">{result.score || 0}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-gray-400">No compliance data yet</div>
          )}
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Auto-fixes available</span>
              <span className="font-bold text-green-600">{scan.fixes_available}</span>
            </div>
            <div className="flex justify-between text-sm mt-1">
              <span className="text-gray-600">Fixes applied</span>
              <span className="font-bold text-gray-900">{scan.fixes_applied}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Pipeline Visualizer */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-4 h-4 text-sentinel-600" />
            <h2 className="section-title">5-Agent Pipeline</h2>
          </div>
          {isActive && (
            <div className="flex items-center gap-2 text-sm text-blue-600 font-medium">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              Running in parallel…
            </div>
          )}
          {isDone && (
            <div className="text-sm text-gray-500">
              {scan.duration_seconds != null ? `Completed in ${scan.duration_seconds.toFixed(1)}s` : 'Completed'}
            </div>
          )}
        </div>

        {/* Connection line */}
        <div className="px-6 py-6">
          <div className="relative">
            {/* Horizontal connector */}
            <div className="absolute top-6 left-[5%] right-[5%] h-0.5 bg-gray-100 z-0" />

            <div className="relative z-10 grid grid-cols-5 gap-3">
              {AGENTS.map((agent, index) => {
                const state: AgentState = scan.agent_states?.[agent.key as keyof typeof scan.agent_states] || 'waiting'
                const colors = COLOR_MAP[agent.color]
                const Icon = agent.icon
                const duration = scan.agent_durations?.[agent.key]
                const error = scan.agent_errors?.[agent.key]
                const isExpanded = expandedAgent === agent.key
                const result = scan.agent_results?.[agent.key]

                return (
                  <div key={agent.key} className="flex flex-col items-center gap-2">
                    {/* Agent card */}
                    <motion.div
                      className={clsx(
                        'w-full rounded-xl border-2 p-4 cursor-pointer transition-all',
                        state === 'running' && 'border-blue-300 bg-blue-50 shadow-md',
                        state === 'completed' && `border-green-200 ${colors.bg}`,
                        state === 'failed' && 'border-red-300 bg-red-50',
                        state === 'waiting' && 'border-gray-100 bg-white',
                        state === 'skipped' && 'border-gray-100 bg-gray-50',
                      )}
                      animate={state === 'running' ? { scale: [1, 1.02, 1] } : {}}
                      transition={{ duration: 1.5, repeat: state === 'running' ? Infinity : 0 }}
                      onClick={() => setExpandedAgent(isExpanded ? null : agent.key)}
                    >
                      {/* Icon */}
                      <div className="flex items-start justify-between mb-3">
                        <div className={clsx(
                          'w-9 h-9 rounded-xl flex items-center justify-center',
                          state === 'waiting' ? 'bg-gray-100' : state === 'running' ? 'bg-blue-500' : state === 'completed' ? colors.icon : 'bg-red-500'
                        )}>
                          {state === 'running' ? (
                            <Loader2 className="w-4 h-4 text-white animate-spin" />
                          ) : (
                            <Icon className={clsx('w-4 h-4', state === 'waiting' ? 'text-gray-400' : 'text-white')} />
                          )}
                        </div>
                        <AgentStatePill state={state} />
                      </div>

                      <div className={clsx('text-xs font-bold mb-0.5', state === 'waiting' ? 'text-gray-400' : 'text-gray-900')}>
                        Agent {index + 1}
                      </div>
                      <div className={clsx('text-sm font-semibold leading-tight mb-2', state === 'waiting' ? 'text-gray-500' : 'text-gray-900')}>
                        {agent.label}
                      </div>

                      {/* Duration / finding count */}
                      {state === 'completed' && (
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>{result?.findings != null ? `${result.findings} findings` : '—'}</span>
                          {duration && <span>{duration.toFixed(1)}s</span>}
                        </div>
                      )}
                      {state === 'failed' && error && (
                        <div className="text-xs text-red-600 truncate">{error.slice(0, 40)}…</div>
                      )}

                      {/* Expand toggle */}
                      {(state === 'completed' || state === 'failed') && (
                        <div className="mt-2 pt-2 border-t border-gray-100 flex justify-center">
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5 text-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400" />}
                        </div>
                      )}
                    </motion.div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Expanded agent detail */}
          <AnimatePresence>
            {expandedAgent && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-4 overflow-hidden"
              >
                {(() => {
                  const agent = AGENTS.find((a) => a.key === expandedAgent)!
                  const result = scan.agent_results?.[expandedAgent]
                  const error = scan.agent_errors?.[expandedAgent]
                  const colors = COLOR_MAP[agent.color]
                  const Icon = agent.icon
                  const agentFindings = findings.filter((f) => f.agent_type === expandedAgent)

                  return (
                    <div className={clsx('rounded-xl border p-5', colors.border, colors.bg)}>
                      <div className="flex items-center gap-3 mb-4">
                        <div className={`w-8 h-8 rounded-xl ${colors.icon} flex items-center justify-center`}>
                          <Icon className="w-4 h-4 text-white" />
                        </div>
                        <div>
                          <div className="font-semibold text-gray-900">{agent.label} — Detail</div>
                          <div className="text-xs text-gray-500">{agent.description}</div>
                        </div>
                      </div>

                      {error && (
                        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                          <strong>Error:</strong> {error}
                        </div>
                      )}

                      {/* Compliance scores for compliance agent */}
                      {expandedAgent === 'compliance' && scan.compliance_results && (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                          {Object.entries(scan.compliance_results).map(([fw, data]: any) => (
                            <div key={fw} className="bg-white rounded-xl p-3 border border-gray-200 text-center">
                              <div className="text-lg font-black text-gray-900">{data.score ?? 0}%</div>
                              <div className="text-xs font-bold text-gray-500 uppercase mt-0.5">{fw.replace('_', '-')}</div>
                              <div className="text-xs text-gray-400 mt-1">
                                {data.passed ?? 0} pass · {data.failed ?? 0} fail
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Top findings for this agent */}
                      {agentFindings.length > 0 ? (
                        <div className="space-y-2">
                          <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
                            Top Findings ({agentFindings.length})
                          </div>
                          {agentFindings.slice(0, 5).map((f) => (
                            <Link
                              key={f.id}
                              to={`/app/findings/${f.id}`}
                              className="flex items-start gap-3 p-3 bg-white rounded-xl border border-gray-200 hover:border-gray-300 transition-colors"
                            >
                              <SeverityBadge severity={f.severity} />
                              <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-gray-900 truncate">{f.title}</div>
                                {f.file_path && (
                                  <div className="text-xs text-gray-500 mt-0.5 font-mono truncate">
                                    {f.file_path}:{f.line_start}
                                  </div>
                                )}
                              </div>
                              {f.fix_available && (
                                <span className="badge badge-success text-[10px] flex-shrink-0">Fix available</span>
                              )}
                              <ArrowRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
                            </Link>
                          ))}
                          {agentFindings.length > 5 && (
                            <Link to={`/app/findings?scan_id=${scan.id}&agent_type=${expandedAgent}`}
                              className="block text-center text-sm text-sentinel-600 hover:underline py-2">
                              View all {agentFindings.length} findings →
                            </Link>
                          )}
                        </div>
                      ) : (
                        <div className="text-center py-4 text-sm text-gray-500">
                          {scan.agent_states?.[expandedAgent as keyof typeof scan.agent_states] === 'completed'
                            ? '✓ No findings — this agent found nothing to report'
                            : 'Findings will appear here once the agent completes'}
                        </div>
                      )}
                    </div>
                  )
                })()}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* All findings */}
      {findings.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="section-title">All Findings ({findings.length})</h2>
            <Link to={`/app/findings?scan_id=${scanId}`} className="text-sm text-sentinel-600 hover:underline">
              View in Findings →
            </Link>
          </div>
          <div className="divide-y divide-gray-50">
            {findings.map((finding) => (
              <Link
                key={finding.id}
                to={`/app/findings/${finding.id}`}
                className="flex items-start gap-4 px-6 py-4 hover:bg-gray-50 transition-colors"
              >
                <SeverityBadge severity={finding.severity} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900">{finding.title}</span>
                    {finding.fix_available && (
                      <span className="badge badge-success text-[10px]">Auto-fix available</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-1 flex items-center gap-3">
                    {finding.file_path && (
                      <span className="font-mono">{finding.file_path}:{finding.line_start}</span>
                    )}
                    <span className="capitalize">{finding.agent_type.replace('_', ' ')}</span>
                    {finding.cve_id && <span className="font-mono text-red-600">{finding.cve_id}</span>}
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-300 flex-shrink-0 mt-1" />
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
