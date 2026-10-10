# Offer捕手 · 技术 Wiki

> 学生求职匹配智能体的完整技术文档：架构、接口、数据模型、匹配算法、部署。
> 最后更新：2026-10

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [目录结构](#3-目录结构)
4. [前端设计](#4-前端设计)
5. [后端 API](#5-后端-api)
6. [数据库设计](#6-数据库设计)
7. [核心算法](#7-核心算法)
8. [DeepSeek 集成](#8-deepseek-集成)
9. [环境变量与配置](#9-环境变量与配置)
10. [部署](#10-部署)
11. [会话与隐私](#11-会话与隐私)

---

## 1. 项目概述

腾讯 AI-HR 培训生线上实战营项目。端到端的求职匹配系统：

- 上传简历 PDF，服务端本地提取文本并结构化解析
- 对话式状态机采集求职偏好（权重排序 → 城市/薪资/行业 → 补充兴趣）
- 六维重叠算法计算岗位匹配度，支持补充兴趣关键词加权
- 针对具体岗位的 ATS 模拟评分与逐条简历改写建议

**技术栈**

| 层 | 技术 |
|---|---|
| 前端 | React 18 + Vite 5 + TDesign React + React Router 6 + Recharts |
| PDF 导出 | html2canvas + jsPDF（前端生成） |
| 后端 | FastAPI 0.115 + Uvicorn 0.34 |
| PDF 解析 | pdfplumber 0.11 |
| AI | DeepSeek API（deepseek-chat），httpx 调用 |
| 数据库 | SQLite（默认）/ MySQL / PostgreSQL，按 `DATABASE_URL` 自动切换 |
| 部署 | 腾讯云 CloudBase（静态托管 + CloudRun）/ Docker |

---

## 2. 系统架构

```
┌────────────────────────────────────────────────────────┐
│                  前端 React SPA                          │
│  / 上传 → /chat 对话 → /results 匹配 → /optimize/:id 优化 │
└───────────────────────┬────────────────────────────────┘
                        │ HTTP + Cookie(offer_session) / ?sid= 降级
                        ▼
┌────────────────────────────────────────────────────────┐
│              FastAPI 后端（Uvicorn :8000）               │
│                                                        │
│  routers/                                              │
│  ├─ resume.py   PDF 上传 → pdfplumber → DeepSeek 结构化 │
│  ├─ chat.py     对话状态机 S2→S3→S4→S5                  │
│  └─ jobs.py     六维匹配 + ATS 分析                     │
│                                                        │
│  services/                                             │
│  ├─ ai_service.py        DeepSeek 封装（6 个职能函数）   │
│  ├─ matching_engine.py   六维重叠 + 成长非对称 + 兴趣加成 │
│  ├─ industry_matcher.py  行业语义相似度                 │
│  └─ seed_data.py         种子岗位初始化                 │
└───────────────────────┬────────────────────────────────┘
                        ▼
┌────────────────────────────────────────────────────────┐
│   数据库：user_profiles / resumes / jobs / chat_history │
└────────────────────────────────────────────────────────┘
```

---

## 3. 目录结构

```
TencentTest_JobAI/
├── frontend/
│   └── src/
│       ├── App.jsx               路由配置
│       ├── api.js                Axios 封装（withCredentials，60s 超时）
│       ├── hooks/useSession.js   会话恢复 Hook
│       └── pages/
│           ├── UploadPage.jsx    简历上传 + 解析预览
│           ├── ChatPage.jsx      对话偏好采集（含拖拽排序组件）
│           ├── ResultsPage.jsx   匹配结果列表 + 六维雷达图 + 技能对比
│           └── OptimizePage.jsx  ATS 评分 + 逐条改写对比
├── backend/
│   └── app/
│       ├── main.py               入口、CORS 兜底、SPA fallback、会话接口
│       ├── config.py             环境变量与算法常量
│       ├── database.py           多驱动封装 + 启动时自动迁移（只加列）
│       ├── routers/              resume / chat / jobs
│       └── services/             ai_service / matching_engine / industry_matcher / seed_data
├── Dockerfile                    根目录一体式镜像（前端构建 + 后端托管）
├── backend/Dockerfile            CloudRun 专用
├── jobs_100.json + _insert_jobs.py   岗位数据与导入脚本
├── deploy.md                     CloudBase 部署记录
└── start.bat                     Windows 一键启动前后端
```

---

## 4. 前端设计

### 4.1 路由

| 路由 | 组件 | 说明 |
|---|---|---|
| `/`, `/upload` | UploadPage | 简历 PDF 上传、解析进度、结构化预览 |
| `/chat` | ChatPage | 状态机对话，支持 `?sid=` 恢复与 `?restart=1` 重开 |
| `/results` | ResultsPage | 岗位列表（分页/筛选）+ 详情（雷达图、六维明细、技能对比、JD） |
| `/optimize/:jobId` | OptimizePage | ATS 通过率、关键词命中/缺失、逐条改写建议 |

### 4.2 会话恢复

- 优先读 httpOnly Cookie `offer_session`（24h 过期）
- Cookie 不可用时降级到 URL 参数 `?sid=`，通过 `GET /api/session/state` 恢复完整状态（消息历史、当前阶段、画像）
- 所有请求 `withCredentials: true`

### 4.3 雷达图

Recharts `RadarChart`：蓝色用户雷达 vs 绿色岗位雷达，悬停显示各维度含义与分数；支持导出 PDF。

---

## 5. 后端 API

### 5.1 会话（main.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| POST | `/api/session/create` | 创建会话，种 `offer_session` Cookie |
| POST | `/api/session/verify` | 校验 Token |
| GET | `/api/session/state` | 完整会话状态（消息、组件、画像） |
| GET | `/api/session/preview` | 脱敏简历预览 |

### 5.2 简历（resume.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/resume/upload` | multipart 上传 PDF → 提取 → 结构化 → 脱敏 → 入库，返回 `preview_html` |
| GET | `/api/resume/preview/{session_id}` | 按会话取预览 |

上传处理流程：读取 PDF → pdfplumber 内存提取文本 → `parse_resume_text()` 结构化 → 姓名/手机/邮箱脱敏 → 存 `resumes` 表 → 生成预览 HTML → 删除临时文件。PDF 二进制不落库。

### 5.3 对话（chat.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat/init` | 建立会话与空画像，进入 S2 |
| POST | `/api/chat/message` | 状态机推进，携带 `current_stage` + `payload` |
| GET | `/api/chat/state/{session_id}` | 恢复对话（消息历史 + 当前阶段组件） |

**状态机**

```
S2 权重排序   拖拽六维 → weights 按名次映射（30/25/20/15/7/3%）
S3 偏好选择   城市多选 + 薪资滑块 + 行业多选（12 大类）
S4 补充兴趣   自由文本 → extract_interest_keywords() 提取 ≤5 个关键词
              → assess_industry() / assess_interest() 评分 → 生成用户雷达
S5 完成       跳转 /results
```

### 5.4 匹配与 ATS（jobs.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/jobs/match` | 六维匹配，支持 `keywords` 过滤、分页；仅返回 >50 分 |
| POST | `/api/ats/analyze` | ATS 报告：通过率、关键词命中/缺失、格式问题、逐条改写 |

**匹配响应核心字段**

```json
{
  "job_id": "...", "title": "...", "company": "...",
  "match_percentage": 85.5,
  "radar_user": {"技能": 0.8, "行业": 0.7, "薪资": 0.6, "地域": 0.8, "成长": 0.7, "兴趣": 0.85},
  "radar_job":  {"技能": 0.9, "行业": 1.0, "薪资": 0.5, "地域": 1.0, "成长": 0.6, "兴趣": 0.7},
  "dimension_match": {"技能": 0.89, "...": "..."},
  "growth_fit": 0.86,
  "reason": "该岗位与你的补充兴趣「数据分析」匹配，……"
}
```

---

## 6. 数据库设计

### user_profiles — 会话与画像

| 字段 | 类型 | 说明 |
|---|---|---|
| session_id | TEXT PK | 会话标识 |
| resume_id | TEXT | 关联简历 |
| profile | TEXT(JSON) | 画像（权重、偏好、extra_keywords、user_industries、radar_user） |
| current_stage | TEXT | S2~S5 |
| session_token | TEXT | Cookie 认证 Token |
| token_expires_at | DATETIME | 过期时间（24h） |
| created_at / updated_at | DATETIME | |

### resumes — 简历

| 字段 | 类型 | 说明 |
|---|---|---|
| resume_id | TEXT PK | |
| raw_text | TEXT | pdfplumber 提取的文本 |
| parsed_json | TEXT(JSON) | DeepSeek 结构化结果 |

不存 PDF 二进制。

### jobs — 岗位

`job_id`(PK) / `platform` / `title` / `company` / `salary_min` / `salary_max` / `salary_score` / `city` / `city_tier`(1/2/3) / `industry` / `company_size` / `level` / `skills_required`(JSON) / `jd_text` / `radar_json`（预计算岗位雷达）

### chat_history — 对话

`id`(自增 PK) / `session_id` / `stage` / `role`(system/user) / `content` / `created_at`

### 驱动切换与自动迁移

- `DATABASE_URL` 以 `mysql://` 开头 → PyMySQL；以 `postgresql://` 开头 → PostgreSQL；否则 SQLite
- 启动时检查表结构，缺列自动 `ALTER TABLE ADD COLUMN`（仅支持加列）

---

## 7. 核心算法

### 7.1 六维重叠匹配

```
Match% = Σ(min(U_i, J_i) × W_i) / Σ(max(U_i, J_i) × W_i) × 100
```

- `U_i` / `J_i`：用户 / 岗位第 i 维得分（0~1）
- `W_i`：用户排序权重，名次映射 30 / 25 / 20 / 15 / 7 / 3%

### 7.2 各维度评分

| 维度 | 用户侧 | 岗位侧 |
|---|---|---|
| 技能 | 技能数 / 10，封顶 1.0 | 要求技能数 / 10 |
| 行业 | 与岗位行业的语义相似度（见 7.3） | 固定 1.0 |
| 薪资 | 期望档映射：5k→0.2 … 25k+→1.0 | 平均薪资 / 25000 |
| 地域 | 意向城市数 / 5（开放度） | 城市线级：一线 1.0 / 二线 0.8 / 三线 0.6 |
| 成长 | 学历分（专科0.4~博士1.0）× 大厂经历 1.2 倍加成 | 公司规模系数 × 级别系数 |
| 兴趣 | DeepSeek 评估明确度 | 有关键词时实时算，否则预计算/中间值 |

### 7.3 行业语义相似度（industry_matcher.py）

解决"双高假象"：用户行业分高、岗位行业分高，但行业不同。改为相似度计算：

- 12 个行业大类（互联网、教育、金融、文化、医疗、制造、房地产、零售、能源、农业、政府、服务）
- 同组 0.95；关联组按映射表（如互联网+教育 0.60）；无关 0.20
- 规则表判不出时调用 DeepSeek 兜底；用户侧取 Top3 行业对岗位行业的最大相似度

### 7.4 成长维非对称托举（growth_fit）

成长是唯一非对称维度，对称 min/max 会掩盖"大材小用"：

```
job_space >= user_potential:  fit = 1.0 - min((job_space - user_potential) × 0.4, 0.25)
job_space <  user_potential:  fit = max(0.2, job_space / user_potential)
```

雷达图展示原始分，匹配计算用 fit 分。

### 7.5 兴趣关键词加成

- S4 自由文本 → DeepSeek 提取 ≤5 个关键词（API 不可用时本地词典兜底），存 `preferences.extra_keywords`
- 匹配规则：完整命中岗位标题/JD/技能/行业/公司规模；2 字词在标题/技能中命中；3+ 字词的任意 2 字子串在标题/技能中命中
- 每命中 1 个关键词，匹配度 ×1.025，上限 +15%（6 个）
- 命中关键词写入 `reason` 字段以保证可解释性

---

## 8. DeepSeek 集成

`ai_service.py` 统一封装，temperature 0.1，响应自动剥离 markdown 代码块后 `json.loads`。

| 函数 | 用途 | 时机 |
|---|---|---|
| `parse_resume_text()` | 简历文本 → 结构化 JSON | 上传 |
| `assess_industry()` | 经历与行业契合度 + Top3 行业 | S4 |
| `assess_interest()` | 兴趣明确度评分 | S4 |
| `extract_interest_keywords()` | 补充文本提取方向关键词 | S4 |
| `assess_job_interest()` | 岗位 JD 兴趣分 | 预计算备用 |
| `ats_analyze()` | ATS 报告与改写建议 | 优化页 |

降级策略：简历解析失败走正则粗提取；关键词提取失败走本地词典；行业相似度优先本地规则表。

Prompt 模板见设计文档 `Offer捕手学生求职匹配智能体设计文档.md` 第 7 节。

---

## 9. 环境变量与配置

### 后端（backend/.env）

| 变量 | 说明 | 默认 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek 密钥（必填） | — |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com` |
| `DATABASE_URL` | 数据库连接 | `sqlite:///./offer_catcher.db` |
| `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` | CloudBase MySQL 独立变量 | — |

### 前端

| 变量 | 说明 |
|---|---|
| `VITE_API_BASE` | 开发环境留空（走 Vite proxy），生产填 CloudRun 地址 |

### 算法常量（config.py）

`RANK_WEIGHTS`（30/25/20/15/7/3%）、`SALARY_SCORE_MAP`、`DEGREE_SCORE`、`CITY_TIER`、`BIG_COMPANY_KEYWORDS`。

---

## 10. 部署

### 本地开发

```bash
# 后端
cd backend && pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd frontend && npm install && npm run dev
```

入口：http://localhost:5173 ；API 文档：http://localhost:8000/docs 。Windows 可直接运行 `start.bat`。

### Docker（一体式）

```bash
docker build -t offer-catcher .
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=xxx offer-catcher
```

根 Dockerfile 多阶段构建：前端 `vite build` 产物由后端 StaticFiles 托管，SPA 路由 404 回退 `index.html`。

### CloudBase 生产环境

- 前端：静态网站托管（`frontend/dist`）
- 后端：CloudRun 容器 `offer-catcher-api`，0.5 核 / 1GB / 端口 8000 / 最小实例 1
- 环境 ID：`tencenttest-jobai-d1dx907e0c6eca`（ap-shanghai）
- 详细步骤与控制台地址见 `deploy.md`

**已知限制**：CloudRun 上 SQLite 随容器重启丢数据（启动时重建种子数据）；生产使用建议切换 MySQL。

---

## 11. 会话与隐私

- 无账号体系：`offer_session` Token（`secrets.token_urlsafe(48)`），httpOnly + Secure + SameSite=None，24 小时过期
- Cookie 被网关节流时通过 `?sid=` URL 参数降级恢复
- PDF 仅在服务端内存中提取文本，二进制不落库；临时文件解析后删除
- 展示层脱敏：姓名 `张*`、手机 `138****1234`、邮箱 `a**b@domain.com`（库中保留原文供 ATS 分析）
- DeepSeek API Key 仅存在于后端环境变量
