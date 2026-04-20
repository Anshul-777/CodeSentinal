import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  ArrowLeft, AlertTriangle, Shield, Code2, Wrench, CheckCircle,
  XCircle, FileText, ExternalLink, MessageSquare, ThumbsDown,
  Package, ChevronDown, ChevronUp, Loader2, Clock, Lock,
} from 'lucide-react'
import apiClient from '@/api/client'
import { useState } from 'react'
import { format, parseISO } from 'date-fns'
import type { Finding, Fix } from '@/types'
import ReactDiffViewer from 'react-diff-viewer-continued'
import toast from 'react-hot-toast'
import clsx from 'clsx'

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, { cls: string; dot: string }> = {
    critical: { cls: 'bg-red-100 text-red-800 border-red-200', dot: 'bg-red-500' },
    high: { cls: 'bg-orange-100 text-orange-800 border-orange-200', dot: 'bg-orange-500' },
    medium: { cls: 'bg-yellow-100 text-yellow-800 border-yellow-200', dot: 'bg-yellow-500' },
    low: { cls: 'bg-blue-100 text-blue-800 border-blue-200', dot: 'bg-blue-400' },
    info: { cls: 'bg-gray-100 text-gray-700 border-gray-200', dot: 'bg-gray-400' },
  }
  const { cls, dot } = map[severity] || map.info
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold border ${cls}`}>
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      {severity.toUpperCase()}
    </span>
  )
}

function FixStatusBadge({ status, sandboxStatus }: { status: string; sandboxStatus: string }) {
  if (status === 'verified') return <span className="badge badge-success">✓ Verified</span>
  if (sandboxStatus === 'passed') return <span className="badge badge-success">Sandbox passed</span>
  if (sandboxStatus === 'failed') return <span className="badge badge-high">Sandbox failed</span>
  if (status === 'rejected') return <span className="badge badge-high">Rejected</span>
  if (sandboxStatus === 'running') return <span className="badge bg-blue-100 text-blue-700 border border-blue-200"><Loader2 className="w-3 h-3 animate-spin" />Testing…</span>
  return <span className="badge badge-info">{status}</span>
}

export default function FindingDetailPage() {
  const { findingId } = useParams<{ findingId: string }>()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [showFpForm, setShowFpForm] = useState(false)
  const [fpReason, setFpReason] = useState('')
  const [showDiff, setShowDiff] = useState(true)

  const { data: finding, isLoading } = useQuery({
    queryKey: ['finding', findingId],
    queryFn: () => apiClient.get(`/findings/${findingId}`).then((r) => r.data as Finding),
  })

  const { data: fixesData } = useQuery({
    queryKey: ['finding-fixes', findingId],
    queryFn: () => apiClient.get('/findings', { params: { finding_id: findingId } }).then(() =>
      apiClient.get(`/findings/${findingId}`).then((r) => r.data)
    ),
    enabled: !!finding?.fix_available,
  })

  const fpMutation = useMutation({
    mutationFn: (reason: string) => apiClient.post(`/findings/${findingId}/false-positive`, { reason }),
    onSuccess: () => {
      toast.success('Marked as false positive — this will improve future scans.')
      qc.invalidateQueries({ queryKey: ['finding', findingId] })
      setShowFpForm(false)
    },
  })

  if (isLoading) return <div className="p-6 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-sentinel-600" /></div>
  if (!finding) return <div className="p-6 text-center text-gray-500">Finding not found.</div>

  const fixes: Fix[] = []

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start gap-4">
        <button onClick={() => navigate(-1)} className="p-2 rounded-lg hover:bg-gray-100 mt-1 flex-shrink-0">
          <ArrowLeft className="w-4 h-4 text-gray-500" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-3 flex-wrap mb-2">
            <SeverityBadge severity={finding.severity} />
            {finding.is_false_positive && (
              <span className="badge bg-gray-100 text-gray-600 border border-gray-200">False Positive</span>
            )}
            {finding.fix_available && (
              <span className="badge badge-success">Auto-fix available</span>
            )}
          </div>
          <h1 className="text-xl font-bold text-gray-900 leading-snug">{finding.title}</h1>
          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500 flex-wrap">
            {finding.rule_id && <span className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">{finding.rule_id}</span>}
            {finding.cve_id && <span className="font-mono text-xs bg-red-50 text-red-700 px-2 py-0.5 rounded border border-red-200">{finding.cve_id}</span>}
            {finding.cwe_id && <span className="font-mono text-xs bg-orange-50 text-orange-700 px-2 py-0.5 rounded border border-orange-200">{finding.cwe_id}</span>}
            {finding.cvss_score && (
              <span className="text-xs font-semibold">CVSS {finding.cvss_score.toFixed(1)}</span>
            )}
            <span className="capitalize">{finding.agent_type.replace('_', ' ')} agent</span>
            <span>{format(parseISO(finding.created_at), 'MMM d, yyyy')}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="xl:col-span-2 space-y-5">

          {/* WHY FLAGGED — the core user-facing explanation */}
          {finding.why_flagged && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              className="card border-l-4 border-l-sentinel-500 p-5">
              <div className="flex items-center gap-2 mb-3">
                <Shield className="w-4 h-4 text-sentinel-600" />
                <h3 className="font-semibold text-gray-900">Why was this flagged?</h3>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">{finding.why_flagged}</p>
            </motion.div>
          )}

          {/* Location + code snippet */}
          {(finding.file_path || finding.code_snippet) && (
            <div className="card overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between bg-gray-50">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-gray-500" />
                  <span className="font-mono text-sm font-medium text-gray-700">
                    {finding.file_path}
                    {finding.line_start && `:${finding.line_start}`}
                    {finding.line_end && finding.line_end !== finding.line_start && `–${finding.line_end}`}
                  </span>
                </div>
              </div>
              {finding.code_snippet && (
                <pre className="p-5 text-xs font-mono text-gray-800 bg-gray-950 text-gray-100 overflow-x-auto leading-relaxed whitespace-pre-wrap">
                  {finding.code_snippet}
                </pre>
              )}
            </div>
          )}

          {/* Description */}
          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 mb-3">Technical Description</h3>
            <p className="text-sm text-gray-700 leading-relaxed">{finding.description}</p>
          </div>

          {/* Business risk */}
          {finding.business_risk && (
            <div className="card p-5 bg-amber-50 border-amber-200">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <h3 className="font-semibold text-gray-900">Business Risk</h3>
                <span className="text-xs text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">Executive summary</span>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">{finding.business_risk}</p>
            </div>
          )}

          {/* Recommendation */}
          {finding.recommendation && (
            <div className="card p-5 bg-green-50 border-green-200">
              <div className="flex items-center gap-2 mb-3">
                <Wrench className="w-4 h-4 text-green-600" />
                <h3 className="font-semibold text-gray-900">Recommended Fix</h3>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{finding.recommendation}</p>
            </div>
          )}

          {/* Dependency-specific info */}
          {finding.dependency_name && (
            <div className="card p-5">
              <div className="flex items-center gap-2 mb-4">
                <Package className="w-4 h-4 text-orange-500" />
                <h3 className="font-semibold text-gray-900">Dependency Details</h3>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-500 text-xs mb-1">Package</div>
                  <div className="font-mono font-semibold">{finding.dependency_name}</div>
                </div>
                <div>
                  <div className="text-gray-500 text-xs mb-1">Ecosystem</div>
                  <div className="font-medium capitalize">{finding.dependency_ecosystem}</div>
                </div>
                <div>
                  <div className="text-gray-500 text-xs mb-1">Installed version</div>
                  <div className="font-mono text-red-700">{finding.dependency_version}</div>
                </div>
                {finding.dependency_fixed_version && (
                  <div>
                    <div className="text-gray-500 text-xs mb-1">Fix version</div>
                    <div className="font-mono text-green-700">{finding.dependency_fixed_version}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Auto-fix diff */}
          {fixes.length > 0 && fixes[0].diff_patch && (
            <div className="card overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Wrench className="w-4 h-4 text-green-600" />
                  <span className="font-semibold text-gray-900">Auto-Fix Patch</span>
                  <FixStatusBadge status={fixes[0].status} sandboxStatus={fixes[0].sandbox_status} />
                </div>
                <button onClick={() => setShowDiff(!showDiff)} className="text-gray-400 hover:text-gray-600">
                  {showDiff ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              </div>
              {showDiff && fixes[0].original_code && fixes[0].fixed_code && (
                <ReactDiffViewer
                  oldValue={fixes[0].original_code}
                  newValue={fixes[0].fixed_code}
                  splitView={false}
                  useDarkTheme={false}
                  hideLineNumbers={false}
                  leftTitle="Original (vulnerable)"
                  rightTitle="Fixed"
                  styles={{ variables: { light: { diffViewerBackground: '#f9fafb', addedBackground: '#f0fdf4', removedBackground: '#fff1f2' } } }}
                />
              )}
              {showDiff && fixes[0].description && (
                <div className="px-5 py-4 bg-green-50 border-t border-green-100">
                  <p className="text-sm text-green-800 leading-relaxed">{fixes[0].description}</p>
                  {fixes[0].why_safe && (
                    <p className="text-xs text-green-700 mt-2 italic">{fixes[0].why_safe}</p>
                  )}
                </div>
              )}
              {showDiff && fixes[0].sandbox_checks_passed && fixes[0].sandbox_checks_passed.length > 0 && (
                <div className="px-5 py-3 border-t border-gray-100">
                  <div className="text-xs font-semibold text-gray-500 mb-2">Sandbox validation</div>
                  <div className="flex flex-wrap gap-2">
                    {fixes[0].sandbox_checks_passed.map((check) => (
                      <span key={check} className="flex items-center gap-1 text-xs text-green-700 bg-green-50 border border-green-200 px-2 py-1 rounded-lg">
                        <CheckCircle className="w-3 h-3" /> {check.replace(/_/g, ' ')}
                      </span>
                    ))}
                    {(fixes[0].sandbox_checks_failed || []).map((check) => (
                      <span key={check} className="flex items-center gap-1 text-xs text-red-700 bg-red-50 border border-red-200 px-2 py-1 rounded-lg">
                        <XCircle className="w-3 h-3" /> {check.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* References */}
          {finding.references && finding.references.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-gray-900 mb-3">References</h3>
              <div className="space-y-1.5">
                {finding.references.map((ref, i) => (
                  <a key={i} href={ref} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-sentinel-600 hover:underline">
                    <ExternalLink className="w-3.5 h-3.5" />
                    {ref}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-5">
          {/* Metadata */}
          <div className="card p-5">
            <h3 className="font-semibold text-gray-900 mb-4">Finding Details</h3>
            <dl className="space-y-3 text-sm">
              {[
                { label: 'Status', value: <span className="capitalize font-medium">{finding.status.replace('_', ' ')}</span> },
                { label: 'Severity', value: <SeverityBadge severity={finding.severity} /> },
                { label: 'Confidence', value: <span className="capitalize">{finding.confidence}</span> },
                { label: 'Category', value: <span className="capitalize">{finding.category?.replace('_', ' ')}</span> },
                { label: 'Agent', value: <span className="capitalize">{finding.agent_type.replace('_', ' ')}</span> },
                { label: 'First seen', value: finding.first_seen_at ? format(parseISO(finding.first_seen_at), 'MMM d, yyyy') : '—' },
                { label: 'Fix available', value: finding.fix_available ? <span className="text-green-700 font-medium">Yes</span> : 'No' },
                { label: 'Fix complexity', value: finding.fix_complexity ? <span className="capitalize">{finding.fix_complexity}</span> : '—' },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-start justify-between gap-4">
                  <dt className="text-gray-500 flex-shrink-0">{label}</dt>
                  <dd className="text-right font-medium text-gray-900">{value}</dd>
                </div>
              ))}
            </dl>
          </div>

          {/* Compliance */}
          {finding.compliance_frameworks && finding.compliance_frameworks.length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-gray-900 mb-3">Compliance Impact</h3>
              <div className="flex flex-wrap gap-2">
                {finding.compliance_frameworks.map((fw) => (
                  <span key={fw} className="badge bg-purple-50 text-purple-800 border border-purple-200 text-xs">
                    {fw}
                  </span>
                ))}
              </div>
              {finding.compliance_details && (
                <div className="mt-3 text-xs text-gray-600 bg-gray-50 rounded-lg p-3 space-y-1">
                  {finding.compliance_details.clause && <div><strong>Clause:</strong> {finding.compliance_details.clause}</div>}
                  {finding.compliance_details.requirement && <div><strong>Requirement:</strong> {finding.compliance_details.requirement}</div>}
                  {finding.compliance_details.gap && <div><strong>Gap:</strong> {finding.compliance_details.gap}</div>}
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="card p-5 space-y-3">
            <h3 className="font-semibold text-gray-900">Actions</h3>
            <Link to={`/app/autofix?finding_id=${finding.id}`} className="btn-primary w-full justify-center text-sm">
              <Wrench className="w-4 h-4" />
              View Auto-Fix
            </Link>
            <button
              onClick={() => setShowFpForm(!showFpForm)}
              className="btn-secondary w-full justify-center text-sm"
            >
              <ThumbsDown className="w-4 h-4" />
              Mark False Positive
            </button>
          </div>

          {/* False positive form */}
          {showFpForm && (
            <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="card p-5">
              <h3 className="font-semibold text-gray-900 mb-3 text-sm">Report as False Positive</h3>
              <p className="text-xs text-gray-500 mb-3">Your feedback helps improve future scans. Please explain why this finding is incorrect.</p>
              <textarea
                value={fpReason}
                onChange={(e) => setFpReason(e.target.value)}
                placeholder="e.g., This SQL query only accepts internal admin IDs, not user input…"
                className="input text-sm resize-none"
                rows={4}
              />
              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => fpMutation.mutate(fpReason)}
                  disabled={fpReason.length < 10 || fpMutation.isPending}
                  className="btn-primary flex-1 justify-center text-sm"
                >
                  {fpMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Submit'}
                </button>
                <button onClick={() => setShowFpForm(false)} className="btn-secondary px-4 text-sm">Cancel</button>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  )
}
