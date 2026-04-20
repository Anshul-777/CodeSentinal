import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  GitBranch, Github, Plus, AlertCircle, CheckCircle, Shield,
  Settings, ArrowRight, Lock, Globe, Star, Loader2, ExternalLink,
  RefreshCw, Unplug,
} from 'lucide-react'
import apiClient from '@/api/client'
import { useAuthStore } from '@/store/authStore'
import type { Repository } from '@/types'
import { format, parseISO } from 'date-fns'
import toast from 'react-hot-toast'
import { useEffect, useRef, useState } from 'react'
import clsx from 'clsx'

function RiskPill({ score }: { score?: number }) {
  if (score == null) return <span className="text-xs text-gray-400">—</span>
  const c = score >= 80 ? 'text-red-700 bg-red-50 border-red-200'
    : score >= 50 ? 'text-orange-700 bg-orange-50 border-orange-200'
    : score >= 20 ? 'text-yellow-700 bg-yellow-50 border-yellow-200'
    : 'text-green-700 bg-green-50 border-green-200'
  return <span className={`badge ${c} font-bold`}>Risk {score}</span>
}

function ConnectionBadge({ status }: { status: string }) {
  if (status === 'connected') return <span className="flex items-center gap-1 text-xs text-green-700"><span className="w-2 h-2 rounded-full bg-green-500" />Connected</span>
  if (status === 'error') return <span className="flex items-center gap-1 text-xs text-red-700"><span className="w-2 h-2 rounded-full bg-red-500" />Error</span>
  return <span className="flex items-center gap-1 text-xs text-gray-500"><span className="w-2 h-2 rounded-full bg-gray-400" />Disconnected</span>
}

export default function RepositoriesPage() {
  const qc = useQueryClient()
  const { user } = useAuthStore()
  const [showGHConnect, setShowGHConnect] = useState(false)
  const [manualInstallationId, setManualInstallationId] = useState('')
  const [searchParams, setSearchParams] = useSearchParams()
  const processedInstallationRef = useRef<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['repos'],
    queryFn: () => apiClient.get('/repos').then((r) => r.data),
  })

  const repos: Repository[] = data?.repositories || []
  const total: number = data?.total || 0

  const connectMutation = useMutation({
    mutationFn: (installationId: string) =>
      apiClient.post('/repos/connect-github', { installation_id: installationId, provider: 'github' }),
    onSuccess: (res) => {
      const connected = res?.data?.connected ?? 0
      toast.success(`GitHub connected. Imported ${connected} repositories.`)
      qc.invalidateQueries({ queryKey: ['repos'] })
      setShowGHConnect(false)
      setManualInstallationId('')
    },
    onError: (e: any) => {
      toast.error(e?.response?.data?.detail || 'Could not complete GitHub connection')
    },
  })

  useEffect(() => {
    const installationId = searchParams.get('installation_id')
    if (!installationId) return
    if (processedInstallationRef.current === installationId) return

    processedInstallationRef.current = installationId
    connectMutation.mutate(installationId)

    const next = new URLSearchParams(searchParams)
    next.delete('installation_id')
    next.delete('setup_action')
    next.delete('state')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const onManualConnect = () => {
    const installationId = manualInstallationId.trim()
    if (!installationId) {
      toast.error('Enter installation id first')
      return
    }
    connectMutation.mutate(installationId)
  }

  const ghAppUrl = `https://github.com/apps/${import.meta.env.VITE_GITHUB_APP_NAME || 'codesentinel'}/installations/new`

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">Repositories</h1>
          <p className="text-muted mt-1">{total} repositories connected</p>
        </div>
        <button
          onClick={() => setShowGHConnect(true)}
          className="btn-primary text-sm"
        >
          <Plus className="w-4 h-4" />
          Connect GitHub
        </button>
      </div>

      {/* GitHub App connect panel */}
      {(showGHConnect || total === 0) && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="card border-2 border-dashed border-sentinel-200 bg-sentinel-50/30 p-8"
        >
          <div className="max-w-2xl mx-auto text-center">
            <div className="w-14 h-14 bg-gray-900 rounded-2xl flex items-center justify-center mx-auto mb-5">
              <Github className="w-8 h-8 text-white" />
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Connect your GitHub repositories</h2>
            <p className="text-gray-600 text-sm leading-relaxed mb-6 max-w-lg mx-auto">
              Install the CodeSentinel GitHub App on your organization or specific repositories.
              After installation, your repos will appear here automatically.
              We request the minimum permissions needed: read code, write check runs and PR reviews.
            </p>

            <div className="grid grid-cols-3 gap-4 mb-8 text-sm text-left">
              {[
                { icon: Shield, title: 'PR Scanning', desc: 'Auto-scan every pull request with the 5-agent pipeline' },
                { icon: GitBranch, title: 'Check Runs', desc: 'Post results back as GitHub Check Runs with merge blocking' },
                { icon: Settings, title: 'Per-repo Config', desc: 'Configure blocking rules, auto-fix mode, compliance profiles' },
              ].map(({ icon: Icon, title, desc }) => (
                <div key={title} className="bg-white rounded-xl border border-gray-200 p-4">
                  <Icon className="w-5 h-5 text-sentinel-600 mb-2" />
                  <div className="font-semibold text-gray-900 mb-1">{title}</div>
                  <div className="text-xs text-gray-500">{desc}</div>
                </div>
              ))}
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <a
                href={ghAppUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary"
              >
                <Github className="w-4 h-4" />
                Install GitHub App
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
              <p className="text-xs text-gray-400">
                After installing, repos will appear here within 30 seconds.
              </p>
            </div>

            <div className="mt-5 pt-5 border-t border-gray-200 max-w-md mx-auto text-left">
              <p className="text-xs text-gray-500 mb-2">If redirect/callback is not configured yet, paste GitHub installation id manually:</p>
              <div className="flex gap-2">
                <input
                  value={manualInstallationId}
                  onChange={(e) => setManualInstallationId(e.target.value)}
                  className="input text-sm"
                  placeholder="e.g. 61401234"
                />
                <button onClick={onManualConnect} disabled={connectMutation.isPending} className="btn-secondary text-sm whitespace-nowrap">
                  {connectMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Complete connect'}
                </button>
              </div>
            </div>

            {total > 0 && (
              <button onClick={() => setShowGHConnect(false)} className="mt-4 text-sm text-gray-400 hover:text-gray-600 underline">
                Dismiss
              </button>
            )}
          </div>
        </motion.div>
      )}

      {/* Repos grid */}
      {total > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {repos.map((repo, i) => (
            <motion.div
              key={repo.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
            >
              <Link to={`/app/repositories/${repo.id}`} className="card card-hover block p-5 h-full">
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-9 h-9 bg-gray-900 rounded-xl flex items-center justify-center flex-shrink-0">
                      <Github className="w-5 h-5 text-white" />
                    </div>
                    <div className="min-w-0">
                      <div className="font-semibold text-gray-900 truncate">{repo.name}</div>
                      <div className="text-xs text-gray-500 truncate">{repo.full_name}</div>
                    </div>
                  </div>
                  <ConnectionBadge status={repo.connection_status} />
                </div>

                {repo.description && (
                  <p className="text-sm text-gray-500 mb-4 line-clamp-2">{repo.description}</p>
                )}

                <div className="flex items-center gap-3 mb-4 text-xs text-gray-500">
                  {repo.language && <span className="flex items-center gap-1">{repo.language}</span>}
                  <span className="flex items-center gap-1">
                    {repo.is_private ? <Lock className="w-3 h-3" /> : <Globe className="w-3 h-3" />}
                    {repo.is_private ? 'Private' : 'Public'}
                  </span>
                  <span className="flex items-center gap-1">
                    <GitBranch className="w-3 h-3" />{repo.default_branch}
                  </span>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-gray-500">{repo.total_scans} scans</span>
                    {repo.open_findings > 0 && (
                      <span className="text-red-600 font-semibold">{repo.open_findings} open</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <RiskPill score={repo.last_scan_risk_score ?? undefined} />
                    <ArrowRight className="w-4 h-4 text-gray-300" />
                  </div>
                </div>

                {repo.last_scan_at && (
                  <div className="text-xs text-gray-400 mt-2">
                    Last scan: {format(parseISO(repo.last_scan_at), 'MMM d, yyyy')}
                  </div>
                )}
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
