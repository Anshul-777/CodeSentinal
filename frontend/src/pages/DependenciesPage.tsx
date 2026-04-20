import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Package, AlertTriangle, CheckCircle, ExternalLink, ArrowRight, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import apiClient from '@/api/client'
import clsx from 'clsx'

export default function DependenciesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dependency-findings'],
    queryFn: () => apiClient.get('/findings', { params: { agent_type: 'dependency', limit: 100, status: 'open' } }).then(r => r.data),
  })
  const { data: sbomData } = useQuery({
    queryKey: ['sbom-summary'],
    queryFn: () => apiClient.get('/sbom/summary').then(r => r.data),
  })

  const findings: any[] = data?.findings || []
  const sbom: any[] = sbomData?.entries || []

  const cveFindings = findings.filter(f => f.cve_id || f.category === 'vulnerable_dependency')
  const licenseFindings = findings.filter(f => f.category === 'license_risk')

  const ecosystems = [...new Set(findings.map(f => f.dependency_ecosystem).filter(Boolean))]

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Dependencies</h1>
        <p className="text-muted mt-1">Agent 2 queries OSV.dev for real CVEs, checks license risks, and generates SBOM entries for every manifest found.</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Packages Tracked', value: sbom.length || findings.length, color: 'text-gray-900' },
          { label: 'CVE Vulnerabilities', value: cveFindings.length, color: 'text-red-600' },
          { label: 'License Risks', value: licenseFindings.length, color: 'text-orange-600' },
          { label: 'Ecosystems', value: ecosystems.length, color: 'text-blue-600' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card p-4 text-center">
            <div className={`text-2xl font-black ${color}`}>{value}</div>
            <div className="text-sm text-gray-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="section-title">Vulnerable Packages ({cveFindings.length})</h2>
          <a href="https://osv.dev" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700">
            <ExternalLink className="w-3 h-3" />Powered by OSV.dev
          </a>
        </div>
        {isLoading ? <div className="p-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-400" /></div>
        : cveFindings.length === 0 ? (
          <div className="p-12 text-center">
            <CheckCircle className="w-10 h-10 mx-auto mb-3 text-green-500 opacity-60" />
            <div className="text-gray-500 font-medium">No vulnerable dependencies found</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-100 bg-gray-50 text-left">
                {['Severity','Package','Version','Fixed In','CVE','Ecosystem',''].map(h => (
                  <th key={h} className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr></thead>
              <tbody className="divide-y divide-gray-50">
                {cveFindings.map((f: any) => (
                  <tr key={f.id} className="hover:bg-gray-50 group">
                    <td className="px-4 py-3.5">
                      <span className={clsx('badge text-xs', f.severity==='critical'?'badge-critical':f.severity==='high'?'badge-high':'badge-medium')}>
                        {f.severity.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 font-mono font-medium text-gray-900">{f.dependency_name}</td>
                    <td className="px-4 py-3.5 font-mono text-red-700">{f.dependency_version}</td>
                    <td className="px-4 py-3.5 font-mono text-green-700">{f.dependency_fixed_version || '—'}</td>
                    <td className="px-4 py-3.5">
                      {f.cve_id ? (
                        <a href={`https://osv.dev/vulnerability/${f.cve_id}`} target="_blank" rel="noopener noreferrer"
                          className="font-mono text-xs text-red-600 hover:underline flex items-center gap-1">
                          {f.cve_id}<ExternalLink className="w-3 h-3" />
                        </a>
                      ) : <span className="text-gray-400">—</span>}
                    </td>
                    <td className="px-4 py-3.5 text-xs text-gray-500 capitalize">{f.dependency_ecosystem}</td>
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
        )}
      </div>

      {licenseFindings.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="section-title">License Risks ({licenseFindings.length})</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {licenseFindings.map((f: any) => (
              <Link key={f.id} to={`/app/findings/${f.id}`}
                className="flex items-center gap-4 px-6 py-4 hover:bg-gray-50 transition-colors group">
                <AlertTriangle className="w-4 h-4 text-orange-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-900">{f.dependency_name}</div>
                  <div className="text-sm text-gray-500">{f.title}</div>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
