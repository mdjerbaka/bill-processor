import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import SetupWizard from './pages/SetupWizard'
import DashboardPage from './pages/DashboardPage'
import InvoiceListPage from './pages/InvoiceListPage'
import InvoiceDetailPage from './pages/InvoiceDetailPage'
import PayablesPage from './pages/PayablesPage'
import PaymentsOutPage from './pages/PaymentsOutPage'
import BillsPage from './pages/BillsPage'
import ReceivablesPage from './pages/ReceivablesPage'
import JobsPage from './pages/JobsPage'
import SettingsPage from './pages/SettingsPage'
import JunkBinPage from './pages/JunkBinPage'
import HelpPage from './pages/HelpPage'

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return children
}

function AppRoutes() {
  const { isSetup, setupStatus, isAuthenticated, connectionError } = useAuth()

  // Still checking setup status
  if (isSetup === null) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-950">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        <p className="ml-4 text-gray-400">Connecting to server...</p>
      </div>
    )
  }

  // Needs first-time setup — but always allow /login as an escape hatch
  if (setupStatus && !setupStatus.has_user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<SetupWizard />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupWizard />} />
      <Route path="/" element={
        <ProtectedRoute>
          <Layout />
        </ProtectedRoute>
      }>
        <Route index element={<DashboardPage />} />
        <Route path="invoices" element={<InvoiceListPage />} />
        <Route path="invoices/:id" element={<InvoiceDetailPage />} />
        <Route path="payables" element={<PayablesPage />} />
        <Route path="payments-out" element={<PaymentsOutPage />} />
        <Route path="bills" element={<BillsPage />} />
        <Route path="receivables" element={<ReceivablesPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="junk" element={<JunkBinPage />} />
        <Route path="help" element={<HelpPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
