# Docker 打包计划

## 一、Docker 基础概念

### 什么是 Docker？

Docker 是一个容器化平台，可以把应用和它的依赖打包成一个"容器"，在任何地方都能一致地运行。

### 核心概念

| 概念 | 说明 | 类比 |
| ---- | ---- | ---- |
| 镜像 (Image) | 应用的打包模板 | 安装光盘 |
| 容器 (Container) | 镜像运行的实例 | 运行中的程序 |
| Dockerfile | 构建镜像的脚本 | 安装说明书 |
| docker-compose | 多容器编排工具 | 项目启动脚本 |

### 为什么用 Docker？

- ✅ 一键部署，无需手动安装 Python、MySQL
- ✅ 环境一致，不会出现"我这里能跑"的问题
- ✅ 方便分享和迁移
- ✅ 隔离性好，不影响宿主机

## 二、本项目需要的组件

```
┌─────────────────────────────────────────┐
│           Docker Compose                │
│                                         │
│  ┌─────────────┐   ┌─────────────┐     │
│  │   MySQL     │   │  Python App │     │
│  │  (数据库)    │   │  (Web界面)   │     │
│  │  端口:3306   │◄──│  端口:5000   │     │
│  └─────────────┘   └─────────────┘     │
│         ▲                │              │
│         │                ▼              │
│         │         ┌─────────────┐      │
│         └─────────│   scripts   │      │
│                   │ (定时任务)   │      │
│                   └─────────────┘      │
└─────────────────────────────────────────┘
```

### 需要创建的文件

| 文件 | 作用 |
| ---- | ---- |
| `Dockerfile` | 定义 Python 应用的构建步骤 |
| `docker-compose.yml` | 定义多个容器的编排关系 |
| `.dockerignore` | 排除不需要打包的文件 |
| `scripts/init-db.sh` | 数据库初始化脚本 |

## 三、详细步骤

### 步骤 1：安装 Docker

**Windows/Mac：**
1. 下载 Docker Desktop: <https://www.docker.com/products/docker-desktop/>
2. 安装并启动
3. 验证安装：打开终端，运行 `docker --version`

**Linux (Ubuntu)：**

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 将当前用户添加到 docker 组（免 sudo）
sudo usermod -aG docker $USER

# 重新登录后验证
docker --version
```

### 步骤 2：创建 Dockerfile

Dockerfile 告诉 Docker 如何构建我们的应用镜像。

```dockerfile
# 使用 Python 3.12 基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（MySQL 客户端库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY config/ config/
COPY scripts/ scripts/
COPY web/ web/
COPY sql/ sql/

# 创建数据目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "web/app.py"]
```

### 步骤 3：创建 docker-compose.yml

docker-compose.yml 定义多个容器如何协作。

```yaml
services:
  # MySQL 数据库
  db:
    image: mysql:8.0
    container_name: emby-movies-db
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD:-root123}
      MYSQL_DATABASE: douban_top250
    ports:
      - "3306:3306"
    volumes:
      - mysql-data:/var/lib/mysql
      - ./sql/schema.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Python 应用
  app:
    build: .
    container_name: emby-movies-app
    ports:
      - "5000:5000"
    environment:
      DB_HOST: db
      DB_USER: root
      DB_PASSWORD: ${DB_PASSWORD:-root123}
      DB_NAME: douban_top250
      EMBY_SERVER: ${EMBY_SERVER:-http://localhost:8096}
      EMBY_API_KEY: ${EMBY_API_KEY:-}
      EMBY_PARENT_ID: ${EMBY_PARENT_ID:-}
    volumes:
      - ./data:/app/data
    depends_on:
      db:
        condition: service_healthy

volumes:
  mysql-data:
```

### 步骤 4：创建 .dockerignore

告诉 Docker 哪些文件不需要打包。

```
venv/
.venv/
__pycache__/
*.pyc
.claude/
.git/
*.csv
data/
*.log
temp/
.env
```

### 步骤 5：创建环境变量文件

创建 `.env` 文件（不要提交到 git）。

```bash
# 数据库密码
DB_PASSWORD=your_secure_password

# Emby 服务器配置
EMBY_SERVER=http://your-emby-server:8096
EMBY_API_KEY=your_api_key
EMBY_PARENT_ID=your_library_id
```

### 步骤 6：构建和运行

```bash
# 构建镜像（首次运行需要几分钟）
docker compose build

# 启动所有容器
docker compose up -d

# 查看运行状态
docker compose ps

# 查看日志
docker compose logs -f app

# 停止所有容器
docker compose down
```

### 步骤 7：访问应用

打开浏览器访问：`http://localhost:5000`

## 四、常用命令

### Docker 命令

| 命令 | 说明 |
| ---- | ---- |
| `docker compose up -d` | 后台启动所有容器 |
| `docker compose down` | 停止并删除所有容器 |
| `docker compose ps` | 查看容器状态 |
| `docker compose logs -f` | 实时查看日志 |
| `docker compose exec app bash` | 进入应用容器 |
| `docker compose exec db mysql -uroot -p` | 进入数据库 |

### 重新构建

```bash
# 代码修改后重新构建
docker compose build --no-cache
docker compose up -d

# 只重建应用（不重建数据库）
docker compose up -d --build app
```

## 五、项目文件清单

打包后的项目结构：

```text
imdbid/
├── Dockerfile              # 应用构建脚本
├── docker-compose.yml      # 容器编排配置
├── .dockerignore           # 排除文件列表
├── .env                    # 环境变量（不提交）
├── requirements.txt        # Python 依赖
├── README.md
├── config/
├── scripts/
├── web/
├── sql/
├── douban-scraper/
└── data/                   # 挂载的数据目录
```

## 六、常见问题

### Q: Docker 占用很多空间吗？

A: 本项目镜像约 500MB（主要是 Python 基础镜像）。数据库数据会持久化在 Docker 卷中。

### Q: 如何更新应用？

A: 修改代码后运行：
```bash
docker compose up -d --build app
```

### Q: 如何备份数据库？

A: 使用 mysqldump：
```bash
docker compose exec db mysqldump -uroot -proot123 douban_top250 > backup.sql
```

### Q: 如何查看数据库数据？

A: 进入数据库容器：
```bash
docker compose exec db mysql -uroot -proot123 douban_top250
```

## 七、下一步

确认理解后，我可以帮你：

1. 创建所有 Docker 相关文件
2. 测试构建和运行
3. 验证所有功能正常

准备好后告诉我！
