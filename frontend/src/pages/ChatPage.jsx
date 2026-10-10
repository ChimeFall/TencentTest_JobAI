import React, { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Button, Input, Select, MessagePlugin } from 'tdesign-react'
import { ChevronDownIcon, ChevronRightIcon } from 'tdesign-icons-react'
import { sendMessage, matchJobs, getSessionState, createSession } from '../api'

const RANK_WEIGHTS = {
  0: 0.30, 1: 0.25, 2: 0.20, 3: 0.15, 4: 0.07, 5: 0.03,
}

export default function ChatPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const chatRef = useRef(null)

  const [sessionId, setSessionId] = useState('')
  const [resumeId, setResumeId] = useState('')
  const [stage, setStage] = useState('S2')
  const [messages, setMessages] = useState([])
  const [components, setComponents] = useState([])
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [restoring, setRestoring] = useState(true)

  // Interactive states
  const [sortOrder, setSortOrder] = useState(['技能', '行业', '薪资', '地域', '成长', '兴趣'])
  const [dragIdx, setDragIdx] = useState(null)
  const [selectedCities, setSelectedCities] = useState([])
  const [selectedIndustries, setSelectedIndustries] = useState([])
  const [salaryMin, setSalaryMin] = useState(4)
  const [salaryMax, setSalaryMax] = useState(8)
  const [extraText, setExtraText] = useState('')

  // Restore state from cookie or URL param
  useEffect(() => {
    const sid = searchParams.get('sid')
    const restart = searchParams.get('restart')
    if (sid) {
      // Fresh session from upload — use sid directly, skip cookie check
      setSessionId(sid)
      setStage('S2')
      setComponents([{ type: 'drag_sort', options: ['技能', '行业', '薪资', '地域', '成长', '兴趣'] }])
      setRestoring(false)
      return
    }
    if (restart === '1') {
      // Restart from S2
      restoreFromCookie(true)
    } else {
      restoreFromCookie(false)
    }
  }, [])

  const restoreFromCookie = async (forceRestart) => {
    setRestoring(true)
    try {
      const res = await getSessionState()
      const data = res?.data?.data
      if (data && !forceRestart) {
        setSessionId(data.session_id)
        setResumeId(data.resume_id)
        setStage(data.stage)
        setProfile(data.profile)

        const msgs = (data.messages || []).map(m => ({
          role: m.role,
          content: m.content,
        }))
        setMessages(msgs)

        if (data.profile) {
          const p = data.profile
          if (p.weight_order?.length) setSortOrder(p.weight_order)
          if (p.preferences?.cities?.length) setSelectedCities(p.preferences.cities)
          if (p.preferences?.industries?.length) setSelectedIndustries(p.preferences.industries)
          if (p.preferences?.salary_min) setSalaryMin(p.preferences.salary_min)
          if (p.preferences?.salary_max) setSalaryMax(p.preferences.salary_max)
          if (p.preferences?.extra_interests) setExtraText(p.preferences.extra_interests)
        }

        setComponents(data.components || [])
        setRestoring(false)
        return
      }
      // restart 时保留原 session_id，只重置 stage 到 S2
      if (data && forceRestart) {
        setSessionId(data.session_id)
        setResumeId(data.resume_id)
        setStage('S2')
        // 重置偏好到默认值，让用户重新选择
        setSortOrder(['技能', '行业', '薪资', '地域', '成长', '兴趣'])
        setSelectedCities([])
        setSelectedIndustries([])
        setSalaryMin(4)
        setSalaryMax(8)
        setExtraText('')
        setProfile(null)
        setMessages([])
        setComponents([{ type: 'drag_sort', options: ['技能', '行业', '薪资', '地域', '成长', '兴趣'] }])
        setRestoring(false)
        return
      }
    } catch (err) {
      // No session
    }

    // New — show drag_sort
    setSessionId('')
    setStage('S2')
    setComponents([{ type: 'drag_sort', options: ['技能', '行业', '薪资', '地域', '成长', '兴趣'] }])
    setRestoring(false)
  }

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight
    }
  }, [messages])

  // Drag sort handlers
  const handleDragStart = (idx) => setDragIdx(idx)
  const handleDragOver = (e) => e.preventDefault()
  const handleDrop = (idx) => {
    if (dragIdx === null || dragIdx === idx) return
    const newOrder = [...sortOrder]
    const [removed] = newOrder.splice(dragIdx, 1)
    newOrder.splice(idx, 0, removed)
    setSortOrder(newOrder)
    setDragIdx(null)
  }

  const handleApiError = (err, action) => {
    const detail = err.response?.data?.detail || err.message
    if (detail === '会话不存在' || detail === '简历不存在') {
      MessagePlugin.warning('会话已过期，请重新上传简历')
      navigate('/upload')
      return true
    }
    MessagePlugin.error(action + '失败: ' + detail)
    return false
  }

  const handleSortSubmit = async () => {
    setLoading(true)
    const userMsg = `我的排序：${sortOrder.join(' > ')}`
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])

    try {
      const res = await sendMessage(sessionId, stage, { weight_order: sortOrder })
      const data = res.data.data
      const newSessionId = data.session_id || sessionId
      setSessionId(newSessionId)
      setMessages(prev => [...prev, { role: 'system', content: data.reply }])
      setStage(data.next_stage)
      setComponents(data.components || [])
      if (data.updated_profile) {
        setProfile(data.updated_profile)
        // Create/update cookie session — 用 newSessionId（闭包中最新值）
        await createSession(newSessionId, resumeId, data.updated_profile, data.next_stage)
      }
    } catch (err) {
      if (handleApiError(err, '发送')) return
    } finally {
      setLoading(false)
    }
  }

  const handlePrefsSubmit = async () => {
    setLoading(true)
    const payload = {
      cities: selectedCities,
      salary_min: salaryMin,
      salary_max: salaryMax,
      salary_range: `${salaryMin}k-${salaryMax >= 15 ? '15k以上' : `${salaryMax}k`}`,
      industries: selectedIndustries,
    }
    const summary = `期望城市: ${selectedCities.join('、')}, 薪资: ${payload.salary_range}, 行业: ${selectedIndustries.join('、')}`
    setMessages(prev => [...prev, { role: 'user', content: summary }])

    try {
      const res = await sendMessage(sessionId, stage, payload)
      const data = res.data.data
      setMessages(prev => [...prev, { role: 'system', content: data.reply }])
      setStage(data.next_stage)
      setComponents(data.components || [])
      if (data.updated_profile) {
        setProfile(data.updated_profile)
        await createSession(sessionId, resumeId, data.updated_profile, data.next_stage)
      }
    } catch (err) {
      if (handleApiError(err, '发送')) return
    } finally {
      setLoading(false)
    }
  }

  const handleExtraSubmit = async (skip = false) => {
    setLoading(true)
    const text = skip ? '暂无补充' : extraText.trim()
    setMessages(prev => [...prev, { role: 'user', content: text || '暂无补充' }])

    try {
      const res = await sendMessage(sessionId, stage, { extra_interests: text || '' })
      const data = res.data.data
      setMessages(prev => [...prev, { role: 'system', content: data.reply }])
      setStage(data.next_stage)
      setComponents(data.components || [])
      if (data.updated_profile) {
        setProfile(data.updated_profile)
        await createSession(sessionId, resumeId, data.updated_profile, data.next_stage)
      }
    } catch (err) {
      if (handleApiError(err, '发送')) return
    } finally {
      setLoading(false)
    }
  }

  const handleViewResults = async () => {
    try {
      await matchJobs(sessionId, [], 10)
      navigate(`/results?session_id=${sessionId}`)
    } catch (err) {
      if (handleApiError(err, '匹配')) return
    }
  }

  // Render component
  const renderComponent = (comp) => {
    switch (comp.type) {
      case 'drag_sort':
        return (
          <div className="drag-sort-list">
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>
              拖拽排序（上面最重要），排好后点击确认
            </div>
            {sortOrder.map((dim, idx) => (
              <div
                key={dim}
                className="drag-sort-item"
                draggable
                onDragStart={() => handleDragStart(idx)}
                onDragOver={handleDragOver}
                onDrop={() => handleDrop(idx)}
              >
                <span className="rank">{idx + 1}</span>
                <span className="dim-name">{dim}</span>
                <span className="weight">权重: {(RANK_WEIGHTS[idx] * 100).toFixed(0)}%</span>
              </div>
            ))}
            <div style={{ marginTop: 12 }}>
              <Button
                theme="primary"
                onClick={handleSortSubmit}
                loading={loading}
                style={{ background: 'var(--sky-breeze)', borderColor: 'var(--sky-breeze)', borderRadius: 8 }}
              >
                确认排序
              </Button>
            </div>
          </div>
        )

      case 'multi_select':
        const isCity = comp.key === 'cities'
        const options = comp.options || []
        const selected = isCity ? selectedCities : selectedIndustries
        const setSelected = isCity ? setSelectedCities : setSelectedIndustries

        return (
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 8 }}>{comp.label}</div>
            <div className="multi-select-group">
              {options.map(opt => (
                <div
                  key={opt}
                  className={`select-chip ${selected.includes(opt) ? 'selected' : ''}`}
                  onClick={() => {
                    if (selected.includes(opt)) {
                      setSelected(selected.filter(s => s !== opt))
                    } else {
                      setSelected([...selected, opt])
                    }
                  }}
                >
                  {opt}
                </div>
              ))}
            </div>
            {comp.key === 'industries' && (
              <div style={{ marginTop: 12 }}>
                <Button
                  theme="primary"
                  onClick={handlePrefsSubmit}
                  loading={loading}
                  disabled={selectedCities.length === 0 || selectedIndustries.length === 0}
                  style={{ background: 'var(--sky-breeze)', borderColor: 'var(--sky-breeze)', borderRadius: 8 }}
                >
                  确认选择
                </Button>
              </div>
            )}
          </div>
        )

      case 'slider':
        const minOptions = [2, 3, 4, 5, 6, 7, 8]
        const maxOptions = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        return (
          <div className="slider-container">
            <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 12 }}>{comp.label}</div>
            <div style={{ display: 'flex', gap: 20, alignItems: 'center', marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>最低薪资</div>
                <Select
                  value={salaryMin}
                  onChange={(val) => {
                    setSalaryMin(val)
                    if (val >= salaryMax) setSalaryMax(Math.min(val + 1, 15))
                  }}
                  options={minOptions.map(v => ({ label: `${v}k`, value: v }))}
                  style={{ width: '100%' }}
                />
              </div>
              <span style={{ color: 'var(--text-muted)', marginTop: 18 }}>—</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>最高薪资</div>
                <Select
                  value={salaryMax}
                  onChange={(val) => {
                    setSalaryMax(val)
                    if (val <= salaryMin) setSalaryMin(Math.max(val - 1, 2))
                  }}
                  options={[
                    ...maxOptions.map(v => ({ label: `${v}k`, value: v })),
                    { label: '15k以上', value: 15 },
                  ]}
                  style={{ width: '100%' }}
                />
              </div>
            </div>
            <div style={{ textAlign: 'center', fontSize: 15, fontWeight: 600, color: 'var(--sky-breeze-dark)', marginBottom: 4 }}>
              {salaryMin}k — {salaryMax >= 15 ? '15k以上' : `${salaryMax}k`} /月
            </div>
          </div>
        )

      case 'text_input':
        return (
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 8 }}>{comp.label}</div>
            <Input
              value={extraText}
              onChange={(val) => setExtraText(val)}
              placeholder={comp.placeholder}
              style={{ marginBottom: 12 }}
            />
            <div style={{ display: 'flex', gap: 10 }}>
              <Button
                theme="primary"
                onClick={() => handleExtraSubmit(false)}
                loading={loading}
                disabled={!extraText.trim()}
                style={{ background: 'var(--sky-breeze)', borderColor: 'var(--sky-breeze)', borderRadius: 8 }}
              >
                确认提交
              </Button>
              <Button
                variant="outline"
                onClick={() => handleExtraSubmit(true)}
                loading={loading}
                style={{ borderRadius: 8 }}
              >
                无需补充，直接确认
              </Button>
            </div>
          </div>
        )

      default:
        return null
    }
  }

  const profileSummary = profile ? {
    weightOrder: profile.weight_order || [],
    cities: profile.preferences?.cities || [],
    salary: profile.preferences?.salary_range || '',
    industries: profile.preferences?.industries || [],
    extra: profile.preferences?.extra_interests || '',
  } : null

  if (restoring) {
    return (
      <div className="page-container">
        <header className="page-header">
          <div className="logo"><span>Offer 捕手 · 求职偏好采集</span></div>
        </header>
        <div className="page-content" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 24, marginBottom: 12, color: 'var(--text-muted)' }}>…</div>
            <div style={{ color: 'var(--text-muted)' }}>正在恢复会话...</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="page-container">
      <header className="page-header">
        <div className="logo">
          
          <span>Offer 捕手 · 求职偏好采集</span>
        </div>
        <Button
          variant="outline"
          onClick={() => navigate('/upload')}
          style={{ color: '#39C5BB', borderColor: 'rgba(57,197,187,0.6)' }}
        >
          ← 重新上传简历
        </Button>
      </header>

      <div className="page-content">
        <div className="split-layout">
          <div className="split-left">
            <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div className="chat-container">
                <div className="chat-messages" ref={chatRef}>
                  {messages.map((msg, i) => (
                    <div key={i} className={`chat-message ${msg.role}`}>{msg.content}</div>
                  ))}

                  {(() => {
                    const valid = components.filter(c => c.type && c.type !== 'confirm')
                    if (valid.length === 0) return null
                    return (
                      <div key="component-area" className="chat-component-area fade-in">
                        {valid.map((comp, i) => <React.Fragment key={i}>{renderComponent(comp)}</React.Fragment>)}
                      </div>
                    )
                  })()}

                  {loading && <div className="chat-message system">正在处理中...</div>}
                </div>
              </div>
            </div>
          </div>

          <div className="split-right">
            <div className="card" style={{ flex: 1, overflow: 'auto' }}>
              <div className="card-title">已确认信息</div>
              {profileSummary ? (
                <div className="profile-panel fade-in">
                  <div className="profile-section">
                    <div className="profile-section-title">权重排序</div>
                    <div className="profile-weight-list">
                      {profileSummary.weightOrder.map((dim, i) => (
                        <span key={dim} className="profile-weight-item">
                          {i + 1}. {dim} ({(RANK_WEIGHTS[i] * 100).toFixed(0)}%)
                        </span>
                      ))}
                    </div>
                  </div>
                  {profileSummary.cities.length > 0 && (
                    <div className="profile-section">
                      <div className="profile-section-title">期望城市</div>
                      <div className="profile-value">{profileSummary.cities.join('、')}</div>
                    </div>
                  )}
                  {profileSummary.salary && (
                    <div className="profile-section">
                      <div className="profile-section-title">薪资范围</div>
                      <div className="profile-value">{profileSummary.salary}</div>
                    </div>
                  )}
                  {profileSummary.industries.length > 0 && (
                    <div className="profile-section">
                      <div className="profile-section-title">目标行业</div>
                      <div className="profile-value">{profileSummary.industries.join('、')}</div>
                    </div>
                  )}
                  {profileSummary.extra && (
                    <div className="profile-section">
                      <div className="profile-section-title">补充信息</div>
                      <div className="profile-value">{profileSummary.extra}</div>
                    </div>
                  )}
                  {stage === 'S5' && (
                    <div style={{ marginTop: 24, textAlign: 'center' }}>
                      <Button
                        theme="primary"
                        size="large"
                        onClick={handleViewResults}
                        style={{
                          background: 'var(--sky-breeze)', borderColor: 'var(--sky-breeze)',
                          fontSize: 16, fontWeight: 600, padding: '12px 48px', borderRadius: 10,
                        }}
                      >
                        查看匹配结果
                      </Button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="empty-state">
                  <div>请先在左侧完成偏好设置</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
