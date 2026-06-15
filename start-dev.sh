#!/bin/bash
# 本地开发环境启动脚本

# 加载 .env 文件
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 激活虚拟环境
source venv/bin/activate

# 启动 Flask
echo "启动 Flask..."
echo "访问 http://localhost:5000"
python web/app.py
