import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import ChatPage from './pages/ChatPage'
import ResultsPage from './pages/ResultsPage'
import OptimizePage from './pages/OptimizePage'
import './App.css'

function App() {
  return (
    <Router>
      <div className="app-container">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/optimize/:jobId" element={<OptimizePage />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
