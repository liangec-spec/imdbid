# 🎬 Emby 电影管理系统

管理 Emby 媒体库，对比 IMDB/豆瓣 Top 250，展示 IMDB 评分。

## ✨ 功能

- **Emby 电影导出** - 从 Emby 服务器批量导出电影元数据
- **IMDB Top 250 对比** - 使用贝叶斯加权公式计算排名
- **豆瓣 Top 250 对比** - 自动检测缺失电影
- **IMDB 评分获取** - 从 IMDB 公开数据集批量获取评分（匹配率 99.9%）
- **Web 管理界面** - 搜索、筛选、排序、评分展示
- **Docker 部署** - 一键部署到生产环境
- **自动发布** - GitHub Actions 自动构建 Docker 镜像

## 📁 项目结构

```text
imdbid/
├── config/                  # 集中配置
│   └── __init__.py
├── scripts/                 # 脚本工具
│   ├── export_emby.py       # Emby 导出（含 IMDB 评分）
│   ├── fetch_imdb_top250.py # IMDB Top 250 获取
│   └── import_douban.py     # 豆瓣数据导入
├── douban-scraper/          # 豆瓣爬虫（Go）
│   ├── main.go
│   ├── go.mod
│   └── Makefile
├── web/                     # Web 管理界面
│   ├── app.py
│   └── templates/
│       └── index.html
├── sql/                     # 数据库脚本
│   └── schema.sql
├── .github/workflows/       # GitHub Actions
│   └── docker.yml           # Docker 自动构建
├── Dockerfile               # Docker 镜像构建
├── docker-compose.yml       # 开发环境配置
├── docker-compose.prod.yml  # 生产环境配置
├── .env.example             # 环境变量模板
├── .gitignore
├── requirements.txt
└── README.md
```

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

#### 1. 拉取镜像

```bash
docker pull liangec/emby-movies:latest
```

#### 2. 配置环境变量

```bash
mkdir -p secrets
echo "your_db_password" > secrets/db_password.txt
chmod 600 secrets/db_password.txt

cat > .env << EOF
EMBY_SERVER=http://your-emby-server:8096
EMBY_API_KEY=your-api-key
EMBY_PARENT_ID=your-library-id
DB_PASSWORD=your_db_password
EOF
```

#### 3. 启动服务

```bash
docker compose -f docker-compose.prod.yml up -d
```

#### 4. 访问

打开浏览器访问：`http://localhost:5000`

### 方式二：本地开发

#### 1. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入 Emby 服务器信息和数据库配置
```

#### 3. 初始化数据库

```bash
mysql -u root < sql/schema.sql
```

#### 4. 运行数据更新

```bash
# 导出 Emby 电影并获取 IMDB 评分
python scripts/export_emby.py --mysql

# 获取 IMDB Top 250
python scripts/fetch_imdb_top250.py

# 导入豆瓣 Top 250（需要先编译 Go 程序）
cd douban-scraper && make && cd ..
python scripts/import_douban.py
```

#### 5. 启动 Web 界面

```bash
python web/app.py
# 访问 http://localhost:5000
```

## 🛠️ 技术栈

- **后端**: Python 3.12+, Flask, PyMySQL, Gunicorn
- **前端**: HTML5, CSS3, Vanilla JavaScript
- **数据库**: MySQL 8.0+
- **数据源**: Emby API, IMDB 公开数据集, 豆瓣
- **部署**: Docker, Docker Compose
- **CI/CD**: GitHub Actions

## 📊 数据库

| 表名 | 说明 |
| ---- | ---- |
| emby_movies | Emby 电影数据（含 IMDB 评分） |
| imdb_top250 | IMDB Top 250 |
| douban_top250 | 豆瓣 Top 250 |

## 🔄 发布流程

### 自动发布（推荐）

```bash
# 1. 修改代码并提交
git add .
git commit -m "feat: 添加新功能"
git push

# 2. 创建版本 tag
git tag -a v1.1.0 -m "版本 1.1.0"
git push origin v1.1.0

# 3. GitHub Actions 自动构建并推送到 Docker Hub
# 4. 生产环境拉取新版本
docker pull liangec/emby-movies:v1.1.0
docker compose -f docker-compose.prod.yml up -d
```

### 版本号规范

采用语义化版本号：`v主版本.次版本.补丁版本`

- **主版本**：重大变更，可能不兼容
- **次版本**：新功能，向后兼容
- **补丁版本**：bug 修复

## 🔗 相关链接

- **GitHub**: <https://github.com/liangec-spec/imdbid>
- **Docker Hub**: <https://hub.docker.com/r/liangec/emby-movies>
- **GitHub Actions**: <https://github.com/liangec-spec/imdbid/actions>

## 📦 Docker 镜像

| 标签 | 说明 |
| ---- | ---- |
| `liangec/emby-movies:latest` | 最新稳定版 |
| `liangec/emby-movies:v1.0.0` | 特定版本 |

## 📝 版本历史

### v2.1.0 (2026-06-10)

- 添加 Docker 支持（开发/生产环境）
- 添加 GitHub Actions 自动构建
- 使用 Gunicorn 作为生产级 WSGI 服务器
- 多阶段构建，减小镜像体积
- 非 root 用户运行，提高安全性

### v2.0.0 (2026-06-09)

- 重构项目结构，规范命名
- 集中配置管理（支持环境变量）
- 修复 countries 解析 bug
- 添加线程安全（Web 界面）
- 添加 .gitignore 和 requirements.txt
- 清理冗余文件

### v1.0.0 (2026-06-09)

- 初始版本发布
- Emby 电影导出
- IMDB/豆瓣 Top 250 对比
- Web 管理界面
- IMDB 评分批量获取

## 📄 许可证

MIT License
