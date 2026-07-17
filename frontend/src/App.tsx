import { lazy, Suspense } from 'react'
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom'
import LoadingSpinner from './components/common/LoadingSpinner'

const DocumentUploadPage = lazy(() => import('./routes/DocumentUploadPage'))
const HomePage = lazy(() => import('./routes/HomePage'))
const EditorPage = lazy(() => import('./routes/EditorPage'))
const PresenterPage = lazy(() => import('./routes/PresenterPage'))
const PrepSessionListPage = lazy(() => import('./routes/PrepSessionListPage'))
const SessionLogPage = lazy(() => import('./routes/SessionLogPage'))
const ProjectDetailPage = lazy(() => import('./routes/ProjectDetailPage'))
const ProjectSessionsPage = lazy(() => import('./routes/ProjectSessionsPage'))
const InsightMemoPage = lazy(() => import('./routes/InsightMemoPage'))
const EvidenceMatrixPage = lazy(() => import('./routes/EvidenceMatrixPage'))
const BRDReadinessPage = lazy(() => import('./routes/BRDReadinessPage'))

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <div key={location.pathname} className="motion-fade-in">
      <Routes location={location}>
        <Route path="/" element={<HomePage />} />
        <Route path="/projects/new" element={<DocumentUploadPage />} />
        <Route path="/projects" element={<ProjectSessionsPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="/projects/:projectId/evidence-matrix" element={<EvidenceMatrixPage />} />
        <Route path="/projects/:projectId/readiness" element={<BRDReadinessPage />} />
        <Route path="/prep-sessions" element={<PrepSessionListPage />} />
        <Route path="/editor/:documentId" element={<EditorPage />} />
        <Route path="/interview/:documentId" element={<PresenterPage />} />
        <Route path="/interview/session/:sessionId" element={<PresenterPage />} />
        <Route path="/sessions/:sessionId/insight-memo" element={<InsightMemoPage />} />
        <Route path="/sessions/:sessionId/log" element={<SessionLogPage />} />
      </Routes>
    </div>
  )
}

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-cream-100">
        <Suspense fallback={<LoadingSpinner label="載入中..." />}>
          <AnimatedRoutes />
        </Suspense>
      </div>
    </Router>
  )
}

export default App
