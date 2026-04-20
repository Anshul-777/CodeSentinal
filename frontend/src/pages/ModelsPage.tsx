import { useQuery, useMutation } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle, XCircle, Loader2, ExternalLink, Zap, KeyRound, X } from 'lucide-react'
import apiClient from '@/api/client'
import type { AIProvider } from '@/types'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function ModelsPage() {
  const [testResults, setTestResults] = useState<Record<string, any>>({})
  const [testing, setTesting] = useState<string | null>(null)
  const [selectedModels, setSelectedModels] = useState<Record<string, string>>({})
  const [configProvider, setConfigProvider] = useState<AIProvider | null>(null)
  const [pendingAction, setPendingAction] = useState<'test' | 'default' | null>(null)
  const [apiKeyInput, setApiKeyInput] = useState('')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['ai-providers'],
    queryFn: () => apiClient.get('/models/providers').then(r => r.data),
    refetchInterval: 30000,
  })

  const providers: AIProvider[] = data?.providers || []

  useEffect(() => {
    if (!providers.length) return
    setSelectedModels(prev => {
      const next = { ...prev }
      for (const p of providers) {
        if (!next[p.id]) next[p.id] = p.model
      }
      return next
    })
  }, [providers])

  const testProvider = async (provider: AIProvider) => {
    setTesting(provider.id)
    try {
      const { data } = await apiClient.post('/models/test', { provider: provider.id, model: selectedModels[provider.id] || provider.model })
      setTestResults(prev => ({ ...prev, [provider.id]: data }))
      if (data.success) toast.success(`${provider.name} OK — ${data.latency_ms}ms`)
      else toast.error(`${provider.name}: ${data.message?.slice(0,80)}`)
    } catch { toast.error('Test failed') } finally { setTesting(null) }
  }

  const preferMutation = useMutation({
    mutationFn: (p: { provider: string; model: string }) => apiClient.patch('/models/preference', p),
    onSuccess: () => toast.success('Default provider updated'),
  })

  const configureMutation = useMutation({
    mutationFn: (p: { provider: string; api_key: string }) => apiClient.post('/models/configure', p),
    onSuccess: async () => {
      toast.success('API key saved')
      await refetch()
      if (!configProvider || !pendingAction) return
      const provider = configProvider
      const action = pendingAction
      setConfigProvider(null)
      setPendingAction(null)
      setApiKeyInput('')
      if (action === 'test') await testProvider(provider)
      else preferMutation.mutate({ provider: provider.id, model: selectedModels[provider.id] || provider.model })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to save API key')
    },
  })

  const needsKey = (p: AIProvider) => p.id !== 'ollama' && !p.configured

  const beginAction = async (provider: AIProvider, action: 'test' | 'default') => {
    if (needsKey(provider)) {
      setConfigProvider(provider)
      setPendingAction(action)
      return
    }
    if (action === 'test') {
      await testProvider(provider)
      return
    }
    preferMutation.mutate({ provider: provider.id, model: selectedModels[provider.id] || provider.model })
  }

  const saveApiKey = () => {
    if (!configProvider) return
    if (!apiKeyInput.trim()) {
      toast.error('Enter an API key (or NONE to clear).')
      return
    }
    configureMutation.mutate({ provider: configProvider.id, api_key: apiKeyInput.trim() })
  }

  const typeLabels: Record<string, { label: string; cls: string }> = {
    local: { label: 'Local — Free', cls: 'bg-green-100 text-green-800 border border-green-200' },
    cloud_free: { label: 'Cloud — Free Tier', cls: 'bg-blue-100 text-blue-800 border border-blue-200' },
    cloud_paid: { label: 'Cloud — BYOK', cls: 'bg-gray-100 text-gray-700 border border-gray-200' },
  }

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">AI Models</h1>
        <p className="text-muted mt-1">Configure which providers power the 5-agent pipeline. Fallback chain: Ollama → Groq → Gemini → OpenRouter → OpenAI → Anthropic.</p>
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
                    <div className="font-mono text-xs text-gray-500">Default: {p.default_model || p.model}</div>
                  </div>
                  {p.available ? <span className="flex items-center gap-1 text-xs text-green-700"><CheckCircle className="w-3.5 h-3.5"/>Ready</span>
                    : <span className="flex items-center gap-1 text-xs text-gray-400"><XCircle className="w-3.5 h-3.5"/>Not configured</span>}
                </div>
                <p className="text-sm text-gray-600 flex-1">{p.description}</p>
                <div>
                  <label className="text-xs text-gray-500" htmlFor={`model-${p.id}`}>Model</label>
                  <select
                    id={`model-${p.id}`}
                    aria-label={`${p.name} model`}
                    className="input mt-1 text-sm"
                    value={selectedModels[p.id] || p.model}
                    onChange={(e) => setSelectedModels(prev => ({ ...prev, [p.id]: e.target.value }))}
                  >
                    {(p.models && p.models.length ? p.models : [p.model]).map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
                {p.error && <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2">{p.error}</div>}
                {tr && <div className={clsx('text-xs p-2 rounded-lg border', tr.success?'bg-green-50 border-green-200 text-green-800':'bg-red-50 border-red-200 text-red-700')}>
                  {tr.success ? `✓ ${tr.content?.slice(0,80)} (${tr.latency_ms}ms)` : `✗ ${tr.message?.slice(0,100)}`}
                </div>}
                <div className="flex gap-2">
                  <button onClick={() => beginAction(p, 'test')} disabled={testing===p.id} className="btn-secondary flex-1 justify-center text-sm">
                    {testing===p.id ? <Loader2 className="w-3.5 h-3.5 animate-spin"/> : <Zap className="w-3.5 h-3.5"/>}Test
                  </button>
                  <button onClick={() => beginAction(p, 'default')} className="btn-primary flex-1 justify-center text-sm">
                    Set default
                  </button>
                  {!p.configured && p.id !== 'ollama' && (
                    <button onClick={() => { setConfigProvider(p); setPendingAction(null) }} className="btn-secondary px-3" title="Configure API key">
                      <KeyRound className="w-3.5 h-3.5"/>
                    </button>
                  )}
                  {!p.configured && (
                    <a
                      href={p.setup_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-secondary px-3"
                      title={`Open ${p.name} setup`}
                      aria-label={`Open ${p.name} setup`}
                    >
                      <ExternalLink className="w-3.5 h-3.5"/>
                    </a>
                  )}
                </div>
              </motion.div>
            )
          })}
        </div>
      )}

      {configProvider && (
        <div className="fixed inset-0 z-50 bg-black/35 flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white rounded-2xl border border-gray-200 shadow-xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <div>
                <h3 className="text-base font-semibold text-gray-900">Configure {configProvider.name} API key</h3>
                <p className="text-xs text-gray-500 mt-0.5">Paste key to continue. Use <span className="font-mono">NONE</span> to clear.</p>
              </div>
              <button
                onClick={() => { setConfigProvider(null); setPendingAction(null); setApiKeyInput('') }}
                className="p-1.5 rounded-lg hover:bg-gray-100"
                title="Close dialog"
                aria-label="Close dialog"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <input
                type="password"
                placeholder="Enter API key"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                className="input"
              />
              <div className="text-xs text-gray-500">
                Need a key? <a className="text-sentinel-600 hover:underline" href={configProvider.setup_url} target="_blank" rel="noreferrer">Open provider setup</a>
              </div>
            </div>
            <div className="px-5 py-4 border-t border-gray-100 flex justify-end gap-2">
              <button
                onClick={() => { setConfigProvider(null); setPendingAction(null); setApiKeyInput('') }}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button onClick={saveApiKey} className="btn-primary" disabled={configureMutation.isPending}>
                {configureMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save key'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
