# Offer捕手

腾讯 AI-HR 培训生线上实战营项目，使用CodeBuddy进行编写。给学生用的 AI 求职匹配小工具。上传简历 PDF，聊几句求职意向，系统算出一批岗位的匹配度，还能针对具体岗位给简历改写建议（ATS 模拟）。

做这个项目主要是因为秋招的时候投简历全靠感觉，想试试能不能把"我和这个岗位合不合适"这件事量化一下。匹配算法是自己琢磨的六维重叠法，谈不上多科学，但跑下来结果基本符合直觉，具体见 [PROJECT_WIKI.md](./PROJECT_WIKI.md)。

演示视频：https://www.bilibili.com/video/BV1MPbk6kERS

## 怎么跑起来

需要 Python 3.10+ 和 Node 18+。

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端（另开一个终端）
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 ，API 文档在 http://localhost:8000/docs 。Windows 下也可以直接双击根目录的 `start.bat`，两件事一起干。

需要先在 `backend/.env` 里填 DeepSeek 的 key：

```
DEEPSEEK_API_KEY=你的key
```

没有 key 的话上传简历这步会失败，匹配算法本身不依赖 AI，可以先拿种子数据逛一逛。

## 技术选型

前端 React + Vite + TDesign，后端 FastAPI，数据库默认 SQLite（想接 MySQL/PostgreSQL 改 `DATABASE_URL` 就行）。简历解析用的 pdfplumber，文本在服务端内存里提取，原始 PDF 不落库——简历这东西还是别到处存比较好。

部署用的是腾讯云 CloudBase（静态托管 + CloudRun），细节在 [deploy.md](./deploy.md)。也留了 Dockerfile 可以一把梭：

```bash
docker build -t offer-catcher .
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=xxx offer-catcher
```

## 已知的问题

- CloudRun 上 SQLite 随容器重启丢数据，目前靠启动时重新灌种子数据顶着，正经用得换 MySQL
- 会话靠 Cookie，24 小时过期，没有账号体系（故意的，不想收集信息）
- 岗位数据是种子数据 + 手工导入的 100 条，没有接真实招聘网站的 API
- 雷达图导出 PDF 在某些长 JD 下会截断

## 目录速览

```
frontend/   React 前端，四个页面：上传 → 对话 → 结果 → 优化
backend/    FastAPI 后端，routers 是接口，services 里是匹配算法和 DeepSeek 封装
deploy.md   CloudBase 部署记录
PROJECT_WIKI.md  算法和接口的详细说明
```
