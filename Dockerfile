FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安装系统依赖（包括 cron）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    curl \
    cron \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 复制项目文件
COPY config/ config/
COPY scripts/ scripts/
COPY web/ web/
COPY sql/ sql/
COPY data/douban_mapping.json data/douban_mapping.json

# 创建数据和日志目录
RUN mkdir -p /app/data /app/logs && chown -R appuser:appuser /app

# 添加 cron 任务（每天凌晨 3 点同步即将上映电影）
RUN echo "0 3 * * * cd /app && python scripts/sync_upcoming.py >> /app/logs/upcoming.log 2>&1" > /etc/cron.d/upcoming-sync \
    && chmod 0644 /etc/cron.d/upcoming-sync \
    && crontab /etc/cron.d/upcoming-sync

# 暴露端口
EXPOSE 5000

# 启动 cron + Gunicorn
CMD ["sh", "-c", "cron && gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 web.app:app"]
