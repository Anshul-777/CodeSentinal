import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Wrench, CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp, GitBranch, ExternalLink, Clock, Code2 } from 'lucide-react'
import apiClient from '@/api/client'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function AutoFixPage() {
  const [expanded, setExpanded] = useState<string|null>(null)
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['fixes'],
    queryFn: () => apiClient.get('/autofix').then(r => r.data),
  })
  const fixes: any[] = data?.fixes || []

  const applyMutation = useMutation({
    mutationFn: (id: string) => apiClient.post(`/autofix/${id}/apply`),
    onSuccess: () => { toast.success('Fix applied to repository.'); qc.invalidateQueries({queryKey:['fixes']}) },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Apply failed'),
  })
  const rejectMutation = useMutation({
    mutationFn: (id: string) => apiClient.post(`/autofix/${id}/reject`),
    onSuccess: () => { toast.success('Fix rejected.'); qc.invalidateQueries({queryKey:['fixes']}) },
  })

  const StatusIcon = ({ status }: {status:string}) => {
    if (status === 'verified' || status === 'applied') return <CheckCircle className="w-4 h-4 text-green-600" />
    if (status === 'rejected') return <XCircle className="w-4 h-4 text-red-600" />
    if (status === 'sandbox_testing') return <Loader2 className="w-4 h-4 text-yellow-600 animate-spin" />
    return <Clock className="w-4 h-4 text-gray-400" />
  }

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Auto-Fix</h1>
        <p className="text-muted mt-1">Agent 4 generates verified patches for fixable vulnerabilities. Each fix is sandbox-tested before being available to apply.</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[{l:'Total',v:fixes.length,c:'text-gray-900'},{l:'Verified',v:fixes.filter(f=>f.status==='verified').length,c:'text-green-600'},{l:'Applied',v:fixes.filter(f=>f.status==='applied').length,c:'text-blue-600'},{l:'Rejected',v:fixes.filter(f=>f.status==='rejected').length,c:'text-red-600'}].map(({l,v,c})=>(
          <div key={l} className="card p-4 text-center">
            <div className={`text-2xl font-black ${c}`}>{v}</div>
            <div className="text-sm text-gray-500 mt-1">{l}</div>
          </div>
        ))}
      </div>

      <div className="card p-5 bg-sentinel-50 border-sentinel-200">
        <div className="grid grid-cols-4 gap-4 text-xs text-gray-600">
          {[['1','LLM generates patch','Creates corrected code targeting the specific vulnerability'],
            ['2','Sandbox validation','Syntax check + flake8 lint + pytest if available'],
            ['3','Verification','Only verified if all checks pass & vuln pattern removed'],
            ['4','Apply to repo','Push fix branch and optionally open a PR']].map(([s,t,d])=>(
            <div key={s} className="flex gap-2">
              <div className="w-5 h-5 rounded-full bg-sentinel-600 text-white text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5">{s}</div>
              <div><div className="font-semibold text-gray-800">{t}</div><div className="mt-0.5">{d}</div></div>
            </div>
          ))}
        </div>
      </div>

      {isLoading ? <div className="flex justify-center p-12"><Loader2 className="w-6 h-6 animate-spin text-sentinel-600"/></div>
      : fixes.length === 0 ? (
        <div className="card p-16 text-center">
          <Wrench className="w-12 h-12 mx-auto mb-4 text-gray-200"/>
          <div className="font-medium text-gray-500">No auto-fixes yet</div>
          <div className="text-sm text-gray-400 mt-1">Connect a repo, trigger a scan, and fixes for supported vulnerability classes will appear here.</div>
        </div>
      ) : (
        <div className="space-y-3">
          {fixes.map((fix) => (
            <motion.div key={fix.id} layout className="card overflow-hidden">
              <button onClick={() => setExpanded(expanded===fix.id ? null : fix.id)}
                className="w-full flex items-center gap-4 p-5 text-left hover:bg-gray-50 transition-colors">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-gray-50 flex-shrink-0">
                  <StatusIcon status={fix.status} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={clsx('badge border text-xs', fix.status==='verified'||fix.status==='applied'?'bg-green-100 text-green-800 border-green-200':fix.status==='rejected'?'bg-red-100 text-red-800 border-red-200':'bg-gray-100 text-gray-600 border-gray-200')}>
                      {fix.status.replace('_',' ')}
                    </span>
                    {fix.is_verified && <span className="badge badge-success text-xs">✓ Verified</span>}
                  </div>
                  <div className="font-medium text-gray-900">{fix.file_path || 'Dependency fix'}</div>
                  {fix.description && <div className="text-sm text-gray-500 mt-0.5 line-clamp-1">{fix.description}</div>}
                </div>
                {expanded===fix.id ? <ChevronUp className="w-4 h-4 text-gray-400"/> : <ChevronDown className="w-4 h-4 text-gray-400"/>}
              </button>
              <AnimatePresence>
                {expanded===fix.id && (
                  <motion.div initial={{height:0,opacity:0}} animate={{height:'auto',opacity:1}} exit={{height:0,opacity:0}}
                    className="overflow-hidden border-t border-gray-100">
                    <div className="p-5 space-y-4">
                      {fix.original_code && fix.fixed_code && (
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <div className="text-xs text-red-600 font-semibold mb-1">Vulnerable</div>
                            <pre className="text-xs font-mono bg-red-50 border border-red-200 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap text-red-900">{fix.original_code}</pre>
                          </div>
                          <div>
                            <div className="text-xs text-green-600 font-semibold mb-1">Fixed</div>
                            <pre className="text-xs font-mono bg-green-50 border border-green-200 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap text-green-900">{fix.fixed_code}</pre>
                          </div>
                        </div>
                      )}
                      {fix.sandbox_checks_passed?.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {fix.sandbox_checks_passed.map((c: string) => (
                            <span key={c} className="flex items-center gap-1 text-xs text-green-700 bg-green-50 border border-green-200 px-2 py-1 rounded-lg">
                              <CheckCircle className="w-3 h-3"/>{c.replace(/_/g,' ')}
                            </span>
                          ))}
                        </div>
                      )}
                      {fix.why_safe && <div className="text-sm text-blue-800 bg-blue-50 border border-blue-200 rounded-lg p-3"><strong>Why safe: </strong>{fix.why_safe}</div>}
                      {fix.status === 'verified' && (
                        <div className="flex gap-3">
                          <button onClick={() => applyMutation.mutate(fix.id)} disabled={applyMutation.isPending} className="btn-primary text-sm">
                            {applyMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin"/> : <GitBranch className="w-4 h-4"/>}
                            Apply to Repository
                          </button>
                          <button onClick={() => rejectMutation.mutate(fix.id)} className="btn-secondary text-sm">
                            <XCircle className="w-4 h-4"/>Reject
                          </button>
                        </div>
                      )}
                      {fix.fix_pr_url && (
                        <a href={fix.fix_pr_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sm text-sentinel-600 hover:underline">
                          <ExternalLink className="w-4 h-4"/>View PR on GitHub
                        </a>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
