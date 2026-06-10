# Docker 部署指南

## 开发环境

```bash
# 启动
docker compose up -d

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

## 生产环境

### 1. 配置

```bash
# 创建密码文件
mkdir -p secrets
echo "your_secure_password" > secrets/db_password.txt
chmod 600 secrets/db_password.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 Emby 服务器信息
```

### 2. 部署

```bash
# 构建并启动（使用生产配置）
docker compose -f docker-compose.prod.yml up -d --build

# 查看状态
docker compose -f docker-compose.prod.yml ps

# 查看日志
docker compose -f docker-compose.prod.yml logs -f app
```

### 3. 更新

```bash
# 拉取最新代码后重新构建
docker compose -f docker-compose.prod.yml up -d --build app
```

## 生产环境特性

| 特性 | 说明 |
| ---- | ---- |
| 多阶段构建 | Go 程序单独编译，镜像更小 |
| 非 root 用户 | 应用以 appuser 用户运行 |
| Gunicorn | 生产级 WSGI 服务器，4 个 worker |
| 健康检查 | 自动监控容器状态 |
| 资源限制 | 内存限制 512M |
| 日志轮转 | 单个日志最大 10MB，保留 3 个 |
| Secrets | 密码通过文件注入，不写入镜像 |

## 运行脚本

```bash
# 进入应用容器
docker compose -f docker-compose.prod.yml exec app bash

# 运行导出脚本
docker compose -f docker-compose.prod.yml exec app python scripts/export_emby.py --mysql

# 运行 IMDB Top 250
docker compose -f docker-compose.prod.yml exec app python scripts/fetch_imdb_top250.py
```

## 数据库备份

```bash
# 备份
docker compose -f docker-compose.prod.yml exec db mysqldump -uroot -p$(cat secrets/db_password.txt) douban_top250 > backup_$(date +%Y%m%d).sql

# 恢复
docker compose -f docker-compose.prod.yml exec -T db mysql -uroot -p$(cat secrets/db_password.txt) douban_top250 < backup.sql
```

## 常见问题

### 查看容器资源使用

```bash
docker stats emby-movies-app emby-movies-db
```

### 进入数据库

```bash
docker compose -f docker-compose.prod.yml exec db mysql -uroot -p$(cat secrets/db_password.txt) douban_top250
```

### 重建单个服务

```bash
# 只重建应用
docker compose -f docker-compose.prod.yml up -d --build app

# 只重建数据库（数据会保留）
docker compose -f docker-compose.prod.yml up -d --build db
```
