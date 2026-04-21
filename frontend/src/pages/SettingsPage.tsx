import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { User, Bell, Key, Building, Loader2, CheckCircle, Eye, EyeOff, Github, Trash2, AlertTriangle } from 'lucide-react'
import apiClient from '@/api/client'
import { useAuthStore } from '@/store/authStore'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const { user, setUser, logout } = useAuthStore()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState('profile')
  const [showApiKey, setShowApiKey] = useState(false)
  const [newApiKey, setNewApiKey] = useState<string | null>(null)
  const [confirmEmail, setConfirmEmail] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [profile, setProfile] = useState({
    full_name: user?.full_name || '',
    job_title: user?.job_title || '',
    github_username: user?.github_username || '',
    phone: user?.phone || '',
    user_timezone: user?.user_timezone || 'UTC',
    avatar_url: user?.avatar_url || '',
    notify_email: user?.notify_email ?? true,
    notify_slack: user?.notify_slack ?? false,
    notify_critical_only: user?.notify_critical_only ?? false,
  })

  const avatarGallery = useMemo(() => {
    const seeds = ['guardian', 'cypher', 'audit', 'shield', 'vigil', 'vector']
    return seeds.map((seed) => `https://api.dicebear.com/9.x/thumbs/svg?seed=${seed}`)
  }, [])

  const { data: reposData } = useQuery({
    queryKey: ['repos'],
    queryFn: () => apiClient.get('/repos').then((r) => r.data),
  })

  const { data: githubSetup } = useQuery({
    queryKey: ['github-setup'],
    queryFn: () => apiClient.get('/repos/github/setup').then((r) => r.data),
  })

  const profileMutation = useMutation({
    mutationFn: (data: any) => apiClient.patch('/settings/profile', data),
    onSuccess: (res) => { toast.success('Profile updated'); setUser(res.data) },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Update failed'),
  })

  const apiKeyMutation = useMutation({
    mutationFn: () => apiClient.post('/auth/generate-api-key'),
    onSuccess: (res) => { setNewApiKey(res.data.api_key); toast.success('New API key generated — copy it now!') },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const deleteAccountMutation = useMutation({
    mutationFn: () => apiClient.post('/auth/delete-account', {
      confirm_email: confirmEmail,
      password: confirmPassword,
    }),
    onSuccess: () => {
      toast.success('Account deleted permanently.')
      logout()
      navigate('/login')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to delete account'),
  })

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'github', label: 'GitHub Data', icon: Github },
    { id: 'api', label: 'API Access', icon: Key },
    { id: 'organization', label: 'Organization', icon: Building },
    { id: 'danger', label: 'Danger Zone', icon: AlertTriangle },
  ]

  const repos = reposData?.repositories || []
  const connectedCount = repos.filter((r: any) => r.connection_status === 'connected').length

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Settings</h1>
        <p className="text-muted mt-1">Manage your profile, notification preferences, and API access.</p>
      </div>

      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === tab.id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            <tab.icon className="w-4 h-4" />{tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'profile' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="card p-6 space-y-4">
            <h3 className="section-title">Identity</h3>
            <div className="flex items-center gap-4">
              <img
                src={profile.avatar_url || avatarGallery[0]}
                alt="Profile avatar"
                className="w-20 h-20 rounded-2xl border border-gray-200 bg-gray-50"
              />
              <div>
                <div className="font-semibold text-gray-900">{profile.full_name || user?.email}</div>
                <div className="text-sm text-gray-500">{profile.job_title || 'Security member'}</div>
                <div className="text-xs text-gray-400 mt-1">{user?.email}</div>
              </div>
            </div>
            <div>
              <label className="label">Avatar gallery</label>
              <div className="grid grid-cols-6 gap-2 mt-2">
                {avatarGallery.map((url) => (
                  <button
                    key={url}
                    onClick={() => setProfile((p) => ({ ...p, avatar_url: url }))}
                    className={`rounded-xl border p-1 ${profile.avatar_url === url ? 'border-sentinel-500 ring-2 ring-sentinel-100' : 'border-gray-200'}`}
                  >
                    <img src={url} alt="Avatar option" className="w-10 h-10 rounded-lg" />
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="card p-6 xl:col-span-2 space-y-5">
            <h3 className="section-title">Profile Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div><label className="label">Full name</label>
                <input value={profile.full_name} onChange={e => setProfile(p=>({...p,full_name:e.target.value}))} className="input" placeholder="Your full name" title="Full name" aria-label="Full name" /></div>
              <div><label className="label">Job title</label>
                <input value={profile.job_title || ''} onChange={e => setProfile(p=>({...p,job_title:e.target.value}))} className="input" placeholder="Your job title" title="Job title" aria-label="Job title" /></div>
              <div><label className="label">GitHub username</label>
                <input value={profile.github_username || ''} onChange={e => setProfile(p=>({...p,github_username:e.target.value}))} className="input" placeholder="GitHub username" title="GitHub username" aria-label="GitHub username" /></div>
              <div><label className="label">Phone</label>
                <input value={profile.phone || ''} onChange={e => setProfile(p=>({...p,phone:e.target.value}))} className="input" placeholder="Phone number" title="Phone" aria-label="Phone" /></div>
              <div><label className="label">Timezone</label>
                <input value={profile.user_timezone || 'UTC'} onChange={e => setProfile(p=>({...p,user_timezone:e.target.value}))} className="input" placeholder="Timezone" title="Timezone" aria-label="Timezone" /></div>
              <div><label className="label">Avatar URL</label>
                <input value={profile.avatar_url || ''} onChange={e => setProfile(p=>({...p,avatar_url:e.target.value}))} className="input" placeholder="Avatar URL" title="Avatar URL" aria-label="Avatar URL" /></div>
            </div>
            <div className="text-sm text-gray-500"><strong>Email:</strong> {user?.email} <span className="text-xs text-gray-400">(contact support to change)</span></div>
            <button onClick={() => profileMutation.mutate(profile)} disabled={profileMutation.isPending} className="btn-primary text-sm">
              {profileMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin"/> : <CheckCircle className="w-4 h-4"/>}
              Save Changes
            </button>
          </div>
        </div>
      )}

      {activeTab === 'notifications' && (
        <div className="card p-6 space-y-5 max-w-2xl">
          <h3 className="section-title">Notification Preferences</h3>
          {[
            { key: 'notify_email', label: 'Email notifications', desc: 'Receive scan results and critical alerts by email' },
            { key: 'notify_slack', label: 'Slack notifications', desc: 'Receive alerts via your connected Slack integration' },
            { key: 'notify_critical_only', label: 'Critical only', desc: 'Only notify for critical-severity findings' },
          ].map(({ key, label, desc }) => (
            <div key={key} className="flex items-start justify-between gap-4">
              <div><div className="font-medium text-gray-900 text-sm">{label}</div><div className="text-xs text-gray-500">{desc}</div></div>
              <button onClick={() => { const v = !profile[key as keyof typeof profile]; setProfile(p=>({...p,[key]:v})); profileMutation.mutate({...profile,[key]:v}) }}
                title={`Toggle ${label}`}
                aria-label={`Toggle ${label}`}
                className={`relative w-10 h-5 rounded-full transition-colors flex-shrink-0 ${profile[key as keyof typeof profile] ? 'bg-sentinel-600' : 'bg-gray-300'}`}>
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow ${profile[key as keyof typeof profile] ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </button>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'github' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="card p-6 xl:col-span-2 space-y-4">
            <h3 className="section-title">Connected Repositories</h3>
            <div className="text-sm text-gray-600">{connectedCount} connected of {repos.length} total repositories.</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {repos.map((repo: any) => (
                <div key={repo.id} className="rounded-xl border border-gray-200 p-3">
                  <div className="font-medium text-gray-900 truncate">{repo.full_name}</div>
                  <div className="text-xs text-gray-500 mt-1">{repo.language || 'Unknown'} · {repo.default_branch}</div>
                  <div className="text-xs mt-1">
                    <span className={repo.connection_status === 'connected' ? 'text-green-600' : 'text-gray-500'}>{repo.connection_status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card p-6 space-y-3">
            <h3 className="section-title">GitHub App Status</h3>
            <div className="text-sm text-gray-600">App: <span className="font-mono">{githubSetup?.app_slug || 'codesentinel'}</span></div>
            <div className="text-sm">Configured: <span className={githubSetup?.configured?.ready ? 'text-green-600 font-semibold' : 'text-amber-600 font-semibold'}>{githubSetup?.configured?.ready ? 'Ready' : 'Incomplete'}</span></div>
            <a href={githubSetup?.install_url || '#'} target="_blank" rel="noreferrer" className="btn-secondary text-sm justify-center">Open install page</a>
            {profile.github_username && (
              <a href={`https://github.com/${profile.github_username}`} target="_blank" rel="noreferrer" className="text-sentinel-600 text-sm hover:underline">
                View @{profile.github_username} profile
              </a>
            )}
          </div>
        </div>
      )}

      {activeTab === 'api' && (
        <div className="card p-6 max-w-2xl space-y-5">
          <h3 className="section-title">API Key</h3>
          <p className="text-sm text-gray-600">Use your API key to access the CodeSentinel REST API programmatically. Keys are shown only once — store them securely.</p>
          {user?.api_key_prefix ? (
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl border border-gray-200">
              <Key className="w-4 h-4 text-gray-500" />
              <span className="font-mono text-sm text-gray-700">{user.api_key_prefix}…<span className="text-gray-400">••••••••</span></span>
            </div>
          ) : <div className="text-sm text-gray-500">No API key generated yet.</div>}
          {newApiKey && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-xl">
              <div className="text-xs font-semibold text-green-800 mb-2">⚠️ Copy this key now — it will not be shown again.</div>
              <div className="flex items-center gap-2">
                <code className="flex-1 font-mono text-xs text-green-900 break-all bg-green-100 p-2 rounded">
                  {showApiKey ? newApiKey : newApiKey.slice(0, 12) + '•'.repeat(30)}
                </code>
                <button onClick={() => setShowApiKey(!showApiKey)} className="p-1.5 text-green-700">
                  {showApiKey ? <EyeOff className="w-4 h-4"/> : <Eye className="w-4 h-4"/>}
                </button>
              </div>
              <button onClick={() => { navigator.clipboard.writeText(newApiKey); toast.success('Copied!') }} className="mt-2 text-xs text-green-700 hover:underline">Copy to clipboard</button>
            </div>
          )}
          <button onClick={() => apiKeyMutation.mutate()} disabled={apiKeyMutation.isPending} className="btn-primary text-sm">
            {apiKeyMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin"/> : <Key className="w-4 h-4"/>}
            {user?.api_key_prefix ? 'Regenerate API Key' : 'Generate API Key'}
          </button>
          <p className="text-xs text-gray-400">Generating a new key will invalidate the previous one immediately.</p>
        </div>
      )}

      {activeTab === 'organization' && (
        <div className="card p-6 space-y-4 max-w-2xl">
          <h3 className="section-title">Organization</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><div className="text-gray-500 text-xs mb-1">Name</div><div className="font-semibold text-gray-900">{user?.organization?.name}</div></div>
            <div><div className="text-gray-500 text-xs mb-1">Slug</div><div className="font-mono text-gray-700">{user?.organization?.slug}</div></div>
            <div><div className="text-gray-500 text-xs mb-1">Plan</div><div className="capitalize font-semibold text-sentinel-700">{user?.organization?.plan}</div></div>
          </div>
        </div>
      )}

      {activeTab === 'danger' && (
        <div className="card p-6 border border-red-200 bg-red-50/40 max-w-2xl space-y-4">
          <h3 className="section-title text-red-700">Permanent Delete Account</h3>
          <p className="text-sm text-red-700">
            This action is irreversible. It removes your account and deletes GitHub-linked organization data owned by this account.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              value={confirmEmail}
              onChange={(e) => setConfirmEmail(e.target.value)}
              className="input"
              placeholder="Type your account email"
            />
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="input"
              placeholder="Type your password"
            />
          </div>
          <button
            onClick={() => {
              if (!confirmEmail || !confirmPassword) {
                toast.error('Enter email and password first.')
                return
              }
              deleteAccountMutation.mutate()
            }}
            disabled={deleteAccountMutation.isPending}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
          >
            {deleteAccountMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            Delete Account Permanently
          </button>
        </div>
      )}
    </div>
  )
}
