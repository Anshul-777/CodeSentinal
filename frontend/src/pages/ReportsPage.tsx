import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { BarChart3, Download, Loader2, FileText, FileBadge } from 'lucide-react'
import apiClient from '@/api/client'
import toast from 'react-hot-toast'

const REPORT_TYPES = [
  { id: 'security_summary', label: 'Security Summary', desc: 'Risk scores, finding counts, remediation status across all repositories', formats: ['pdf', 'docx'] },
  { id: 'compliance_report', label: 'Compliance Report', desc: 'Full SOC2/HIPAA/PCI-DSS/GDPR posture with passing/failing controls', formats: ['pdf', 'docx'] },
  { id: 'dependency_report', label: 'Dependency Report', desc: 'All CVEs, license risks, and SBOM export', formats: ['pdf', 'json'] },
  { id: 'executive_summary', label: 'Executive Summary', desc: 'Board-ready risk overview with business-language explanations', formats: ['pdf'] },
  { id: 'findings_detail', label: 'Full Findings Report', desc: 'Every finding with file path, code context, why-flagged, and fix status', formats: ['pdf', 'docx'] },
]

export default function ReportsPage() {
  const [generating, setGenerating] = useState<string | null>(null)

  const generate = async (type: string, format: string) => {
    setGenerating(`${type}-${format}`)
    try {
      const res = await apiClient.get(`/reports/${type}`, {
        params: { format },
        responseType: 'blob',
      })
      const ext = format === 'json' ? 'json' : format
      const blob = new Blob([res.data])
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `codesentinel-${type}-${new Date().toISOString().slice(0,10)}.${ext}`
      a.click()
      URL.revokeObjectURL(url)
      toast.success(`${format.toUpperCase()} report downloaded`)
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Report generation failed')
    } finally { setGenerating(null) }
  }

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Reports</h1>
        <p className="text-muted mt-1">Generate detailed security reports in PDF and DOCX format. All reports reflect live database state.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {REPORT_TYPES.map((rt) => (
          <div key={rt.id} className="card p-5 flex flex-col gap-4">
            <div className="w-10 h-10 bg-sentinel-100 rounded-xl flex items-center justify-center">
              {rt.id === 'executive_summary' ? <FileBadge className="w-5 h-5 text-sentinel-600" /> : <FileText className="w-5 h-5 text-sentinel-600" />}
            </div>
            <div>
              <div className="font-semibold text-gray-900 mb-1">{rt.label}</div>
              <p className="text-sm text-gray-500">{rt.desc}</p>
            </div>
            <div className="flex gap-2 mt-auto">
              {rt.formats.map(fmt => (
                <button key={fmt} onClick={() => generate(rt.id, fmt)}
                  disabled={generating === `${rt.id}-${fmt}`}
                  className="btn-secondary flex-1 justify-center text-sm uppercase">
                  {generating === `${rt.id}-${fmt}` ? <Loader2 className="w-3.5 h-3.5 animate-spin"/> : <Download className="w-3.5 h-3.5"/>}
                  {fmt}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
