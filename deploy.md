# Offer捕手 - 部署指南

## 项目结构
```
Offer捕手/
├── frontend/          # React + Vite + TDesign 前端
│   ├── src/
│   │   ├── pages/     # UploadPage, ChatPage, ResultsPage, OptimizePage
│   │   ├── api.js     # API 封装
│   │   ├── App.jsx    # 路由配置
│   │   └── App.css    # 全局样式
│   └── vite.config.js
├── backend/           # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py    # 入口
│   │   ├── config.py  # 配置
│   │   ├── database.py # SQLite 操作
│   │   ├── routers/   # API 路由
│   │   └── services/  # 业务逻辑
│   ├── seed_data/     # 种子岗位数据
│   └── requirements.txt
└── Dockerfile         # Docker 多阶段构建
```

## CloudBase 部署（当前生产环境）

### 前端 - 静态网站托管
- **URL**: `https://tencenttest-jobai-d1dx907e0c6eca-1442109455.tcloudbaseapp.com/`
- **管理后台**: https://tcb.cloud.tencent.com/dev?envId=tencenttest-jobai-d1dx907e0c6eca#/static-hosting

### 后端 - CloudRun 容器型服务
- **服务名**: `offer-catcher-api`
- **URL**: `https://offer-catcher-api-268800-7-1442109455.sh.run.tcloudbase.com`
- **管理后台**: https://tcb.cloud.tencent.com/dev?envId=tencenttest-jobai-d1dx907e0c6eca#/platform-run
- **配置**: CPU 0.5核 / 内存 1GB / 最小实例数 1 / 端口 8000

### 环境信息
- **环境ID**: `tencenttest-jobai-d1dx907e0c6eca`
- **区域**: `ap-shanghai`
- **套餐**: 体验版
- **控制台**: https://tcb.cloud.tencent.com/dev?envId=tencenttest-jobai-d1dx907e0c6eca#/overview

### 重新部署步骤

1. 构建前端（API地址已在 `.env.production` 中配置）:
```bash
cd frontend
npm run build
```

2. 上传前端到静态托管:
```bash
# 通过 CloudBase 工具或控制台上传 frontend/dist/ 目录
```

3. 部署后端到 CloudRun:
```bash
# 通过 CloudBase 工具部署，使用 Dockerfile 自动构建
```

## 本地开发

### 后端
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| VITE_API_BASE | 前端 API 地址 | 本地为空(走proxy)，生产为CloudRun地址 |
| DEEPSEEK_API_KEY | DeepSeek API密钥 | 内置 |
| DEEPSEEK_BASE_URL | DeepSeek API地址 | https://api.deepseek.com |
| DATABASE_URL | 数据库URL | sqlite:///./offer_catcher.db |

## 注意事项

1. **PDF解析**：依赖 pdfplumber，需要系统安装 libpoppler
2. **隐私**：PDF文本仅在后端本地提取，不上传第三方
3. **种子数据**：首次启动自动生成10条种子岗位
4. **DeepSeek API**：需要有效的API密钥才能使用AI功能
5. **会话管理**：使用 Cookie 维持用户会话，无需登录
6. **数据库**：CloudRun 容器使用本地 SQLite，注意数据持久化（容器重启会丢失数据）
