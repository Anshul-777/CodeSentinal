import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import ProductTour from '@/components/tour/ProductTour'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Shield, LayoutDashboard, GitBranch, Scan, Bug, Wrench, CheckSquare,
  Package, Key, FileText, ClipboardList, BarChart3, Settings, Bell,
  Plug, Cpu, Users, Activity, BookOpen, ChevronLeft, ChevronRight,
  LogOut, User, Search, Menu, X, ChevronDown,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import apiClient from '@/api/client'
import clsx from 'clsx'

interface NavItem {
  path: string
  label: string
  icon: React.ElementType
  badge?: string
  section?: string
}

const NAV_ITEMS: NavItem[] = [
  { path: '/app/dashboard', label: 'Dashboard', icon: LayoutDashboard, section: 'Overview' },
  { path: '/app/repositories', label: 'Repositories', icon: GitBranch, section: 'Security' },
  { path: '/app/scans', label: 'Scans', icon: Scan, section: 'Security' },
  { path: '/app/findings', label: 'Findings', icon: Bug, section: 'Security' },
  { path: '/app/autofix', label: 'Auto-Fix', icon: Wrench, section: 'Security' },
  { path: '/app/secrets', label: 'Secrets', icon: Key, section: 'Security' },
  { path: '/app/dependencies', label: 'Dependencies', icon: Package, section: 'Analysis' },
  { path: '/app/compliance', label: 'Compliance', icon: CheckSquare, section: 'Analysis' },
  { path: '/app/sbom', label: 'SBOM', icon: FileText, section: 'Analysis' },
  { path: '/app/reports', label: 'Reports', icon: BarChart3, section: 'Governance' },
  { path: '/app/policies', label: 'Policies', icon: BookOpen, section: 'Governance' },
  { path: '/app/audit', label: 'Audit Logs', icon: ClipboardList, section: 'Governance' },
  { path: '/app/notifications', label: 'Notifications', icon: Bell, section: 'Configuration' },
  { path: '/app/integrations', label: 'Integrations', icon: Plug, section: 'Configuration' },
  { path: '/app/models', label: 'AI Models', icon: Cpu, section: 'Configuration' },
  { path: '/app/team', label: 'Team', icon: Users, section: 'Configuration' },
  { path: '/app/observability', label: 'Observability', icon: Activity, section: 'Configuration' },
  { path: '/app/settings', label: 'Settings', icon: Settings, section: 'Configuration' },
]

const SECTIONS = ['Overview', 'Security', 'Analysis', 'Governance', 'Configuration']

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = async () => {
    try { await apiClient.post('/auth/logout') } catch {}
    logout()
    navigate('/login')
  }

  const grouped = SECTIONS.reduce((acc, section) => {
    acc[section] = NAV_ITEMS.filter((i) => i.section === section)
    return acc
  }, {} as Record<string, NavItem[]>)

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className={clsx('flex items-center gap-3 px-4 py-5 border-b border-gray-100', collapsed && 'justify-center px-2')}>
        <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-sentinel-600 to-violet-600 rounded-lg flex items-center justify-center shadow-glow">
          <Shield className="w-5 h-5 text-white" />
        </div>
        {!collapsed && (
          <div>
            <div className="font-bold text-gray-900 leading-none">CodeSentinel</div>
            <div className="text-[10px] text-gray-500 mt-0.5 font-medium tracking-wide uppercase">Security Platform</div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-4 space-y-0.5">
        {SECTIONS.map((section) => (
          <div key={section} className="mb-3">
            {!collapsed && (
              <div className="px-3 mb-1 text-[10px] font-semibold text-gray-400 uppercase tracking-widest">
                {section}
              </div>
            )}
            {grouped[section].map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  clsx(
                    'sidebar-item',
                    isActive && 'sidebar-item-active',
                    collapsed && 'justify-center px-2'
                  )
                }
                title={collapsed ? item.label : undefined}
              >
                <item.icon className="w-4 h-4 flex-shrink-0" />
                {!collapsed && <span>{item.label}</span>}
                {!collapsed && item.badge && (
                  <span className="ml-auto text-[10px] font-semibold bg-sentinel-100 text-sentinel-700 px-1.5 py-0.5 rounded-full">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* User area */}
      <div className={clsx('border-t border-gray-100 px-2 py-3', collapsed && 'px-1')}>
        {user?.is_test_user && !collapsed && (
          <div className="mb-2 mx-1 px-2 py-1.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700 font-medium">
            🧪 Test Account
          </div>
        )}
        <div className={clsx('flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-gray-100 cursor-pointer', collapsed && 'justify-center')}>
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-sentinel-500 to-violet-500 flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-bold text-white">
              {user?.full_name?.charAt(0) || 'U'}
            </span>
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-900 truncate">{user?.full_name}</div>
              <div className="text-xs text-gray-500 truncate">{user?.email}</div>
            </div>
          )}
        </div>
        <button
          onClick={handleLogout}
          className={clsx(
            'mt-1 w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? 'Sign out' : undefined}
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          {!collapsed && 'Sign out'}
        </button>
      </div>
    </div>
  )

  return (
    <>
    <ProductTour />
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Desktop sidebar */}
      <aside
        className={clsx(
          'hidden lg:flex flex-col bg-white border-r border-gray-200 flex-shrink-0 transition-all duration-300',
          collapsed ? 'w-[60px]' : 'w-[220px]'
        )}
      >
        <SidebarContent />
        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute left-0 top-1/2 -translate-y-1/2 translate-x-[208px] w-5 h-5 bg-white border border-gray-200 rounded-full flex items-center justify-center shadow-sm hover:shadow-md transition-all z-10"
          style={{ left: collapsed ? '48px' : '208px' }}
        >
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
        </button>
      </aside>

      {/* Mobile sidebar overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/20 z-40 lg:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              className="fixed left-0 top-0 h-full w-[240px] bg-white border-r border-gray-200 z-50 lg:hidden"
            >
              <SidebarContent />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Topbar */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center px-4 gap-4 flex-shrink-0">
          <button
            onClick={() => setMobileOpen(true)}
            className="lg:hidden p-1.5 rounded-lg hover:bg-gray-100"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="flex-1 flex items-center gap-3">
            {/* Global search placeholder */}
            <div className="hidden sm:flex items-center gap-2 max-w-xs w-full px-3 py-1.5 bg-gray-100 rounded-lg text-sm text-gray-400">
              <Search className="w-4 h-4" />
              <span>Search findings, scans, repos…</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Org indicator */}
            {user?.organization && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg text-sm">
                <div className="w-5 h-5 bg-sentinel-600 rounded text-white text-[10px] flex items-center justify-center font-bold">
                  {user.organization.name.charAt(0)}
                </div>
                <span className="text-gray-700 font-medium max-w-[120px] truncate">{user.organization.name}</span>
                <span className="text-[10px] text-gray-400 bg-white border px-1.5 py-0.5 rounded-full font-medium capitalize">
                  {user.organization.plan}
                </span>
              </div>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1600px] w-full mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
    </>
  )
}
