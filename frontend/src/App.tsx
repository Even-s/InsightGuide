import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import DeckUploadPage from './routes/DeckUploadPage'
import EditorPage from './routes/EditorPage'
import PresenterPage from './routes/PresenterPage'
import SessionListPage from './routes/SessionListPage'
import PrepSessionListPage from './routes/PrepSessionListPage'
import BRDGenerationPage from './routes/BRDGenerationPage'

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-cream-100">
        <Routes>
          {/* Main routes */}
          <Route path="/" element={<DeckUploadPage />} />
          <Route path="/sessions" element={<SessionListPage />} />
          <Route path="/prep-sessions" element={<PrepSessionListPage />} />
          <Route path="/editor/:deckId" element={<EditorPage />} />
          <Route path="/presenter/:deckId" element={<PresenterPage />} />
          <Route path="/interview/:deckId" element={<PresenterPage />} />
          <Route path="/interview/:sessionId/brd" element={<BRDGenerationPage />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
