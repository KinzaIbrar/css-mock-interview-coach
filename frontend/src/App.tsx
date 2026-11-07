import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { FocusLayout } from '@/components/layout/FocusLayout'
import { PageLoader } from '@/components/ui/Feedback'
import { ProtectedRoute, PublicOnlyRoute } from '@/routes/guards'

// Route-level code splitting keeps the first load small (the charting library only loads with the dashboard/results).
const Login = lazy(() => import('@/pages/Login'))
const Register = lazy(() => import('@/pages/Register'))
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const InterviewSetup = lazy(() => import('@/pages/InterviewSetup'))
const InterviewRoom = lazy(() => import('@/pages/InterviewRoom'))
const InterviewResults = lazy(() => import('@/pages/InterviewResults'))
const InterviewHistory = lazy(() => import('@/pages/InterviewHistory'))
const QuestionBank = lazy(() => import('@/pages/QuestionBank'))
const Profile = lazy(() => import('@/pages/Profile'))
const NotFound = lazy(() => import('@/pages/NotFound'))

export default function App() {
  return (
    <Suspense fallback={<div className="min-h-screen"><PageLoader /></div>}>
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          {/* The interview room has its own distraction-free layout (no sidebar). */}
          <Route element={<FocusLayout />}>
            <Route path="/interviews/:id" element={<InterviewRoom />} />
          </Route>
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/interviews/new" element={<InterviewSetup />} />
            <Route path="/interviews/:id/results" element={<InterviewResults />} />
            <Route path="/history" element={<InterviewHistory />} />
            <Route path="/questions" element={<QuestionBank />} />
            <Route path="/profile" element={<Profile />} />
          </Route>
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}
