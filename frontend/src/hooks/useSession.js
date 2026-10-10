import { useState, useEffect, useCallback } from 'react'
import { verifySession, getSessionState, getResumePreview } from '../api'

/**
 * Hook to manage session via httpOnly cookie.
 * Returns session info without exposing session_id in URL.
 */
export function useSession() {
  const [sessionId, setSessionId] = useState('')
  const [resumeId, setResumeId] = useState('')
  const [stage, setStage] = useState('')
  const [ready, setReady] = useState(false)
  const [hasSession, setHasSession] = useState(false)

  // Try to restore session from cookie on mount
  useEffect(() => {
    restoreFromCookie()
  }, [])

  const restoreFromCookie = async () => {
    try {
      const res = await verifySession()
      if (res.data.code === 0) {
        const d = res.data.data
        setSessionId(d.session_id)
        setResumeId(d.resume_id)
        setStage(d.stage)
        setHasSession(true)
      }
    } catch (err) {
      // No active session — user needs to upload resume
      setHasSession(false)
    } finally {
      setReady(true)
    }
  }

  const getState = useCallback(async () => {
    try {
      const res = await getSessionState()
      return res.data.data
    } catch (err) {
      return null
    }
  }, [])

  const getPreview = useCallback(async () => {
    try {
      const res = await getResumePreview()
      if (res.data.code === 0) return res.data.data
      return null
    } catch (err) {
      return null
    }
  }, [])

  return {
    sessionId,
    resumeId,
    stage,
    ready,
    hasSession,
    getState,
    getPreview,
    setSessionId,
    setResumeId,
    setStage,
    setHasSession,
  }
}
