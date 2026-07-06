import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import LoginPage from './pages/auth/LoginPage';
import RegisterPage from './pages/auth/RegisterPage';
import PatientDashboard from './pages/patient/PatientDashboard';
import ExerciseSelectionPage from './pages/patient/ExerciseSelectionPage';
import CameraValidationPage from './pages/patient/CameraValidationPage';
import LiveSessionPage from './pages/patient/LiveSessionPage';
import SessionSummaryPage from './pages/patient/SessionSummaryPage';
import UploadSessionPage from './pages/patient/UploadSessionPage';
import AllSessionsPage from './pages/patient/AllSessionsPage';
import AnalyticsPage from './pages/patient/AnalyticsPage';
import ReportsPage from './pages/patient/ReportsPage';
import TherapistDashboard from './pages/therapist/TherapistDashboard';
import PatientDetailPage from './pages/therapist/PatientDetailPage';
import { useAuthStore } from './stores/authStore';

// Root route component that redirects based on role
function RootRedirect() {
  const { user, isAuthenticated } = useAuthStore();

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (user.role === 'therapist') {
    return <Navigate to="/therapist/dashboard" replace />;
  }

  return <PatientDashboard />;
}

export default function App() {
  return (
    <Router>
      <Routes>
        {/* Public Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected Routes Wrapper under Layout */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          {/* Patient / Shared Routes */}
          <Route index element={<RootRedirect />} />
          <Route path="dashboard" element={<RootRedirect />} />
          <Route path="sessions" element={<AllSessionsPage />} />
          <Route path="exercises" element={<ExerciseSelectionPage />} />
          <Route path="camera/:exerciseId/:sessionId" element={<CameraValidationPage />} />
          <Route path="session/live/:sessionId/:exerciseId" element={<LiveSessionPage />} />
          <Route path="session/summary/:sessionId" element={<SessionSummaryPage />} />
          <Route path="session/upload/:sessionId/:exerciseId" element={<UploadSessionPage />} />
          <Route path="progress" element={<AnalyticsPage />} />
          <Route path="reports" element={<ReportsPage />} />

          {/* Therapist-Only Routes */}
          <Route
            path="therapist/dashboard"
            element={
              <ProtectedRoute allowedRoles={['therapist', 'admin']}>
                <TherapistDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="therapist/patient/:patientId"
            element={
              <ProtectedRoute allowedRoles={['therapist', 'admin']}>
                <PatientDetailPage />
              </ProtectedRoute>
            }
          />
        </Route>

        {/* Fallback route */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}
