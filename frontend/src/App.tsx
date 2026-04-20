import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useQuery } from '@tanstack/react-query'
import apiClient from '@/api/client'

// Pages — lazy loaded
import LandingPage from '@/pages/LandingPage'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import AppShell from '@/components/layout/AppShell'
import DashboardPage from '@/pages/DashboardPage'
import RepositoriesPage from '@/pages/RepositoriesPage'
import RepositoryDetailPage from '@/pages/RepositoryDetailPage'
import ScansPage from '@/pages/ScansPage'
import ScanDetailPage from '@/pages/ScanDetailPage'
import FindingsPage from '@/pages/FindingsPage'
import FindingDetailPage from '@/pages/FindingDetailPage'
import AutoFixPage from '@/pages/AutoFixPage'
import CompliancePage from '@/pages/CompliancePage'
import DependenciesPage from '@/pages/DependenciesPage'
import SecretsPage from '@/pages/SecretsPage'
import SBOMPage from '@/pages/SBOMPage'
import AuditLogsPage from '@/pages/AuditLogsPage'
import ReportsPage from '@/pages/ReportsPage'
import PoliciesPage from '@/pages/PoliciesPage'
import NotificationsPage from '@/pages/NotificationsPage'
import IntegrationsPage from '@/pages/IntegrationsPage'
import ModelsPage from '@/pages/ModelsPage'
import TeamPage from '@/pages/TeamPage'
import ObservabilityPage from '@/pages/ObservabilityPage'
import SettingsPage from '@/pages/SettingsPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function PublicOnlyRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  if (isAuthenticated) return <Navigate to="/app/dashboard" replace />
  return <>{children}</>
}

function AuthInitializer() {
  const { isAuthenticated, setUser, logout } = useAuthStore()

  useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const { data } = await apiClient.get('/auth/me')
      setUser(data)
      return data
    },
    enabled: isAuthenticated,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

  return null
}

export default function App() {
  return (
    <>
      <AuthInitializer />
      <Routes>
        {/* Public */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<PublicOnlyRoute><LoginPage /></PublicOnlyRoute>} />
        <Route path="/register" element={<PublicOnlyRoute><RegisterPage /></PublicOnlyRoute>} />

        {/* Protected app */}
        <Route path="/app" element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
          <Route index element={<Navigate to="/app/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="repositories" element={<RepositoriesPage />} />
          <Route path="repositories/:repoId" element={<RepositoryDetailPage />} />
          <Route path="scans" element={<ScansPage />} />
          <Route path="scans/:scanId" element={<ScanDetailPage />} />
          <Route path="findings" element={<FindingsPage />} />
          <Route path="findings/:findingId" element={<FindingDetailPage />} />
          <Route path="autofix" element={<AutoFixPage />} />
          <Route path="compliance" element={<CompliancePage />} />
          <Route path="dependencies" element={<DependenciesPage />} />
          <Route path="secrets" element={<SecretsPage />} />
          <Route path="sbom" element={<SBOMPage />} />
          <Route path="audit" element={<AuditLogsPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="policies" element={<PoliciesPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="integrations" element={<IntegrationsPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="team" element={<TeamPage />} />
          <Route path="observability" element={<ObservabilityPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
