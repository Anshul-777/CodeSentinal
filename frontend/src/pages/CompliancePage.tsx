import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { CheckCircle, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import apiClient from '@/api/client'
import clsx from 'clsx'

const FRAMEWORKS = [
  { id: 'soc2', name: 'SOC 2 Type II', short: 'SOC2', color: 'bg-blue-500', desc: 'Trust Service Criteria: CC6.1–CC8.1 covering access, monitoring, and change management.' },
  { id: 'hipaa', name: 'HIPAA Security Rule', short: 'HIPAA', color: 'bg-green-500', desc: 'ePHI protection: access control, encryption at rest and in transit, authentication.' },
  { id: 'pci_dss', name: 'PCI-DSS 4.0', short: 'PCI-DSS', color: 'bg-orange-500', desc: 'Cardholder data security: req 6.3, 6.4, 8.3, 8.6 covering vulns and passwords.' },
  { id: 'gdpr', name: 'GDPR Article 32', short: 'GDPR', color: 'bg-purple-500', desc: 'Personal data protection: encryption, retention, integrity, and availability.' },
]

export default function CompliancePage() {
  const [repositoryId, setRepositoryId] = useState('')

  const { data: reposData } = useQuery({
    queryKey: ['repos'],
    queryFn: () => apiClient.get('/repos').then(r => r.data),
  })
  const repos = reposData?.repositories || []

  const { data: summary } = useQuery({
    queryKey: ['compliance-summary', repositoryId],
    queryFn: () => apiClient.get('/compliance/summary', { params: { repository_id: repositoryId || undefined } }).then(r => r.data),
  })
  const { data: findingsData } = useQuery({
    queryKey: ['compliance-findings', repositoryId],
    queryFn: () => apiClient.get('/compliance/findings', { params: { repository_id: repositoryId || undefined, limit: 20 } }).then(r => r.data),
  })

  const scores: Record<string, any> = summary?.scores || {}
  const findings: any[] = findingsData?.findings || []

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Compliance</h1>
        <p className="text-muted mt-1">Agent 5 checks every code change against SOC2, HIPAA, PCI-DSS 4.0, and GDPR Article 32.</p>
        <div className="mt-3 max-w-sm">
          <select
            value={repositoryId}
            onChange={(e) => setRepositoryId(e.target.value)}
            className="input text-sm"
            aria-label="Repository filter"
            title="Repository filter"
          >
            <option value="">All repositories</option>
            {repos.map((r: any) => <option key={r.id} value={r.id}>{r.full_name}</option>)}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
        {FRAMEWORKS.map((fw, i) => {
          const d = scores[fw.id]
          const score = d?.score ?? null
          const scoreCls = score == null ? 'text-gray-400' : score >= 80 ? 'text-green-500' : score >= 60 ? 'text-yellow-500' : 'text-red-500'
          return (
            <motion.div key={fw.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
              className="card p-5">
              <div className={`h-1 rounded-full ${fw.color} mb-4`} />
              <div className="flex items-center justify-between mb-3">
                <div>
                  <div className="text-xs font-bold text-gray-500 uppercase tracking-wide">{fw.short}</div>
                  <div className="font-bold text-gray-900 text-sm mt-0.5">{fw.name}</div>
                </div>
                <div className={`text-3xl font-black ${scoreCls}`}>{score != null ? `${score}%` : '—'}</div>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">{fw.desc}</p>
              {d && (
                <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
                  <span className="text-green-600 font-medium">{d.passed || 0} passed</span>
                  <span className={d.failed > 0 ? 'text-red-600 font-medium' : 'text-gray-400'}>{d.failed || 0} failed</span>
                </div>
              )}
            </motion.div>
          )
        })}
      </div>

      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="section-title">Open Violations ({findings.length})</h2>
          <Link to="/app/findings?agent_type=compliance" className="text-sm text-sentinel-600 hover:underline">View all →</Link>
        </div>
        {findings.length === 0 ? (
          <div className="p-12 text-center">
            <CheckCircle className="w-10 h-10 mx-auto mb-3 text-green-500 opacity-60" />
            <div className="text-gray-500 font-medium">No open compliance violations</div>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {findings.map((f: any) => (
              <Link key={f.id} to={`/app/findings/${f.id}`}
                className="flex items-center gap-4 px-6 py-4 hover:bg-gray-50 transition-colors group">
                <span className={clsx('badge text-xs', f.severity === 'critical' ? 'badge-critical' : f.severity === 'high' ? 'badge-high' : 'badge-medium')}>
                  {f.severity.toUpperCase()}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-900 truncate">{f.title}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{(f.compliance_frameworks || []).join(' · ')}</div>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
