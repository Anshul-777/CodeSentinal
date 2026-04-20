import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Users, Plus, Loader2, Trash2, Mail } from 'lucide-react'
import apiClient from '@/api/client'
import toast from 'react-hot-toast'
import { useAuthStore } from '@/store/authStore'
import { format, parseISO } from 'date-fns'
import clsx from 'clsx'

const ROLES = [
  { id: 'admin', label: 'Admin', desc: 'Full access except billing' },
  { id: 'analyst', label: 'Analyst', desc: 'View and manage findings, run scans' },
  { id: 'developer', label: 'Developer', desc: 'View findings and scan results' },
  { id: 'viewer', label: 'Viewer', desc: 'Read-only access' },
]

export default function TeamPage() {
  const { user } = useAuthStore()
  const qc = useQueryClient()
  const [showInvite, setShowInvite] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('developer')

  const { data, isLoading } = useQuery({
    queryKey: ['team-members'],
    queryFn: () => apiClient.get('/team').then(r => r.data),
  })

  const inviteMutation = useMutation({
    mutationFn: (p: any) => apiClient.post('/team/invite', p),
    onSuccess: () => { toast.success('Invitation sent'); qc.invalidateQueries({ queryKey: ['team-members'] }); setShowInvite(false); setInviteEmail('') },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to invite'),
  })

  const removeMutation = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/team/${id}`),
    onSuccess: () => { toast.success('Member removed'); qc.invalidateQueries({ queryKey: ['team-members'] }) },
  })

  const updateRoleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => apiClient.patch(`/team/${id}`, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['team-members'] }),
  })

  const members: any[] = data?.members || []

  const roleBadge = (role: string) => {
    const map: Record<string, string> = { owner: 'bg-sentinel-100 text-sentinel-800 border-sentinel-200', admin: 'bg-purple-100 text-purple-800 border-purple-200', analyst: 'bg-blue-100 text-blue-800 border-blue-200', developer: 'bg-gray-100 text-gray-700 border-gray-200', viewer: 'bg-gray-100 text-gray-500 border-gray-200' }
    return map[role] || map.viewer
  }

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div><h1 className="page-title">Team</h1><p className="text-muted mt-1">{members.length} member{members.length !== 1 ? 's' : ''} in {user?.organization?.name}</p></div>
        <button onClick={() => setShowInvite(!showInvite)} className="btn-primary text-sm"><Plus className="w-4 h-4"/>Invite Member</button>
      </div>

      {showInvite && (
        <div className="card p-5 space-y-4">
          <h3 className="section-title">Invite Team Member</h3>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Email address</label>
              <input type="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} className="input" placeholder="colleague@company.com" /></div>
            <div><label className="label">Role</label>
              <select value={inviteRole} onChange={e => setInviteRole(e.target.value)} className="input bg-white">
                {ROLES.map(r => <option key={r.id} value={r.id}>{r.label} — {r.desc}</option>)}
              </select></div>
          </div>
          <div className="flex gap-3">
            <button onClick={() => inviteMutation.mutate({ email: inviteEmail, role: inviteRole })}
              disabled={!inviteEmail || inviteMutation.isPending} className="btn-primary text-sm">
              {inviteMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin"/> : <Mail className="w-4 h-4"/>}
              Send Invitation
            </button>
            <button onClick={() => setShowInvite(false)} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        {isLoading ? <div className="p-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-400"/></div>
        : members.length === 0 ? (
          <div className="p-12 text-center"><Users className="w-10 h-10 mx-auto mb-3 text-gray-200"/><div className="text-gray-500">Invite your first team member</div></div>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100 bg-gray-50 text-left">
              {['Member','Role','Joined','Actions'].map(h => <th key={h} className="px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-gray-50">
              {members.map((m: any) => (
                <tr key={m.id} className="hover:bg-gray-50">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-sentinel-500 to-violet-500 flex items-center justify-center text-white text-xs font-bold">
                        {m.user?.full_name?.charAt(0) || 'U'}
                      </div>
                      <div>
                        <div className="font-medium text-gray-900">{m.user?.full_name || m.user?.email}</div>
                        <div className="text-xs text-gray-500">{m.user?.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    {m.role === 'owner' ? (
                      <span className={`badge border text-xs ${roleBadge(m.role)}`}>Owner</span>
                    ) : (
                      <select value={m.role} onChange={e => updateRoleMutation.mutate({ id: m.id, role: e.target.value })}
                        className={`badge border text-xs cursor-pointer bg-transparent ${roleBadge(m.role)}`}>
                        {ROLES.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
                      </select>
                    )}
                  </td>
                  <td className="px-5 py-4 text-xs text-gray-500">{m.accepted_at ? format(parseISO(m.accepted_at), 'MMM d, yyyy') : 'Pending'}</td>
                  <td className="px-5 py-4">
                    {m.role !== 'owner' && m.user?.id !== user?.id && (
                      <button onClick={() => removeMutation.mutate(m.id)} className="text-xs text-red-600 hover:underline flex items-center gap-1">
                        <Trash2 className="w-3.5 h-3.5"/>Remove
                      </button>
                    )}
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
