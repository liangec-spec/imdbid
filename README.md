# 🎬 Emby 电影管理系统

管理 Emby 媒体库，对比 IMDB/豆瓣 Top 250，展示 IMDB 评分，管理电影合集。

## ✨ 功能

- **Emby 电影导出** - 从 Emby 服务器批量导出电影元数据
- **IMDB Top 250 对比** - 使用贝叶斯加权公式计算排名（最低 100,000 票）
- **豆瓣 Top 250 对比** - 自动检测缺失电影
- **IMDB 评分获取** - 从 IMDB 公开数据集批量获取评分（匹配率 99.9%）
- **电影合集管理** - 展示 Emby 合集，显示未收录电影（基于 TMDB）
- **即将/正在上映** - 中国/美国各 50 部电影
- **Web 管理界面** - 搜索、筛选、排序、分页、主题切换
- **Docker 部署** - 一键部署到生产环境

## 📁 项目结构

```text
imdbid/
├── config/                     # 集中配置
│   └── __init__.py
├── scripts/                    # 脚本工具
│   ├── export_emby.py          # Emby 导出（含 IMDB 评分）
│   ├── fetch_imdb_top250.py    # IMDB Top 250 获取
│   ├── fetch_douban_top250.py  # 豆瓣 Top 250 爬虫
│   ├── import_douban.py        # 豆瓣数据导入
│   ├── sync_collections.py     # 电影合集同步
│   └── sync_upcoming.py        # 即将/正在上映同步
├── web/                        # Web 管理界面
│   ├── app.py
│   └── templates/
│       └── index.html
├── sql/                        # 数据库脚本
│   └── schema.sql
├── data/                       # 数据文件（Git 忽略）
│   └── posters/                # 图片缓存
├── .github/workflows/          # GitHub Actions
│   └── docker.yml              # Docker 自动构建
├── Dockerfile                  # Docker 镜像构建
├── docker-compose.yml          # Docker Compose 配置
├── .env.example                # 环境变量模板
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
cp .env.example .env
```

编辑 `.env` 文件，填入以下配置：

```bash
# 必填
EMBY_SERVER=http://your-emby-server:8096
EMBY_API_KEY=your-api-key
EMBY_PARENT_ID=your-library-id
DB_PASSWORD=your_secure_password

# 可选
EMBY_COLLECTIONS_PARENT_ID=43626    # 合集媒体库 ID，默认 43626
TMDB_API_KEY=your-tmdb-api-key      # 用于合集和即将上映功能
```

#### 3. 启动服务

```bash
docker compose up -d
```

#### 4. 访问

打开浏览器访问：`http://your-server:8097`

#### 5. 初始化数据

```bash
# 导出 Emby 电影（含 IMDB 评分）
docker compose exec app python scripts/export_emby.py --mysql

# 获取 IMDB Top 250
docker compose exec app python scripts/fetch_imdb_top250.py

# 获取豆瓣 Top 250
docker compose exec app python scripts/fetch_douban_top250.py

# 同步电影合集
docker compose exec app python scripts/sync_collections.py

# 同步即将/正在上映
docker compose exec app python scripts/sync_upcoming.py
```

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
# 编辑 .env 文件
```

#### 3. 初始化数据库

```bash
mysql -u root < sql/schema.sql
```

#### 4. 运行脚本

```bash
python scripts/export_emby.py --mysql
python scripts/fetch_imdb_top250.py
python scripts/fetch_douban_top250.py
python scripts/sync_collections.py
python scripts/sync_upcoming.py
```

#### 5. 启动 Web 界面

```bash
python web/app.py
# 访问 http://localhost:5000
```

## ⚙️ 配置项说明

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
| ---- | ---- | ------ | ---- |
| `EMBY_SERVER` | ✅ | - | Emby 服务器地址 |
| `EMBY_API_KEY` | ✅ | - | Emby API 密钥 |
| `EMBY_PARENT_ID` | ✅ | - | 电影媒体库 ID |
| `DB_PASSWORD` | ✅ | - | MySQL root 密码 |
| `EMBY_COLLECTIONS_PARENT_ID` | ❌ | 43626 | 合集媒体库 ID |
| `TMDB_API_KEY` | ❌ | - | TMDB API Key（合集和即将上映功能需要） |

### 获取配置值

**Emby API Key：**
1. 打开 Emby 管理后台
2. 设置 → API 密钥 → 创建新密钥

**Emby 媒体库 ID（Parent ID）：**
```bash
curl -s "http://your-emby-server:8096/Library/VirtualFolders?api_key=your-api-key" | python3 -m json.tool
```

**TMDB API Key：**
1. 访问 <https://www.themoviedb.org/settings/api>
2. 注册账号并申请 API Key

## 🛠️ 技术栈

- **后端**: Python 3.12, Flask, Gunicorn, PyMySQL
- **前端**: HTML5, CSS3, JavaScript
- **数据库**: MySQL 8.0
- **数据源**: Emby API, IMDB 公开数据集, TMDB API, 豆瓣
- **部署**: Docker, Docker Compose, GitHub Actions

## 📊 数据库

| 表名 | 说明 |
| ---- | ---- |
| emby_movies | Emby 电影数据（含 IMDB 评分、封面 URL） |
| imdb_top250 | IMDB Top 250 |
| douban_top250 | 豆瓣 Top 250（含 douban_id） |
| douban_imdb_mapping | 豆瓣-IMDB 手动关联映射 |
| emby_collections | 电影合集 |
| emby_collection_movies | 合集内的电影 |
| upcoming_movies | 即将/正在上映电影 |

## 🎨 Web 界面功能

### 电影清单

- 分页显示（每页 50 条）
- 搜索（电影名称、IMDB ID）
- 排序（名称、年份、IMDB 评分、加入日期）
- 筛选（全部、仅 IMDB 250、仅豆瓣 250、两者都在）
- 点击展开详情（导演、演员、简介、编码等）
- 显示封面缩略图、分辨率、位置、加入日期
- IMDB/豆瓣排名显示（前 50 加粗）

### Top 250

- 豆瓣 Top 250（支持搜索、筛选、手动关联 IMDB ID）
- IMDB Top 250（支持搜索、筛选）

### 电影合集

- 合集列表（分页、搜索、筛选）
- 展开显示已收录/未收录电影
- 未收录电影基于 TMDB 数据对比
- 显示电影封面

### 即将/正在上映

- 中国/美国各 50 部电影
- 即将上映（按上映日期排序）
- 正在上映（按热度排序）
- 显示电影海报

### 主题切换

6 种配色主题：午夜蓝、翡翠绿、日落粉、海洋蓝、星空紫、浅色模式

## 🔄 版本发布

### 自动发布（GitHub Actions）

```bash
# 1. 修改代码并提交
git add .
git commit -m "feat: 添加新功能"
git push

# 2. 创建版本 tag
git tag -a v2.1.0 -m "版本 2.1.0"
git push origin v2.1.0

# 3. GitHub Actions 自动构建并推送到 Docker Hub
```

### 版本号规范

采用语义化版本号：`v主版本.次版本.补丁版本`

- **主版本**：重大变更
- **次版本**：新功能
- **补丁版本**：bug 修复

## 🔗 相关链接

- **GitHub**: <https://github.com/liangec-spec/imdbid>
- **Docker Hub**: <https://hub.docker.com/r/liangec/emby-movies>

## 📦 Docker 镜像

| 标签 | 说明 |
| ---- | ---- |
| `liangec/emby-movies:latest` | 最新稳定版 |
| `liangec/emby-movies:v2.2.2` | 特定版本 |

## 📝 版本历史

### v2.2.2 (2026-06-23)

- 图片代理添加本地缓存
- 图片延迟加载，避免并发过多导致 502
- 自动清理 30 天前的缓存

### v2.2.1 (2026-06-22)

- 修复 cron 任务使用 python3
- 添加正在上映页面（中国/美国各 50 部）
- 同步脚本同时更新即将上映和正在上映

### v2.2.0 (2026-06-18)

- 即将上映电影功能
  - 中国/美国各 50 部即将上映电影
  - 数据库存储，每日自动更新（cron）
  - 手动更新按钮
- 电影封面图片
  - 所有清单显示封面缩略图
  - 详情页大图展示
  - 图片代理（公网无需访问 Emby）
- 合集管理优化
  - 合集主行显示海报
  - 合集内电影显示海报
- 电影排名显示
  - IMDB/豆瓣排名数字显示（前 50 加粗）
- 界面优化
  - 侧边栏导航 + 表格优先布局
  - 浅色主题默认
  - 详情页下拉动画
  - 固定列宽，防止展开时跳动

### v2.1.0 (2026-06-16)

- 电影合集管理功能
  - 合集列表（分页、搜索、筛选）
  - 基于 TMDB API 显示未收录电影
  - 数据库缓存，秒级响应
- 电影详情展开功能
  - 所有清单支持点击展开详情
  - 显示导演、演员、简介、编码等
- 分辨率从 path 字段提取
- 位置列显示（movie1/movie2）
- 主题切换功能（6种配色）
- 后端分页和搜索 API

### v2.0.0 (2026-06-15)

- 豆瓣 Top 250 使用 douban_id 作为主键
- 手动关联功能（文件+数据库双备份）
- 后端分页和搜索 API
- 分辨率从 path 字段提取
- 新增位置列显示
- 最低投票数提高到 100,000

### v1.2.0 (2026-06-11)

- 用 Python 重写豆瓣爬虫，移除 Go 依赖
- 优化 IMDB Top 250 脚本内存占用
- 增加容器内存限制到 1GB

### v1.1.0 (2026-06-10)

- 修复数据库连接配置
- 修复日期字段空字符串报错
- 简化 Dockerfile

### v1.0.0 (2026-06-09)

- 初始版本发布
- Emby 电影导出
- IMDB/豆瓣 Top 250 对比
- Web 管理界面
- Docker 部署支持
- GitHub Actions 自动构建

## 📄 许可证

MIT License
