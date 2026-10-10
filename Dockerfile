# Offer捕手 - Docker 部署文件 (纯后端, 前端已预构建)

FROM python:3.11-slim
WORKDIR /app

# 安装系统依赖 (pdfplumber需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# 前端静态文件（已本地构建好）
COPY frontend/dist ./frontend/dist

# 创建上传目录
RUN mkdir -p uploads

EXPOSE 8000

# 启动命令
CMD ["sh", "-c", "python -c 'from app.database import init_db; from app.services.seed_data import init_seed_data; init_db(); init_seed_data()' && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
