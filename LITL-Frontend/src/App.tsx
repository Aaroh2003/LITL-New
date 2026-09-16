import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { AuthProvider, ProtectedRoutes } from '@/lib/auth'
import { DocumentRoutes } from '@/lib/documents'
import LandingScreen from '@/screens/LandingScreen'
import LoginScreen from '@/screens/LoginScreen'
import SignupScreen from '@/screens/SignupScreen'
import DocumentsScreen from '@/screens/DocumentsScreen'
import UploadScreen from '@/screens/UploadScreen'
import AnalyzingScreen from '@/screens/AnalyzingScreen'
import DetectionSummaryScreen from '@/screens/DetectionSummaryScreen'
import ReviewScreen from '@/screens/ReviewScreen'
import ReportsScreen from '@/screens/ReportsScreen'
import VerificationReportScreen from '@/screens/VerificationReportScreen'
import HelpScreen from '@/screens/HelpScreen'

export function App() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0); document.title = 'LiTL — Lawyer in the Loop' }, [pathname])
  return <AuthProvider><Routes>
    <Route path="/" element={<LandingScreen />} />
    <Route path="/help" element={<HelpScreen />} />
    <Route path="/login" element={<LoginScreen />} />
    <Route path="/signup" element={<SignupScreen />} />
    <Route element={<ProtectedRoutes />}>
      <Route path="/documents" element={<DocumentsScreen />} />
      <Route path="/upload" element={<UploadScreen />} />
      <Route path="/documents/:documentId" element={<DocumentRoutes />}>
        <Route index element={<Navigate to="summary" replace />} />
        <Route path="analysis" element={<AnalyzingScreen />} />
        <Route path="summary" element={<DetectionSummaryScreen />} />
        <Route path="review/:findingId?" element={<ReviewScreen />} />
        <Route path="reports" element={<ReportsScreen />} />
        <Route path="reports/:reportId" element={<VerificationReportScreen />} />
      </Route>
    </Route>
    <Route path="*" element={<Navigate to="/documents" replace />} />
  </Routes></AuthProvider>
}
export default App
