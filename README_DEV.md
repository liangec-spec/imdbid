# 本地开发指南

## 快速开始

### 1. 启动数据库

```bash
docker compose -f docker-compose.dev.yml up -d
```

### 2. 配置环境变量

```bash
export DB_HOST=localhost
export DB_USER=root
export DB_PASSWORD=dev123
export DB_NAME=douban_top250
```

### 3. 运行 Flask

```bash
source venv/bin/activate
python web/app.py
```

访问 http://localhost:5000

## 测试脚本

```bash
# 导出 Emby 电影
python scripts/export_emby.py --mysql

# 获取 IMDB Top 250
python scripts/fetch_imdb_top250.py

# 获取豆瓣 Top 250
python scripts/fetch_douban_top250.py
```

## 本地 Docker 构建

```bash
# 构建镜像
docker build -t emby-movies:test .

# 运行
docker run -d --name emby-test \
  -p 8097:5000 \
  -e DB_HOST=host.docker.internal \
  -e DB_USER=root \
  -e DB_PASSWORD=dev123 \
  -e DB_NAME=douban_top250 \
  emby-movies:test
```

## 修改代码后

### Python 脚本
直接运行，无需重新构建。

### Docker 镜像
```bash
docker build -t emby-movies:test .
docker compose restart app
```

## 数据库管理

```bash
# 进入数据库
docker compose -f docker-compose.dev.yml exec db mysql -uroot -pdev123 douban_top250

# 查看表
SHOW TABLES;

# 查看电影数量
SELECT COUNT(*) FROM emby_movies;

# 重置数据库
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
```
