import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Shield, Bug, Wrench, Package, CheckSquare, Key, AlertTriangle,
  TrendingUp, TrendingDown, GitBranch, ArrowRight, Activity,
  Clock, CheckCircle, XCircle, Loader2, BarChart3, Zap,
} from 'lucide-react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts'
import apiClient from '@/api/client'
import { useAuthStore } from '@/store/authStore'
import { format, parseISO } from 'date-fns'
import type { Scan, FindingsSummary } from '@/types'
import clsx from 'clsx'

const SEV_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#3b82f6',
  info: '#9ca3af',
}

function StatCard({ title, value, sub, icon: Icon, color, trend }: {
  title: string; value: string | number; sub?: string;
  icon: React.ElementType; color: string; trend?: 'up' | 'down' | 'neutral'
}) {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="card p-5">
      <div className="flex items-start justify-between mb-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-xs font-medium ${trend === 'up' ? 'text-red-600' : trend === 'down' ? 'text-green-600' : 'text-gray-500'}`}>
            {trend === 'up' ? <TrendingUp className="w-3 h-3" /> : trend === 'down' ? <TrendingDown className="w-3 h-3" /> : null}
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-gray-900 mb-1">{value}</div>
      <div className="text-sm font-medium text-gray-600">{title}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </motion.div>
  )
}

function ScanStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    queued: { label: 'Queued', cls: 'bg-gray-100 text-gray-600' },
    running: { label: 'Running', cls: 'bg-blue-100 text-blue-700' },
    completed: { label: 'Completed', cls: 'bg-green-100 text-green-700' },
    blocked: { label: 'Blocked', cls: 'bg-red-100 text-red-700' },
    failed: { label: 'Failed', cls: 'bg-red-100 text-red-600' },
    cancelled: { label: 'Cancelled', cls: 'bg-gray-100 text-gray-500' },
  }
  const { label, cls } = map[status] || { label: status, cls: 'bg-gray-100 text-gray-600' }
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${cls}`}>{label}</span>
}

export default function DashboardPage() {
  const { user } = useAuthStore()

  const { data: summary } = useQuery({
    queryKey: ['findings-summary'],
    queryFn: () => apiClient.get('/findings/summary/by-org').then((r) => r.data as FindingsSummary),
  })

  const { data: scansData } = useQuery({
    queryKey: ['recent-scans'],
    queryFn: () => apiClient.get('/scans', { params: { limit: 10 } }).then((r) => r.data),
    refetchInterval: 15000,
  })

  const { data: repos } = useQuery({
    queryKey: ['repos'],
    queryFn: () => apiClient.get('/repos').then((r) => r.data),
  })

  const { data: metrics } = useQuery({
    queryKey: ['scan-metrics'],
    queryFn: () => apiClient.get('/observability/metrics').then((r) => r.data),
  })

  const recentScans: Scan[] = scansData?.scans || []
  const totalRepos = repos?.total || 0

  const severityData = summary
    ? Object.entries(summary.by_severity)
        .filter(([, v]) => v > 0)
        .map(([k, v]) => ({ name: k.charAt(0).toUpperCase() + k.slice(1), value: v, color: SEV_COLORS[k] }))
    : []

  const dailyData = metrics?.daily_scans || []
  const categoryData = (summary?.by_category || []).slice(0, 6)

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{greeting}, {user?.full_name?.split(' ')[0]} 👋</h1>
          <p className="text-gray-500 mt-1">
            {user?.organization?.name} · {totalRepos} {totalRepos === 1 ? 'repository' : 'repositories'} connected
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/app/repositories" className="btn-secondary text-sm">
            <GitBranch className="w-4 h-4" />
            Connect repo
          </Link>
          <Link to="/app/scans" className="btn-primary text-sm">
            <Activity className="w-4 h-4" />
            View all scans
          </Link>
        </div>
      </div>

      {/* Alert — if no repos connected */}
      {totalRepos === 0 && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="card border-l-4 border-l-sentinel-500 p-5 bg-sentinel-50"
        >
          <div className="flex items-start gap-4">
            <Shield className="w-8 h-8 text-sentinel-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-gray-900 mb-1">Connect your first repository to get started</h3>
              <p className="text-sm text-gray-600 mb-4">
                Install the CodeSentinel GitHub App on your organization or repository,
                then connect it here to start receiving automated security scans on every pull request.
              </p>
              <Link to="/app/repositories" className="btn-primary text-sm">
                Connect GitHub repository
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </motion.div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Open Findings"
          value={summary?.total_open ?? '—'}
          sub={`${summary?.by_severity?.critical ?? 0} critical`}
          icon={Bug}
          color="bg-red-500"
          trend={summary && summary.total_open > 0 ? 'up' : 'neutral'}
        />
        <StatCard
          title="Repositories"
          value={totalRepos}
          sub="connected"
          icon={GitBranch}
          color="bg-sentinel-600"
        />
        <StatCard
          title="Scans (7 days)"
          value={metrics?.scans_last_7_days ?? '—'}
          sub={`avg ${metrics?.avg_scan_duration_seconds ?? '—'}s`}
          icon={Zap}
          color="bg-violet-600"
        />
        <StatCard
          title="Total Scans"
          value={metrics?.total_scans ?? '—'}
          sub="all time"
          icon={Activity}
          color="bg-emerald-600"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Scan activity */}
        <div className="lg:col-span-2 card p-5">
          <div className="flex items-center justify-between mb-5">
            <h3 className="section-title">Scan Activity (Last 7 Days)</h3>
            <span className="text-xs text-gray-400">{dailyData.length > 0 ? 'Live data' : 'No scans yet'}</span>
          </div>
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={dailyData}>
                <defs>
                  <linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9ca3af' }} tickFormatter={(d) => format(parseISO(d), 'MMM d')} />
                <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }} />
                <Area type="monotone" dataKey="count" name="Scans" stroke="#6366f1" fill="url(#scanGrad)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-44 flex items-center justify-center text-gray-400 text-sm">
              No scan data yet — trigger a scan to see activity
            </div>
          )}
        </div>

        {/* Severity breakdown */}
        <div className="card p-5">
          <h3 className="section-title mb-5">Findings by Severity</h3>
          {severityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={severityData} cx="50%" cy="50%" innerRadius={50} outerRadius={75}
                  dataKey="value" nameKey="name" paddingAngle={3}>
                  {severityData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Legend formatter={(value) => <span className="text-xs text-gray-600">{value}</span>} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-44 flex items-center justify-center text-gray-400 text-sm text-center">
              No open findings<br />Excellent security posture 🎉
            </div>
          )}
        </div>
      </div>

      {/* Categories + Recent scans */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top categories */}
        <div className="card p-5">
          <h3 className="section-title mb-4">Top Vulnerability Categories</h3>
          {categoryData.length > 0 ? (
            <div className="space-y-3">
              {categoryData.map((item: any) => (
                <div key={item.category} className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-700 truncate capitalize">
                        {item.category?.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs font-bold text-gray-900 ml-2">{item.count}</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-sentinel-500 rounded-full"
                        style={{ width: `${Math.min(100, (item.count / (categoryData[0]?.count || 1)) * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400 text-sm">No findings categorized yet</div>
          )}
        </div>

        {/* Recent scans */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between p-5 border-b border-gray-100">
            <h3 className="section-title">Recent Scans</h3>
            <Link to="/app/scans" className="text-sm text-sentinel-600 hover:underline font-medium">View all</Link>
          </div>
          {recentScans.length > 0 ? (
            <div className="divide-y divide-gray-50">
              {recentScans.slice(0, 6).map((scan) => (
                <Link
                  key={scan.id}
                  to={`/app/scans/${scan.id}`}
                  className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex-shrink-0">
                    {scan.status === 'running' ? (
                      <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                    ) : scan.status === 'completed' ? (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    ) : scan.status === 'blocked' ? (
                      <XCircle className="w-4 h-4 text-red-500" />
                    ) : (
                      <Clock className="w-4 h-4 text-gray-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900 truncate">
                        {scan.pr_title || scan.branch || scan.commit_sha?.slice(0, 8) || `Scan #${scan.id.slice(0, 6)}`}
                      </span>
                      <ScanStatusBadge status={scan.status} />
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {scan.trigger.toUpperCase()} · {format(parseISO(scan.created_at), 'MMM d, h:mm a')}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0 text-right">
                    {scan.risk_score != null && (
                      <div className={clsx(
                        'text-sm font-bold',
                        scan.risk_score >= 80 ? 'text-red-600' : scan.risk_score >= 50 ? 'text-orange-600' : scan.risk_score >= 20 ? 'text-yellow-600' : 'text-green-600'
                      )}>
                        {scan.risk_score}
                      </div>
                    )}
                    <div className="text-right">
                      <div className="text-sm font-semibold text-gray-900">{scan.findings_total}</div>
                      <div className="text-xs text-gray-400">findings</div>
                    </div>
                    {scan.findings_critical > 0 && (
                      <span className="badge badge-critical">{scan.findings_critical} crit</span>
                    )}
                    <ArrowRight className="w-4 h-4 text-gray-300" />
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="px-5 py-12 text-center text-gray-400">
              <Activity className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <div className="text-sm font-medium">No scans yet</div>
              <div className="text-xs mt-1">Connect a repository and open a pull request to trigger your first scan</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
