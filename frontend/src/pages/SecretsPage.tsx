import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Key, AlertTriangle, CheckCircle, ArrowRight, Loader2, Shield } from 'lucide-react'
import apiClient from '@/api/client'
import { format, parseISO } from 'date-fns'
import clsx from 'clsx'

const SECRET_TYPES: Record<string, { label: string; color: string }> = {
  aws_credential: { label: 'AWS Credential', color: 'text-orange-700 bg-orange-50 border-orange-200' },
  github_pat: { label: 'GitHub PAT', color: 'text-gray-800 bg-gray-100 border-gray-200' },
  github_actions_token: { label: 'GitHub Actions Token', color: 'text-gray-800 bg-gray-100 border-gray-200' },
  openai_key: { label: 'OpenAI API Key', color: 'text-green-800 bg-green-50 border-green-200' },
  stripe_live_key: { label: 'Stripe Live Key', color: 'text-purple-800 bg-purple-50 border-purple-200' },
  jwt_secret: { label: 'JWT Secret', color: 'text-blue-800 bg-blue-50 border-blue-200' },
  private_key: { label: 'Private Key', color: 'text-red-800 bg-red-50 border-red-200' },
  hardcoded_password: { label: 'Hardcoded Password', color: 'text-red-800 bg-red-50 border-red-200' },
  api_key: { label: 'API Key', color: 'text-indigo-800 bg-indigo-50 border-indigo-200' },
  slack_token: { label: 'Slack Token', color: 'text-green-800 bg-green-50 border-green-200' },
  mongodb_uri: { label: 'MongoDB URI', color: 'text-green-800 bg-green-50 border-green-200' },
  postgres_uri: { label: 'PostgreSQL URI', color: 'text-blue-800 bg-blue-50 border-blue-200' },
  google_api_key: { label: 'Google API Key', color: 'text-blue-800 bg-blue-50 border-blue-200' },
}

export default function SecretsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['secrets'],
    queryFn: () => apiClient.get('/findings', {
      params: { category: 'secrets', status: 'open', limit: 100 }
    }).then(r => r.data),
  })

  const secrets: any[] = data?.findings || []
  const byType = secrets.reduce((acc: Record<string, number>, s) => {
    const t = s.secret_type || 'unknown'
    acc[t] = (acc[t] || 0) + 1
    return acc
  }, {})

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Secret Scanning</h1>
        <p className="text-muted mt-1">
          15+ credential pattern types detected across all scanned files. Hardcoded secrets are always critical severity.
        </p>
      </div>

      {secrets.length > 0 && (
        <div className="card border-l-4 border-l-red-500 bg-red-50 p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <div>
              <div className="font-semibold text-red-900 mb-1">
                {secrets.length} hardcoded secret{secrets.length > 1 ? 's' : ''} detected
              </div>
              <div className="text-sm text-red-700">
                Revoke and rotate these credentials immediately. They are permanently stored in git history even after removal.
                Use <code className="font-mono text-xs bg-red-100 px-1 rounded">git-filter-repo</code> to purge from history.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* By type breakdown */}
      {Object.keys(byType).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(byType).map(([type, count]) => {
            const meta = SECRET_TYPES[type] || { label: type, color: 'bg-gray-100 text-gray-700 border-gray-200' }
            return (
              <span key={type} className={`badge border ${meta.color}`}>
                {meta.label} ({count})
              </span>
            )
          })}
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="section-title">Detected Secrets ({secrets.length})</h2>
        </div>
        {isLoading ? <div className="p-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-400" /></div>
        : secrets.length === 0 ? (
          <div className="p-12 text-center">
            <CheckCircle className="w-10 h-10 mx-auto mb-3 text-green-500 opacity-60" />
            <div className="text-gray-500 font-medium">No hardcoded secrets found</div>
            <div className="text-sm text-gray-400 mt-1">All scanned files are clear of credential patterns</div>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {secrets.map((s: any) => {
              const meta = SECRET_TYPES[s.secret_type] || { label: s.secret_type || 'Secret', color: 'bg-gray-100 text-gray-700 border-gray-200' }
              return (
                <Link key={s.id} to={`/app/findings/${s.id}`}
                  className="flex items-start gap-4 px-6 py-4 hover:bg-gray-50 transition-colors group">
                  <div className="w-9 h-9 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0">
                    <Key className="w-4 h-4 text-red-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="badge badge-critical text-xs">CRITICAL</span>
                      <span className={`badge border text-xs ${meta.color}`}>{meta.label}</span>
                    </div>
                    <div className="font-medium text-gray-900 truncate">{s.title}</div>
                    {s.file_path && (
                      <div className="font-mono text-xs text-gray-500 mt-0.5">{s.file_path}:{s.line_start}</div>
                    )}
                    <div className="text-xs text-gray-500 mt-1">{s.why_flagged?.slice(0, 120)}</div>
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0 text-right">
                    <div className="text-xs text-gray-500">{s.first_seen_at ? format(parseISO(s.first_seen_at), 'MMM d') : ''}</div>
                    <ArrowRight className="w-4 h-4 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
