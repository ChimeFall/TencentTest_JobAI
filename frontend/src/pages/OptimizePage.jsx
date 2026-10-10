import { useState, useEffect } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Button, MessagePlugin, Tag } from 'tdesign-react'
import { ChevronDownIcon, ChevronRightIcon } from 'tdesign-icons-react'
import { analyzeATS } from '../api'

export default function OptimizePage() {
  const navigate = useNavigate()
  const { jobId } = useParams()
  const [searchParams] = useSearchParams()

  const [atsData, setAtsData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState({})
  const [sessionId, setSessionId] = useState('')

  useEffect(() => {
    const rid = searchParams.get('resume_id') || ''
    const jid = jobId || ''
    const sid = searchParams.get('session_id') || ''
    setSessionId(sid)

    if (!rid || !jid) {
      MessagePlugin.warning('请先从匹配结果页进入')
      navigate(`/results?session_id=${sessionId}`)
      return
    }

    fetchATS(rid, jid)
  }, [])

  const fetchATS = async (rid, jid) => {
    setLoading(true)
    try {
      const res = await analyzeATS(rid, jid)
      if (res.data.code === 0) {
        setAtsData(res.data.data)
      }
    } catch (err) {
      MessagePlugin.error('ATS分析失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const toggleExpand = (id) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const copyOptimized = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      MessagePlugin.success('已复制到剪贴板')
    })
  }

  const atsScoreColor = atsData ? (
    atsData.ats_score >= 80 ? 'var(--success)' :
    atsData.ats_score >= 60 ? 'var(--sky-breeze-dark)' :
    'var(--error)'
  ) : 'var(--text-muted)'

  return (
    <div className="page-container">
      <header className="page-header">
        <div className="logo">
          
          <span>Offer 捕手 · 简历优化</span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Button
            variant="outline"
            onClick={() => navigate(`/upload?session_id=${sessionId}`)}
            style={{ color: '#39C5BB', borderColor: 'rgba(57,197,187,0.6)' }}
          >
            ← 重新上传简历
          </Button>
          <Button
            variant="outline"
            onClick={() => navigate(`/results?session_id=${sessionId}`)}
            style={{ color: '#39C5BB', borderColor: 'rgba(57,197,187,0.6)' }}
          >
            ← 重新选择岗位
          </Button>
        </div>
      </header>

      <div className="page-content">
        {loading ? (
          <div className="loading-spinner">
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, marginBottom: 12 }}>⏳</div>
              <div style={{ color: 'var(--text-muted)' }}>正在分析简历与岗位匹配度...</div>
            </div>
          </div>
        ) : atsData ? (
          <>
            {/* ATS Score */}
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="ats-score-circle">
                <div className="ats-score-value" style={{ color: atsScoreColor }}>
                  {atsData.ats_score}%
                </div>
                <div className="ats-score-label">ATS 通过率预估</div>
              </div>

              {/* Keywords */}
              <div className="keyword-section">
                <div className="keyword-group">
                  <div className="keyword-group-title">命中关键词</div>
                  <div className="keyword-tags">
                    {(atsData.keyword_hit || []).map(kw => (
                      <span key={kw} className="keyword-tag hit">{kw}</span>
                    ))}
                  </div>
                </div>
                <div className="keyword-group">
                  <div className="keyword-group-title">缺失关键词</div>
                  <div className="keyword-tags">
                    {(atsData.keyword_miss || []).map(kw => (
                      <span key={kw} className="keyword-tag miss">{kw}</span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Format Issues */}
              {atsData.format_issues?.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <div className="card-title">格式问题</div>
                  {atsData.format_issues.map((issue, i) => (
                    <Tag key={i} theme="warning" variant="light" style={{ marginRight: 8, marginBottom: 8 }}>
                      {issue}
                    </Tag>
                  ))}
                </div>
              )}
            </div>

            {/* Suggestions */}
            <div className="card">
              <div className="card-title">优化建议</div>
              <div className="suggestion-list">
                {(atsData.suggestions || []).map(sug => (
                  <div key={sug.id} className="suggestion-item fade-in">
                    <div
                      className="suggestion-header"
                      onClick={() => toggleExpand(sug.id)}
                    >
                      <div>
                        <div className="suggestion-location">{sug.location}</div>
                        <div className="suggestion-issue">#{sug.id} {sug.issue}</div>
                      </div>
                      {expanded[sug.id] ? <ChevronDownIcon /> : <ChevronRightIcon />}
                    </div>

                    {expanded[sug.id] && (
                      <div className="suggestion-body">
                        <div className="suggestion-advice">{sug.advice}</div>

                        <div>
                          <div className="compare-label" style={{ color: 'var(--error)' }}>原文：</div>
                          <div className="compare-block original">
                            {sug.original}
                          </div>
                        </div>

                        <div>
                          <div className="compare-label" style={{ color: 'var(--success)' }}>优化后：</div>
                          <div className="compare-block optimized">
                            {sug.optimized}
                          </div>
                        </div>

                        <Button
                          size="small"
                          variant="outline"
                          onClick={() => copyOptimized(sug.optimized)}
                          style={{ alignSelf: 'flex-start', borderRadius: 6 }}
                        >
                          复制优化文本
                        </Button>
                      </div>
                    )}
                  </div>
                ))}

                {(!atsData.suggestions || atsData.suggestions.length === 0) && (
                  <div className="empty-state">
                    <div>暂无优化建议</div>
                  </div>
                )}
              </div>

            </div>
          </>
        ) : (
          <div className="card">
            <div className="empty-state">
              <div>暂无分析数据</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
