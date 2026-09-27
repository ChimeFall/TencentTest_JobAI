import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || ''

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  withCredentials: true,  // Send cookies with every request
})

// Resume
export const uploadResume = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/api/resume/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// Session management (cookie-based)
export const createSession = (sessionId, resumeId, profile = {}, stage = 'S2') => {
  return api.post('/api/session/create', {
    session_id: sessionId,
    resume_id: resumeId,
    profile,
    stage,
  })
}

export const verifySession = () => {
  return api.post('/api/session/verify')
}

export const getSessionState = () => {
  return api.get('/api/session/state')
}

export const getResumePreview = () => {
  return api.get('/api/session/preview')
}

// Chat
export const initChat = (resumeId) => {
  return api.post('/api/chat/init', { resume_id: resumeId })
}

export const sendMessage = (sessionId, currentStage, payload) => {
  return api.post('/api/chat/message', {
    session_id: sessionId,
    current_stage: currentStage,
    payload,
  })
}

// Jobs
export const matchJobs = (sessionId, keywords = [], limit = 10, page = 1) => {
  return api.post('/api/jobs/match', {
    session_id: sessionId,
    keywords,
    limit,
    page,
  })
}

// ATS
export const analyzeATS = (resumeId, jobId) => {
  return api.post('/api/ats/analyze', {
    resume_id: resumeId,
    job_id: jobId,
  })
}

// Legacy state recovery (kept for backward compat)
export const getChatState = (sessionId) => {
  return api.get(`/api/chat/state/${sessionId}`)
}

export default api
