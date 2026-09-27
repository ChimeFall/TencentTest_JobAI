#!/bin/bash
# Offer捕手 - 后端启动脚本

cd "$(dirname "$0")"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt -q

# 初始化数据库
echo "初始化数据库..."
python -c "from app.database import init_db; from app.services.seed_data import init_seed_data; init_db(); init_seed_data()"

# 启动服务
echo "启动 Offer捕手 API 服务..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
