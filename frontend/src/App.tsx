import { lazy, Suspense } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import LoadingSpinner from './components/common/LoadingSpinner'

const DocumentUploadPage = lazy(() => import('./routes/DocumentUploadPage'))
const EditorPage = lazy(() => import('./routes/EditorPage'))
const PresenterPage = lazy(() => import('./routes/PresenterPage'))
const InterviewReportPage = lazy(() => import('./routes/InterviewReportPage'))
const PrepSessionListPage = lazy(() => import('./routes/PrepSessionListPage'))
const BRDGenerationPage = lazy(() => import('./routes/BRDGenerationPage'))
const SessionLogPage = lazy(() => import('./routes/SessionLogPage'))
const ProjectDetailPage = lazy(() => import('./routes/ProjectDetailPage'))
const ProjectSessionsPage = lazy(() => import('./routes/ProjectSessionsPage'))
const InsightMemoPage = lazy(() => import('./routes/InsightMemoPage'))
const EvidenceMatrixPage = lazy(() => import('./routes/EvidenceMatrixPage'))
const BRDReadinessPage = lazy(() => import('./routes/BRDReadinessPage'))

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-cream-100">
        <Suspense fallback={<LoadingSpinner label="載入中..." />}>
          <Routes>
            <Route path="/" element={<DocumentUploadPage />} />
            <Route path="/projects" element={<ProjectSessionsPage />} />
            <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
            <Route path="/projects/:projectId/evidence-matrix" element={<EvidenceMatrixPage />} />
            <Route path="/projects/:projectId/readiness" element={<BRDReadinessPage />} />
            <Route path="/prep-sessions" element={<PrepSessionListPage />} />
            <Route path="/editor/:documentId" element={<EditorPage />} />
            <Route path="/interview/:documentId" element={<PresenterPage />} />
            <Route path="/interview/session/:sessionId" element={<PresenterPage />} />
            <Route path="/interview/:documentId/report/:sessionId" element={<InterviewReportPage />} />
            <Route path="/interview/:sessionId/brd" element={<BRDGenerationPage />} />
            <Route path="/sessions/:sessionId/insight-memo" element={<InsightMemoPage />} />
            <Route path="/sessions/:sessionId/log" element={<SessionLogPage />} />
          </Routes>
        </Suspense>
      </div>
    </Router>
  )
}

export default App
