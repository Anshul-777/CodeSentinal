import { useQuery, useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Cpu, CheckCircle, XCircle, Loader2, ExternalLink, Zap, AlertTriangle } from 'lucide-react'
import apiClient from '@/api/client'
import type { AIProvider } from '@/types'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function ModelsPage() {
  const [testResults, setTestResults] = useState<Record<string, any>>({})
  const [testing, setTesting] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['ai-providers'],
    queryFn: () => apiClient.get('/models/providers').then(r => r.data),
    refetchInterval: 30000,
  })

  const providers: AIProvider[] = data?.providers || []

  const testProvider = async (provider: AIProvider) => {
    setTesting(provider.id)
    try {
      const { data } = await apiClient.post('/models/test', { provider: provider.id, model: provider.model })
      setTestResults(prev => ({ ...prev, [provider.id]: data }))
      if (data.success) toast.success(`${provider.name} OK — ${data.latency_ms}ms`)
      else toast.error(`${provider.name}: ${data.message?.slice(0,80)}`)
    } catch { toast.error('Test failed') } finally { setTesting(null) }
  }

  const preferMutation = useMutation({
    mutationFn: (p: { provider: string }) => apiClient.patch('/models/preference', p),
    onSuccess: () => toast.success('Default provider updated'),
  })

  const typeLabels: Record<string, { label: string; cls: string }> = {
    local: { label: 'Local — Free', cls: 'bg-green-100 text-green-800 border border-green-200' },
    cloud_free: { label: 'Cloud — Free Tier', cls: 'bg-blue-100 text-blue-800 border border-blue-200' },
    cloud_paid: { label: 'Cloud — BYOK', cls: 'bg-gray-100 text-gray-700 border border-gray-200' },
  }

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">AI Models</h1>
        <p className="text-muted mt-1">Configure which providers power the 5-agent pipeline. Fallback chain: Ollama → Groq → OpenAI → Anthropic.</p>
      </div>
      {isLoading ? <div className="flex justify-center p-12"><Loader2 className="w-6 h-6 animate-spin text-sentinel-600"/></div> : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {providers.map((p, i) => {
            const { label, cls } = typeLabels[p.type] || typeLabels.cloud_paid
            const tr = testResults[p.id]
            return (
              <motion.div key={p.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i*0.08 }}
                className={clsx('card p-5 flex flex-col gap-3', !p.available && 'opacity-60')}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-bold text-gray-900">{p.name}</span>
                      <span className={`badge text-[10px] ${cls}`}>{label}</span>
                    </div>
                    <div className="font-mono text-xs text-gray-500">{p.model}</div>
                  </div>
                  {p.available ? <span className="flex items-center gap-1 text-xs text-green-700"><CheckCircle className="w-3.5 h-3.5"/>Ready</span>
                    : <span className="flex items-center gap-1 text-xs text-gray-400"><XCircle className="w-3.5 h-3.5"/>Not configured</span>}
                </div>
                <p className="text-sm text-gray-600 flex-1">{p.description}</p>
                {p.error && <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2">{p.error}</div>}
                {tr && <div className={clsx('text-xs p-2 rounded-lg border', tr.success?'bg-green-50 border-green-200 text-green-800':'bg-red-50 border-red-200 text-red-700')}>
                  {tr.success ? `✓ ${tr.content?.slice(0,80)} (${tr.latency_ms}ms)` : `✗ ${tr.message?.slice(0,100)}`}
                </div>}
                <div className="flex gap-2">
                  <button onClick={() => testProvider(p)} disabled={testing===p.id} className="btn-secondary flex-1 justify-center text-sm">
                    {testing===p.id ? <Loader2 className="w-3.5 h-3.5 animate-spin"/> : <Zap className="w-3.5 h-3.5"/>}Test
                  </button>
                  <button onClick={() => preferMutation.mutate({provider:p.id})} className="btn-primary flex-1 justify-center text-sm">
                    Set default
                  </button>
                  {!p.configured && <a href={p.setup_url} target="_blank" rel="noopener noreferrer" className="btn-secondary px-3"><ExternalLink className="w-3.5 h-3.5"/></a>}
                </div>
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}
