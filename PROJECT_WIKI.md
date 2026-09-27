# 项目说明（算法 / 接口 / 数据库）

README 放不下的细节都记在这。最后一次整理是 2026-06。

## 整体流程

```
上传简历 PDF
  → pdfplumber 提取文本（服务端内存里做，PDF 本身不落库）
  → DeepSeek 把文本解析成结构化 JSON，顺便脱敏（姓名/手机/邮箱）
  → 对话页收集偏好：先拖权重排序，再选城市/薪资/行业，最后自由输入补充兴趣
  → 六维匹配算出岗位列表
  → 点具体岗位进 ATS 分析页，拿逐条改写建议
```

前端路由就四个：`/`（上传）、`/chat`（对话）、`/results`（结果）、`/optimize/:jobId`（优化）。

会话这块绕了点弯路：CloudBase 的网关上 httpOnly Cookie 偶尔被吃掉，所以做了双保险——优先 Cookie（`offer_session`，24 小时），不行了前端就从 URL 的 `?sid=` 恢复。所有 axios 请求都带 `withCredentials`。

## 匹配算法

这是项目的核心，多说两句。

用户和岗位各打六个维度的分：技能、行业、薪资、地域、成长、兴趣。然后按用户自己排的权重算重叠度：

```
匹配度 = Σ(min(U_i, J_i) × W_i) / Σ(max(U_i, J_i) × W_i) × 100%
```

权重映射是拍脑袋定的：第 1 名 30%，第 2 名 25%，20%、15%、7%、3% 递减。用 min/max 而不用余弦相似度，是想让"单项瘸腿"被惩罚得更明显一点。

几个维度里有两个特殊的：

**行业**——一开始直接用绝对值比，结果出现"用户行业分高、岗位行业分也高，但压根不是一个行业"的乌龙。后来改成算语义相似度：把行业归到 12 个大类（互联网、教育、金融、文化、医疗、制造、房地产、零售、能源、农业、政府、服务），同组 0.95，有关联的组按预设值（比如互联网+教育 0.60），无关 0.20。DeepSeek 可用的时候让它判，不可用走本地映射表。代码在 `industry_matcher.py`。

**成长**——唯一一个非对称维度。岗位成长空间大于等于用户潜力给高分，装不下就线性衰减：`growth_fit = min(1.0, u_potential / j_space)`。雷达图上还是显示原始分，但算匹配度用衰减后的 fit 分。不然"用户太强岗位太菜"这种错配会被漏掉。

**兴趣关键词加成**——用户在对话最后一步自由输入的补充（比如"想干数据分析，偏好中厂"），用 DeepSeek 提取最多 5 个关键词（API 挂了就用本地词典兜底），然后在岗位标题/JD/技能/行业/公司规模里匹配。每命中一个匹配度乘 1.025，封顶 +15%。命中了会在 `reason` 字段里写明是哪条命中的，方便解释。

## 后端接口

| 方法 | 路径 | 干嘛的 |
|------|------|--------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/session/create` | 建会话，种 Cookie |
| POST | `/api/session/verify` | 验 Token |
| GET | `/api/session/state` | 拉完整会话状态（消息、画像） |
| GET | `/api/session/preview` | 脱敏后的简历预览 |
| POST | `/api/resume/upload` | 传 PDF，解析 + 脱敏 + 入库 |
| GET | `/api/resume/preview/{session_id}` | 按 session 拿预览 |
| POST | `/api/chat/init` | 初始化对话，返回 session_id |
| POST | `/api/chat/message` | 状态机驱动对话 |
| GET | `/api/chat/state/{session_id}` | 恢复对话状态 |
| POST | `/api/jobs/match` | 匹配，支持分页和关键词过滤 |
| POST | `/api/ats/analyze` | ATS 分析 + 改写建议 |

对话是个四段状态机（S2 权重排序 → S3 城市/薪资/行业 → S4 补充兴趣 + 提关键词 → S5 完成），历史存 `chat_history` 表。

`/api/jobs/match` 返回里比较关键的字段：`match_percentage`（总分）、`radar_user` / `radar_job`（两个雷达）、`dimension_match`（每维明细）、`reason`（文字解释）。

## 数据库

四张表：`user_profiles`（会话 + 画像 JSON）、`resumes`（提取后的文本和解析结果，**没有** PDF 二进制）、`jobs`（岗位，含预计算的雷达分）、`chat_history`。

`DATABASE_URL` 决定用哪个库：`mysql://` 开头走 MySQL，`postgresql://` 开头走 PostgreSQL，否则 SQLite。启动时有个简单的自动迁移，发现表缺列就 `ALTER TABLE` 补上——升级代码不用手动刷库，代价是只支持加列，删列改名还得手动。

画像 JSON 大概长这样：

```json
{
  "radar_user": {"技能": 0.8, "行业": 0.7, "薪资": 0.6, "地域": 0.8, "成长": 0.7, "兴趣": 0.85},
  "weight_order": ["技能", "行业", "薪资", "地域", "成长", "兴趣"],
  "weights": {"技能": 0.30, "行业": 0.25, "薪资": 0.20, "地域": 0.15, "成长": 0.07, "兴趣": 0.03},
  "preferences": {
    "cities": ["北京", "上海"],
    "salary_range": "10k-15k",
    "industries": ["互联网", "AI"],
    "extra_interests": "想干数据分析，偏好中厂",
    "extra_keywords": ["数据分析", "中厂"]
  }
}
```

## 环境变量

后端：`DEEPSEEK_API_KEY`（必填）、`DEEPSEEK_BASE_URL`（默认官方地址）、`DATABASE_URL`。前端：`VITE_API_BASE`，开发环境留空走 Vite proxy，生产填 CloudRun 地址。

## 踩过的坑（按时间顺序，2026-06-11 那几天）

留着备忘，也给想复现的人提个醒：

- pdfplumber 对某些字体嵌入的 PDF 会抽出乱码，目前没好办法，解析失败就提示用户换文件
- CloudRun 网关返回的 405/401 不走过 CORSMiddleware，错误响应没有 CORS 头，浏览器直接报跨域。最后在 `main.py` 里加了个全局中间件手动补头，再加显式 OPTIONS 路由才解决
- 「返回修改偏好」后老会话过期，跳到对话页直接白屏。现在的做法是 forceRestart 时保留原 sessionId
- 一开始把 PDF 二进制存进 `resumes.pdf_data`，后来想想隐私上过不去，删了，只留文本
- 全局蓝色 box-shadow 在某些屏幕上看像 UI 坏了，删了
- S3 的行业选项一开始只有几个大类，不够用，扩到 12 个
