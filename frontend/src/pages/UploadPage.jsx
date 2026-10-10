import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Progress, MessagePlugin } from 'tdesign-react'
import { CloudUploadIcon } from 'tdesign-icons-react'
import { uploadResume, initChat, createSession, getResumePreview } from '../api'
import '../App.css'

export default function UploadPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [parsedData, setParsedData] = useState(null)
  const [previewHtml, setPreviewHtml] = useState('')
  const [resumeId, setResumeId] = useState(null)
  const [restoring, setRestoring] = useState(false)
  const [hasSession, setHasSession] = useState(false)

  // Try to restore resume from cookie session
  useEffect(() => {
    restoreFromCookie()
  }, [])

  const restoreFromCookie = async () => {
    setRestoring(true)
    try {
      const res = await getResumePreview()
      const data = res?.data?.data
      if (data) {
        setParsedData(data.parsed)
        setPreviewHtml(data.preview_html)
        setResumeId(data.resume_id)
        setFile({ name: '已上传的简历.pdf' })
        setHasSession(true)
      }
    } catch (err) {
      // No session — normal
    } finally {
      setRestoring(false)
    }
  }

  const handleFileSelect = (e) => {
    const f = e.target.files?.[0]
    if (f) processFile(f)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const f = e.dataTransfer.files?.[0]
    if (f) processFile(f)
  }

  const processFile = async (f) => {
    if (!f.name.endsWith('.pdf')) {
      MessagePlugin.warning('仅支持PDF格式文件')
      return
    }
    setFile(f)
    setUploading(true)
    setProgress(30)

    try {
      const res = await uploadResume(f)
      setProgress(100)
      if (res.data.code === 0) {
        const data = res.data.data
        setParsedData(data.parsed)
        setPreviewHtml(data.preview_html)
        setResumeId(data.resume_id)
        MessagePlugin.success('简历解析成功！')
      } else {
        MessagePlugin.error('简历解析失败，请重试')
      }
    } catch (err) {
      MessagePlugin.error('上传失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setUploading(false)
    }
  }

  const handleStartMatch = async () => {
    if (!resumeId) return
    try {
      const res = await initChat(resumeId)
      if (res.data.code === 0) {
        const { session_id, profile } = res.data.data
        // Create cookie session + also pass session_id via URL as fallback
        await createSession(session_id, resumeId, profile || {}, 'S2')
        navigate(`/chat?sid=${session_id}`)
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message
      if (detail === '简历不存在') {
        MessagePlugin.warning('简历已过期，请重新上传')
        setResumeId(null)
        setParsedData(null)
        setPreviewHtml('')
        setFile(null)
        setHasSession(false)
      } else {
        MessagePlugin.error('初始化对话失败: ' + detail)
      }
    }
  }

  return (
    <div className="page-container">
      <header className="page-header">
        <div className="logo">
          <span>Offer 捕手 · 学生求职匹配智能体</span>
        </div>
      </header>

      <div className="page-content">
        <div className="split-layout">
          {/* Left: Upload Zone */}
          <div className="split-left">
            <div className="card" style={{ flex: 1 }}>
              <div className="card-title">上传简历</div>

              {restoring ? (
                <div style={{ textAlign: 'center', padding: 40 }}>
                  <div style={{ fontSize: 24, marginBottom: 12 }}>⏳</div>
                  <div style={{ color: 'var(--text-muted)' }}>正在恢复简历...</div>
                </div>
              ) : (
                <>
                  <div
                    className={`upload-zone ${uploading ? 'active' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDrop={handleDrop}
                    onDragOver={(e) => e.preventDefault()}
                  >
                    <CloudUploadIcon size="48px" style={{ color: 'var(--sky-breeze)' }} />
                    <div className="upload-text">
                      {file ? file.name : '点击或拖拽PDF简历到此处'}
                    </div>
                    <div className="upload-hint">支持 .pdf 格式，最大 10MB</div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf"
                      style={{ display: 'none' }}
                      onChange={handleFileSelect}
                    />
                  </div>

                  {uploading && (
                    <div style={{ marginTop: 16 }}>
                      <Progress
                        percentage={progress}
                        label={progress < 100 ? '解析中...' : '解析完成'}
                        theme={progress < 100 ? 'primary' : 'success'}
                      />
                    </div>
                  )}

                  <div className="privacy-notice">
                    <span>PDF在本地解析，文本不上传第三方</span>
                  </div>

                  <div style={{ marginTop: 20, textAlign: 'center' }}>
                    <Button
                      theme="primary"
                      size="large"
                      disabled={!resumeId}
                      onClick={handleStartMatch}
                      style={{
                        background: !resumeId ? '#ccc' : 'var(--sky-breeze)',
                        borderColor: !resumeId ? '#ccc' : 'var(--sky-breeze)',
                        color: 'white',
                        fontSize: 16,
                        fontWeight: 600,
                        padding: '12px 48px',
                        borderRadius: 10,
                      }}
                    >
                      {hasSession ? '继续匹配' : '开始匹配'}
                    </Button>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Right: Resume Preview */}
          <div className="split-right">
            <div className="card" style={{ flex: 1, overflow: 'auto' }}>
              <div className="card-title">简历预览</div>
              {previewHtml ? (
                <div
                  className="resume-preview fade-in"
                  dangerouslySetInnerHTML={{ __html: previewHtml }}
                />
              ) : (
                <div className="empty-state">
                  <div>上传简历后将在此处显示结构化预览</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
