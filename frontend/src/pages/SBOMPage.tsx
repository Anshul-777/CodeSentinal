import { useQuery } from '@tanstack/react-query'
import { FileText, Download, Loader2, CheckCircle, Package } from 'lucide-react'
import apiClient from '@/api/client'

export default function SBOMPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['sbom'],
    queryFn: () => apiClient.get('/sbom').then(r => r.data),
  })

  const entries: any[] = data?.entries || []
  const safe = entries.filter(e => e.license_risk === 'safe' || e.license_risk === 'unknown').length
  const risky = entries.filter(e => ['high','medium'].includes(e.license_risk)).length

  const downloadSBOM = async () => {
    const res = await apiClient.get('/sbom/export', { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a'); a.href = url; a.download = 'sbom.json'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div><h1 className="page-title">SBOM</h1><p className="text-muted mt-1">Software Bill of Materials — {entries.length} packages tracked.</p></div>
        <button onClick={downloadSBOM} className="btn-secondary text-sm"><Download className="w-4 h-4"/>Export SPDX JSON</button>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="card p-4 text-center"><div className="text-2xl font-black text-gray-900">{entries.length}</div><div className="text-sm text-gray-500">Total Packages</div></div>
        <div className="card p-4 text-center"><div className="text-2xl font-black text-green-600">{safe}</div><div className="text-sm text-gray-500">Safe / Unknown</div></div>
        <div className="card p-4 text-center"><div className="text-2xl font-black text-orange-600">{risky}</div><div className="text-sm text-gray-500">License Risk</div></div>
      </div>
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100"><h2 className="section-title">Package Inventory</h2></div>
        {isLoading ? <div className="p-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-400"/></div>
        : entries.length === 0 ? (
          <div className="p-12 text-center"><Package className="w-10 h-10 mx-auto mb-3 text-gray-200"/><div className="text-gray-500">No packages tracked yet — run a scan to generate SBOM data.</div></div>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100 bg-gray-50 text-left">
              {['Package','Version','Ecosystem','License','Risk'].map(h => <th key={h} className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-gray-50">
              {entries.map((e: any, i: number) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono font-medium text-gray-900">{e.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">{e.version}</td>
                  <td className="px-4 py-3 text-xs text-gray-500 capitalize">{e.ecosystem}</td>
                  <td className="px-4 py-3 text-xs">{e.license || 'Unknown'}</td>
                  <td className="px-4 py-3">
                    <span className={`badge text-xs ${e.license_risk==='high'?'badge-high':e.license_risk==='medium'?'badge-medium':'badge-success'}`}>
                      {e.license_risk || 'safe'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
