import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Select, MessagePlugin } from 'tdesign-react'
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Radar, Legend, Tooltip,
} from 'recharts'
import { MoneyIcon, LocationIcon, BuildingIcon, UsergroupIcon, ChartBarIcon, LinkIcon, SearchIcon } from 'tdesign-icons-react'
import { matchJobs, getSessionState } from '../api'

// ── Dimension explanation mapping ──
const DIMENSION_TOOLTIPS = {
  '技能': {
    user: '你掌握的技能数量 / 10（封顶 1.0），反映技能覆盖面',
    job: '岗位要求的技能数量 / 10（封顶 1.0），反映岗位技能门槛',
    summary: '技能维度衡量供需双方的技能覆盖广度，重叠越高说明技能匹配越好。',
  },
  '行业': {
    user: '你的背景与当前岗位行业的语义相似度（0~1），由行业分组表 + DeepSeek 计算',
    job: '固定 1.0 — 岗位完全代表自身行业',
    summary: '行业维度使用语义相似度算法，而非简单查表。同组行业相似度 0.85，跨组无关 0.15。',
  },
  '薪资': {
    user: '基于你期望的薪资范围映射到 0.4~1.0 分',
    job: '岗位薪资中位数 / 25k（封顶 1.0），反映薪资竞争力',
    summary: '薪资维度通过 min/max 对称比较，期望与岗位薪资越接近，重叠度越高。',
  },
  '地域': {
    user: '你选择的城市越多越灵活（城市数/5，封顶 1.0）',
    job: '城市层级评分：一线 1.0，二线 0.8，三线 0.6',
    summary: '地域维度平衡了你的灵活性（多城可选）和岗位的城市层级。',
  },
  '成长': {
    user: '学历分（0.4~1.0）× 大厂经历加成（×1.2），代表你的成长潜力',
    job: '公司规模分 × 职级分（实习 0.5~高级 1.0），代表岗位提供的成长空间',
    summary: '成长维度使用非对称托举公式：岗位空间 ≥ 用户潜力时高分，岗位空间不足时线性衰减。避免"高材生打螺丝"与"小白进核心岗"得分相同。',
  },
  '兴趣': {
    user: 'DeepSeek 评估你的自我评价与热门技术方向的契合度（0~1）',
    job: '基于你补充的兴趣关键词与岗位标题/JD/技能的关键词匹配度',
    summary: '兴趣维度将你的补充意向（如"想做数据分析"）与岗位内容做关键词匹配，标题直接匹配可得 0.95 分。',
  },
}

// ── Custom Tooltip Component ──
function RadarTooltip({ active, payload, selectedJob }) {
  if (!active || !payload || !payload.length) return null

  const dim = payload[0]?.payload?.dimension
  const info = DIMENSION_TOOLTIPS[dim]
  if (!info) return null

  const userVal = payload.find(p => p.dataKey === 'user')?.value ?? 0
  const jobVal = payload.find(p => p.dataKey === 'job')?.value ?? 0

  return (
    <div style={{
      background: '#fff',
      border: '1px solid #e8e8e8',
      borderRadius: 10,
      padding: '12px 16px',
      maxWidth: 320,
      boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
      fontSize: 13,
      lineHeight: 1.7,
    }}>
      <div style={{
        fontWeight: 700,
        fontSize: 15,
        marginBottom: 8,
        color: 'var(--text-primary)',
        borderBottom: '1px solid #f0f0f0',
        paddingBottom: 6,
      }}>
        {dim} 维度
      </div>

      <div style={{ marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
          <span style={{
            display: 'inline-block',
            width: 10, height: 10,
            borderRadius: '50%',
            background: '#FFE76F',
            border: '2px solid #FFD700',
          }} />
          <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>用户</span>
          <span style={{ fontWeight: 600, color: '#B8860B' }}>{userVal}%</span>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: 11, paddingLeft: 18 }}>
          {info.user}
        </div>
      </div>

      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
          <span style={{
            display: 'inline-block',
            width: 10, height: 10,
            borderRadius: '50%',
            background: '#002EA6',
          }} />
          <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>岗位</span>
          <span style={{ fontWeight: 600, color: '#002EA6' }}>{jobVal}%</span>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: 11, paddingLeft: 18 }}>
          {info.job}
        </div>
      </div>

      {/* Growth-specific: show fit score if available */}
      {dim === '成长' && selectedJob?.growth_fit != null && (
        <div style={{
          marginTop: 6,
          padding: '6px 8px',
          background: 'var(--snow-mist)',
          borderRadius: 6,
          fontSize: 12,
        }}>
          <span style={{ color: 'var(--text-muted)' }}>托举适配度：</span>
          <span style={{
            fontWeight: 700,
            color: selectedJob.growth_fit >= 0.8 ? 'var(--success)' :
                   selectedJob.growth_fit >= 0.6 ? 'var(--sky-breeze-dark)' : 'var(--warning)',
          }}>
            {Math.round(selectedJob.growth_fit * 100)}%
          </span>
        </div>
      )}

      <div style={{
        marginTop: 8,
        paddingTop: 6,
        borderTop: '1px solid #f0f0f0',
        color: 'var(--text-muted)',
        fontSize: 11,
        lineHeight: 1.5,
      }}>
        {info.summary}
      </div>
    </div>
  )
}

export default function ResultsPage() {
  const navigate = useNavigate()
  const [matches, setMatches] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)
  const [industryFilter, setIndustryFilter] = useState('all')
  const [sortBy, setSortBy] = useState('match')
  const [resumeId, setResumeId] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [totalPages, setTotalPages] = useState(1)

  useEffect(() => {
    loadSessionAndMatches(1)
  }, [])

  const loadSessionAndMatches = async (pg = 1) => {
    setLoading(true)
    try {
      // 1. 从 cookie session 获取 session_id
      const stateRes = await getSessionState()
      const data = stateRes?.data?.data
      if (!data || !data.session_id) {
        MessagePlugin.warning('未找到会话信息，请先完成偏好设置')
        navigate('/chat')
        return
      }
      const sid = data.session_id
      setSessionId(sid)
      if (data.resume_id) setResumeId(data.resume_id)

      // 2. 执行匹配（分页，每页10条）
      const res = await matchJobs(sid, [], 10, pg)
      const matchData = res.data.data
      setMatches(matchData.matches || [])
      setTotalCount(matchData.total || 0)
      setTotalPages(matchData.total_pages || 1)
      setPage(pg)
      if (matchData.matches?.length) {
        setSelectedJob(matchData.matches[0])
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message
      if (detail === '未登录或会话已过期' || detail === '会话无效或已过期') {
        MessagePlugin.warning('会话已过期，请重新上传简历')
        navigate('/upload')
      } else {
        MessagePlugin.error('加载匹配结果失败: ' + detail)
      }
    } finally {
      setLoading(false)
    }
  }

  const handlePageChange = (newPage) => {
    if (newPage < 1 || newPage > totalPages || newPage === page) return
    loadSessionAndMatches(newPage)
  }

  const navBtnStyle = (active) => ({
    width: 26, height: 26, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 16, fontWeight: 600,
    background: active ? 'var(--sky-breeze)' : 'transparent',
    color: active ? '#fff' : 'var(--text-muted)',
    transition: 'all 0.15s',
  })

  const pageBtnStyle = (active) => ({
    minWidth: 26, height: 26, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: active ? 700 : 500,
    background: active ? 'var(--sky-breeze)' : 'transparent',
    color: active ? '#fff' : 'var(--text-secondary)',
    padding: '0 4px', transition: 'all 0.15s',
  })

  const filteredMatches = matches
    .filter(m => industryFilter === 'all' || m.industry === industryFilter)
    .sort((a, b) => {
      if (sortBy === 'match') return b.match_percentage - a.match_percentage
      return b.salary_max - a.salary_max
    })

  const industries = [...new Set(matches.map(m => m.industry))]

  const getRadarData = (job) => {
    if (!job) return []
    const dims = ['技能', '行业', '薪资', '地域', '成长', '兴趣']
    return dims.map(dim => ({
      dimension: dim,
      user: (job.radar_user?.[dim] || 0) * 100,
      job: (job.radar_job?.[dim] || 0) * 100,
    }))
  }

  const userSkills = selectedJob?.radar_user ? Object.keys(selectedJob.radar_user) : []
  const jobSkills = selectedJob?.skills_required || []

  const hitSkills = jobSkills.filter(s => {
    return userSkills.some(us => s.toLowerCase().includes(us.toLowerCase()) || us.toLowerCase().includes(s.toLowerCase()))
  })
  const missSkills = jobSkills.filter(s => !hitSkills.includes(s))

  if (loading) {
    return (
      <div className="page-container">
        <header className="page-header">
          <div className="logo"><span>Offer 捕手 · 匹配结果</span></div>
        </header>
        <div className="page-content" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 24, marginBottom: 12 }}>⏳</div>
            <div style={{ color: 'var(--text-muted)' }}>正在加载匹配结果...</div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="page-container">
      <header className="page-header">
        <div className="logo">
          
          <span>Offer 捕手 · 匹配结果</span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <Button
            variant="outline"
            onClick={() => navigate(`/chat?session_id=${sessionId}&restart=1`)}
            style={{
              color: '#39C5BB',
              borderColor: 'rgba(57,197,187,0.6)',
            }}
          >
            ← 返回修改偏好
          </Button>
        </div>
      </header>

      <div className="page-content">
        {/* Filter Bar */}
        <div className="filter-bar">
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>行业：</span>
          <Select
            value={industryFilter}
            onChange={(val) => setIndustryFilter(val)}
            options={[
              { label: '全部', value: 'all' },
              ...industries.map(ind => ({ label: ind, value: ind })),
            ]}
            style={{ width: 120 }}
          />
          <span style={{ fontSize: 13, color: 'var(--text-muted)', marginLeft: 16 }}>排序：</span>
          <Select
            value={sortBy}
            onChange={(val) => setSortBy(val)}
            options={[
              { label: '匹配度优先', value: 'match' },
              { label: '薪资优先', value: 'salary' },
            ]}
            style={{ width: 130 }}
          />
          <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 'auto' }}>
            匹配到 {totalCount} 个岗位，第 {page}/{totalPages} 页
          </span>
        </div>

        <div className="split-layout">
          {/* Left: Job List */}
          <div className="split-left">
            <div className="card" style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
              <div className="job-list" style={{ flex: 1 }}>
                {filteredMatches.map(job => (
                  <div
                    key={job.job_id}
                    className={`job-card ${selectedJob?.job_id === job.job_id ? 'selected' : ''}`}
                    onClick={() => setSelectedJob(job)}
                  >
                    <div className="job-card-header">
                      <div>
                        <div className="job-title">{job.title}</div>
                        <div className="job-company">{job.company}</div>
                      </div>
                      <div className="job-match-badge" style={{
                        background: job.match_percentage >= 80 ? 'var(--sky-breeze-dark)' : 'var(--sky-breeze)'
                      }}>
                        {job.match_percentage}%
                      </div>
                    </div>
                    <div className="job-meta">
                      <span><MoneyIcon /> {job.salary_min / 1000}k-{job.salary_max / 1000}k</span>
                      <span><LocationIcon /> {job.city}</span>
                      <span><BuildingIcon /> {job.industry}</span>
                    </div>
                  </div>
                ))}
                {filteredMatches.length === 0 && (
                  <div className="empty-state">
                    <div className="empty-state-icon"><SearchIcon size="32px" /></div>
                    <div>没有匹配的岗位</div>
                  </div>
                )}
              </div>
              {/* Pagination - compact scroll style */}
              {totalPages > 1 && (
                <div style={{
                  display: 'flex', justifyContent: 'center', alignItems: 'center',
                  gap: 2, padding: '8px 4px', borderTop: '1px solid var(--border-color)',
                }}>
                  <button
                    onClick={() => handlePageChange(page - 1)}
                    disabled={page <= 1}
                    style={navBtnStyle(false)}
                  >‹</button>
                  {(() => {
                    const pages = []
                    const start = Math.max(1, page - 2)
                    const end = Math.min(totalPages, page + 2)
                    if (start > 1) {
                      pages.push(<button key={1} onClick={() => handlePageChange(1)} style={pageBtnStyle(false)}>1</button>)
                      if (start > 2) pages.push(<span key="l" style={{padding:'0 2px',color:'var(--text-muted)'}}>…</span>)
                    }
                    for (let i = start; i <= end; i++) {
                      pages.push(<button key={i} onClick={() => handlePageChange(i)} style={pageBtnStyle(i === page)}>{i}</button>)
                    }
                    if (end < totalPages) {
                      if (end < totalPages - 1) pages.push(<span key="r" style={{padding:'0 2px',color:'var(--text-muted)'}}>…</span>)
                      pages.push(<button key={totalPages} onClick={() => handlePageChange(totalPages)} style={pageBtnStyle(false)}>{totalPages}</button>)
                    }
                    return pages
                  })()}
                  <button
                    onClick={() => handlePageChange(page + 1)}
                    disabled={page >= totalPages}
                    style={navBtnStyle(false)}
                  >›</button>
                </div>
              )}
            </div>
          </div>

          {/* Right: Job Detail */}
          <div className="split-right">
            {selectedJob ? (
              <div className="card job-detail fade-in" style={{ flex: 1, overflow: 'auto' }}>
                {/* Header */}
                <div className="job-detail-header">
                  <div className="job-detail-title">{selectedJob.title}</div>
                  <div className="job-detail-company">{selectedJob.company}</div>
                  <div className="job-detail-meta">
                    <span className="job-detail-meta-item"><MoneyIcon /> {selectedJob.salary_min / 1000}k - {selectedJob.salary_max / 1000}k/月</span>
                    <span className="job-detail-meta-item"><LocationIcon /> {selectedJob.city}</span>
                    <span className="job-detail-meta-item"><BuildingIcon /> {selectedJob.industry}</span>
                    <span className="job-detail-meta-item"><UsergroupIcon /> {selectedJob.company_size}</span>
                    <span className="job-detail-meta-item"><ChartBarIcon /> {selectedJob.level}</span>
                    {selectedJob.platform && (
                      <span className="job-detail-meta-item"><LinkIcon /> {selectedJob.platform}</span>
                    )}
                  </div>
                </div>

                {/* Radar Chart */}
                <div className="radar-section" style={{ paddingBottom: 30, textAlign: 'center' }}>
                  <RadarChart
                    data={getRadarData(selectedJob)}
                    width={350}
                    height={320}
                    cx={175}
                    cy={160}
                    outerRadius={115}
                    style={{ margin: '0 auto' }}
                  >
                    <PolarGrid stroke="#e0e0e0" />
                    <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                    <Tooltip content={<RadarTooltip selectedJob={selectedJob} />} />
                    <Radar
                      name="用户"
                      dataKey="user"
                      stroke="#FFE76F"
                      fill="#FFE76F"
                      fillOpacity={0.3}
                      strokeWidth={2}
                    />
                    <Radar
                      name="岗位"
                      dataKey="job"
                      stroke="#002EA6"
                      fill="#002EA6"
                      fillOpacity={0.25}
                      strokeWidth={2}
                    />
                    <Legend wrapperStyle={{ paddingTop: 10 }} iconType="square" />
                  </RadarChart>
                  <div className="radar-center">{selectedJob.match_percentage}%</div>
                  <div className="radar-label">综合匹配度</div>
                </div>

                {/* Match Reason */}
                <div className="match-reason">
                  <strong>匹配理由：</strong>{selectedJob.reason}
                </div>

                {/* Dimension Detail */}
                <div className="card-title" style={{ marginTop: 16 }}>
                  六维对比
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
                  {selectedJob.dimension_match && Object.entries(selectedJob.dimension_match).map(([dim, val]) => (
                    <div key={dim} style={{
                      padding: '8px 12px',
                      background: 'var(--snow-mist)',
                      borderRadius: 8,
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: 13,
                    }}>
                      <span style={{ color: 'var(--text-muted)' }}>{dim}</span>
                      <span style={{
                        fontWeight: 600,
                        color: val >= 0.8 ? 'var(--success)' : val >= 0.6 ? 'var(--sky-breeze-dark)' : 'var(--warning)',
                      }}>
                        {Math.round(val * 100)}%
                      </span>
                    </div>
                  ))}
                </div>

                {/* Skills Compare */}
                <div className="card-title">技能对比</div>
                <div className="skills-compare">
                  {hitSkills.map(s => (
                    <span key={s} className="skill-match hit">✓ {s}</span>
                  ))}
                  {missSkills.map(s => (
                    <span key={s} className="skill-match miss">✗ {s}</span>
                  ))}
                </div>

                {/* JD Preview */}
                <div className="card-title">岗位描述</div>
                <div style={{
                  fontSize: 13,
                  lineHeight: 1.8,
                  color: 'var(--text-secondary)',
                  whiteSpace: 'pre-wrap',
                  maxHeight: 200,
                  overflow: 'auto',
                  padding: 12,
                  background: 'var(--snow-mist)',
                  borderRadius: 8,
                }}>
                  {selectedJob.jd_text}
                </div>

                {/* Actions */}
                <div style={{ marginTop: 20, display: 'flex', gap: 12 }}>
                  <Button
                    theme="primary"
                    onClick={() => {
                      navigate(`/optimize/${selectedJob.job_id}?resume_id=${resumeId}&session_id=${sessionId}`)
                    }}
                    style={{
                      background: 'var(--sky-breeze)',
                      borderColor: 'var(--sky-breeze)',
                      fontWeight: 600,
                      borderRadius: 8,
                    }}
                  >
                    优化简历
                  </Button>
                </div>
              </div>
            ) : (
              <div className="card" style={{ flex: 1 }}>
                <div className="empty-state">
                  <div>请从左侧选择一个岗位查看详情</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
