import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Activity, CheckCircle, XCircle, Loader2, Cpu, Database, Zap, Clock } from 'lucide-react'
import apiClient from '@/api/client'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { format, parseISO } from 'date-fns'

export default function ObservabilityPage() {
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => apiClient.get('/observability/health').then(r => r.data),
    refetchInterval: 15000,
  })
  const { data: metrics } = useQuery({
    queryKey: ['scan-metrics'],
    queryFn: () => apiClient.get('/observability/metrics').then(r => r.data),
    refetchInterval: 30000,
  })

  const StatusDot = ({ status }: { status: string }) => (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${status === 'healthy' ? 'text-green-700' : status === 'degraded' ? 'text-yellow-700' : 'text-red-700'}`}>
      <span className={`w-2 h-2 rounded-full ${status === 'healthy' ? 'bg-green-500' : status === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'}`} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )

  const dailyScans = metrics?.daily_scans || []

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Observability</h1>
        <p className="text-muted mt-1">System health, scan queue, AI provider status, and performance metrics.</p>
      </div>

      {/* Overall status banner */}
      {health && (
        <div className={`card p-4 flex items-center gap-3 ${health.overall === 'healthy' ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200'}`}>
          <Activity className={`w-5 h-5 ${health.overall === 'healthy' ? 'text-green-600' : 'text-yellow-600'}`} />
          <div>
            <span className="font-semibold text-gray-900">System status: </span>
            <StatusDot status={health.overall} />
            <span className="text-xs text-gray-500 ml-3">v{health.version} · {health.environment}</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Services */}
        <div className="card p-5">
          <h3 className="section-title mb-4">Services</h3>
          {healthLoading ? <Loader2 className="w-5 h-5 animate-spin text-gray-400" /> : (
            <div className="space-y-3">
              {[
                { label: 'PostgreSQL', check: health?.checks?.database },
                { label: 'Redis', check: health?.checks?.redis },
              ].map(({ label, check }) => (
                <div key={label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-gray-400" />
                    <span className="text-sm font-medium text-gray-700">{label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {check?.latency_ms && <span className="text-xs text-gray-500">{check.latency_ms}ms</span>}
                    <StatusDot status={check?.status || 'unknown'} />
                  </div>
                </div>
              ))}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-gray-400" />
                  <span className="text-sm font-medium text-gray-700">Scan Queue</span>
                </div>
                <span className="text-xs text-gray-600 font-medium">
                  {health?.checks?.scan_queue?.queued || 0} queued · {health?.checks?.scan_queue?.running || 0} running
                </span>
              </div>
            </div>
          )}
        </div>

        {/* AI Providers */}
        <div className="card p-5 md:col-span-2">
          <h3 className="section-title mb-4">AI Providers</h3>
          {healthLoading ? <Loader2 className="w-5 h-5 animate-spin text-gray-400" /> : (
            <div className="space-y-2">
              {(health?.checks?.ai_providers || []).map((p: any) => (
                <div key={p.provider} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-sm font-medium text-gray-700 capitalize">{p.provider}</span>
                    <span className="font-mono text-xs text-gray-400">{p.model}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    {p.latency_ms && <span className="text-xs text-gray-500">{p.latency_ms}ms</span>}
                    <StatusDot status={p.available ? 'healthy' : 'unhealthy'} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Scan activity chart */}
      <div className="card p-5">
        <h3 className="section-title mb-5">Scan Activity (Last 7 Days)</h3>
        {dailyScans.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={dailyScans}>
              <defs>
                <linearGradient id="scanGrad2" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9ca3af' }}
                tickFormatter={(d) => format(parseISO(d), 'MMM d')} />
              <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }} />
              <Area type="monotone" dataKey="count" name="Scans" stroke="#6366f1"
                fill="url(#scanGrad2)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-44 flex items-center justify-center text-gray-400 text-sm">No scan data yet</div>
        )}
      </div>

      {/* Scan metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Scans', value: metrics?.total_scans ?? '—' },
          { label: 'Scans Last 7 Days', value: metrics?.scans_last_7_days ?? '—' },
          { label: 'Avg Duration', value: metrics?.avg_scan_duration_seconds ? `${metrics.avg_scan_duration_seconds}s` : '—' },
          { label: 'Completed', value: metrics?.status_breakdown?.completed ?? '—' },
        ].map(({ label, value }) => (
          <div key={label} className="card p-4 text-center">
            <div className="text-2xl font-black text-gray-900">{value}</div>
            <div className="text-sm text-gray-500 mt-1">{label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
