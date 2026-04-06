import { Routes, Route, Navigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '@/store/auth.store'
import { useEffect } from 'react'
import MainLayout from '@/layouts/MainLayout'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import CampaignsPage from '@/pages/CampaignsPage'
import CampaignNewPage from '@/pages/CampaignNewPage'
import CampaignDetailPage from '@/pages/CampaignDetailPage'
import CampaignEditPage from '@/pages/CampaignEditPage'
import PublicationNewPage from '@/pages/PublicationNewPage'
import PublicationDetailPage from '@/pages/PublicationDetailPage'
import PublicationEditPage from '@/pages/PublicationEditPage'
import GeneticPage from '@/pages/GeneticPage'
import ProfilePage from '@/pages/ProfilePage'
import MetaConnectPage from '@/pages/MetaConnectPage'
import { ConfirmDialog } from '@/components/ConfirmDialog'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, token } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

function IndexRedirect() {
  const [searchParams] = useSearchParams()
  if (searchParams.get("oauth")) {
    return <Navigate to={`/settings/meta-connect?${searchParams.toString()}`} replace />
  }
  return <Navigate to="/dashboard" replace />
}

export default function App() {
  const { loadUser, token } = useAuthStore()

  useEffect(() => {
    if (token) loadUser()
  }, [token, loadUser])

  return (
    <>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
          <Route index element={<IndexRedirect />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="campaigns" element={<CampaignsPage />} />
          <Route path="campaigns/new" element={<CampaignNewPage />} />
          <Route path="campaigns/:campaignId" element={<CampaignDetailPage />} />
          <Route path="campaigns/:campaignId/edit" element={<CampaignEditPage />} />
          <Route path="publications/new/:campaignId" element={<PublicationNewPage />} />
          <Route path="publications/:publicationId" element={<PublicationDetailPage />} />
          <Route path="publications/:publicationId/edit" element={<PublicationEditPage />} />
          <Route path="genetic" element={<GeneticPage />} />
          <Route path="settings/meta-connect" element={<MetaConnectPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
      </Routes>
      <ConfirmDialog />
    </>
  )
}
