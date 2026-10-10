# Offer捕手：学生求职匹配智能体

腾讯 AI-HR 培训生线上实战营项目。

本项目是一种基于简单AI对话，面向高校学生的端到端求职匹配系统，帮助求职者匹配心仪岗位与修改简历的工具。通过分析求职者上传的简历，对话式交互采集求职偏好，用六维图以及六维重叠算法计算显示岗位与求职者的适配度，并针对具体岗位提供ATS模拟评分与逐条简历改写建议。

tips：本系统用六维图做适配度直观展示，主要是受游戏/动漫中数据展示环节里画面的影响。选一个岗位就会有一个六维图展示自己和岗位的数据，感觉还是很酷的吧。

演示视频：https://www.bilibili.com/video/BV1MPbk6kERS

## 功能特性

- **简历智能解析**：上传 PDF，服务端本地提取文本（pdfplumber），DeepSeek 结构化为教育经历、技能、实习经历等字段，展示层自动脱敏
- **对话式偏好采集**：状态机驱动（权重排序 → 城市/薪资/行业选择 → 自由补充），结构化组件与自由输入结合
- **六维岗位匹配**：技能 / 行业 / 薪资 / 地域 / 成长 / 兴趣六维重叠算法，输出匹配百分比、双雷达图与逐维明细
- **兴趣关键词加成**：从用户补充信息中提取方向关键词，命中岗位时匹配度加权（每词 +2.5%，上限 15%）
- **ATS 简历优化**：模拟企业 ATS 筛选，给出通过率预估、关键词命中/缺失分析和逐条改写建议
- **隐私安全**：PDF 二进制不落库，Cookie 匿名会话（24 小时过期），无需注册

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + Vite 5 + TDesign React + React Router 6 + Recharts |
| 后端 | FastAPI + Uvicorn + pdfplumber |
| AI | DeepSeek API（deepseek-chat） |
| 数据库 | SQLite（默认）/ MySQL / PostgreSQL，按 `DATABASE_URL` 自动切换 |
| 部署 | 腾讯云 CloudBase（静态托管 + CloudRun）/ Docker |

## 快速开始

环境要求：Python 3.10+，Node.js 18+。

**1. 配置 API 密钥**

创建 `backend/.env`：

```
DEEPSEEK_API_KEY=你的密钥
```

**2. 启动后端**

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**3. 启动前端**（另开终端）

```bash
cd frontend
npm install
npm run dev
```

**4. 访问**

| 入口 | 地址 |
|---|---|
| 前端页面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/docs |

Windows 下可直接运行根目录 `start.bat` 同时启动前后端。首次启动自动初始化种子岗位数据。

## Docker 部署

```bash
docker build -t offer-catcher .
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=xxx offer-catcher
```

## 项目结构

- `frontend/`：React 前端，四个页面（上传 → 对话 → 结果 → 优化）
- `backend/`：FastAPI 后端，`routers/` 为接口层，`services/` 为匹配算法与 AI 封装
- `Dockerfile`：一体式镜像（前端构建产物由后端托管）
- `jobs_100.json` + `_insert_jobs.py`：岗位数据与导入脚本

## 文档（Word 版）

- [PROJECT_WIKI.docx](./PROJECT_WIKI.docx)：技术 Wiki——架构、API、数据库、匹配算法详解
- [Offer捕手学生求职匹配智能体设计文档.docx](./Offer捕手学生求职匹配智能体设计文档.docx)：设计文档

## 已知限制

- CloudRun 上 SQLite 数据随容器重启丢失，生产环境建议切换 MySQL
- 岗位数据为预置种子数据，未接入实时招聘平台
- 雷达图导出 PDF 在长文本场景下可能截断
