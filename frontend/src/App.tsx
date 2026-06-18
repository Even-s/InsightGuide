import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import DocumentUploadPage from './routes/DocumentUploadPage'
import EditorPage from './routes/EditorPage'
import PresenterPage from './routes/PresenterPage'
import InterviewReportPage from './routes/InterviewReportPage'
import PrepSessionListPage from './routes/PrepSessionListPage'
import BRDGenerationPage from './routes/BRDGenerationPage'
import PromptsPage from './routes/PromptsPage'
import SessionLogPage from './routes/SessionLogPage'
import ProjectListPage from './routes/ProjectListPage'
import ProjectDetailPage from './routes/ProjectDetailPage'
import ProjectSessionsPage from './routes/ProjectSessionsPage'
import InsightMemoPage from './routes/InsightMemoPage'
import EvidenceMatrixPage from './routes/EvidenceMatrixPage'
import BRDReadinessPage from './routes/BRDReadinessPage'

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-cream-100">
        <Routes>
          <Route path="/" element={<DocumentUploadPage />} />
          <Route path="/projects" element={<ProjectListPage />} />
          <Route path="/projects/manage" element={<ProjectSessionsPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/projects/:projectId/evidence-matrix" element={<EvidenceMatrixPage />} />
          <Route path="/projects/:projectId/readiness" element={<BRDReadinessPage />} />
          <Route path="/prep-sessions" element={<PrepSessionListPage />} />
          <Route path="/editor/:deckId" element={<EditorPage />} />
          <Route path="/interview/:deckId" element={<PresenterPage />} />
          <Route path="/interview/:deckId/report/:sessionId" element={<InterviewReportPage />} />
          <Route path="/interview/:sessionId/brd" element={<BRDGenerationPage />} />
          <Route path="/sessions/:sessionId/insight-memo" element={<InsightMemoPage />} />
          <Route path="/sessions/:sessionId/log" element={<SessionLogPage />} />
          <Route path="/prompts" element={<PromptsPage />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
