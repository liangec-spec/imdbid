# 🎬 Emby 电影管理系统

管理 Emby 媒体库，对比 IMDB/豆瓣 Top 250，展示 IMDB 评分，管理电影合集。

## ✨ 功能

- **Emby 电影导出** — 从 Emby 服务器批量导出电影元数据
- **IMDB Top 250 对比** — 使用贝叶斯加权公式计算排名（最低 100,000 票）
- **豆瓣 Top 250 对比** — 自动检测缺失电影，支持手动关联 IMDB ID
- **IMDB 评分获取** — 从 IMDB 公开数据集批量获取评分（匹配率 99.9%）
- **电影合集管理** — 展示 Emby 合集，显示未收录电影（基于 TMDB）
- **即将/正在上映** — 中国/美国各 50 部电影
- **Web 管理界面** — 搜索、筛选、排序、分页、主题切换、实时操作日志
- **Docker 部署** — 一键部署到生产环境

## 📁 项目结构

```text
imdbid/
├── config/                     # 集中配置
│   └── __init__.py
├── scripts/                    # 脚本工具
│   ├── db.py                   # 共享数据库模块（连接池）
│   ├── movie_utils.py          # 共享电影工具函数
│   ├── backup_db.sh            # 数据库备份脚本
│   ├── export_emby.py          # Emby 导出（含 IMDB 评分）
│   ├── fetch_imdb_top250.py    # IMDB Top 250 获取
│   ├── fetch_douban_top250.py  # 豆瓣 Top 250 爬虫
│   ├── import_douban.py        # 豆瓣数据导入
│   ├── sync_collections.py     # 电影合集同步
│   └── sync_upcoming.py        # 即将/正在上映同步
├── web/                        # Web 管理界面
│   ├── app.py                  # Flask 后端
│   ├── safe_order.py           # ORDER BY 白名单映射
│   └── templates/
│       └── index.html          # 单页前端（SPA）
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
├── start-dev.sh                # 本地开发启动脚本
├── README_DEV.md               # 本地开发指南
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

详见 `README_DEV.md`

```bash
# 安装依赖
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env && vi .env

# 启动开发服务器
./start-dev.sh
```

## ⚙️ 配置项说明

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
| ---- | ---- | ------ | ---- |
| `EMBY_SERVER` | ✅ | --- | Emby 服务器地址 |
| `EMBY_API_KEY` | ✅ | --- | Emby API 密钥 |
| `EMBY_PARENT_ID` | ✅ | --- | 电影媒体库 ID |
| `DB_PASSWORD` | ✅ | --- | MySQL root 密码 |
| `DB_HOST` | ❌ | localhost | 数据库地址 |
| `DB_USER` | ❌ | root | 数据库用户 |
| `DB_NAME` | ❌ | douban_top250 | 数据库名 |
| `EMBY_COLLECTIONS_PARENT_ID` | ❌ | 43626 | 合集媒体库 ID |
| `TMDB_API_KEY` | ❌ | --- | TMDB API Key（合集和即将上映功能需要） |

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

- **后端**: Python 3.12, Flask, Gunicorn, PyMySQL, DBUtils（连接池）
- **前端**: HTML5, CSS3, JavaScript（原生 SPA，无框架）
- **数据库**: MySQL 8.0
- **数据源**: Emby API, IMDB 公开数据集, TMDB API v3, 豆瓣爬虫
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
- 搜索（电影名称、原始标题、IMDB ID）
- 排序（名称、年份、IMDB 评分/投票数、加入日期）
- 筛选（全部、仅 IMDB 250、仅豆瓣 250、两者都在）
- 点击展开详情（支持平滑动画展开/收起）
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
- 支持深色/亮色主题

### 管理页面

- 数据总览：Emby 电影总数、IMDB/豆瓣 Top 250 缺失数、合集数
- 一键更新按钮：Emby 清单、IMDB 250、豆瓣 250、合集、即将上映
- **实时操作日志**：点击更新后日志区域实时显示脚本执行输出

### 其他特性

- **页面记忆**：刷新后自动恢复到上次浏览的页面
- **侧边栏布局**：Logo 点击返回电影页，管理入口在底部
- **亮色/暗色主题切换**

## 📜 更新日志

### v2.3.1 (2026-06-25)

UI/UX 全面优化 + 批量写入性能提升

#### 🎨 前端优化
- **上映页改为横向轮播**：CN/US 各一行，左右箭头滑动浏览
- **自定义滚动动画**：`requestAnimationFrame` 缓动滚动，替代原生 scroll
- **排序调整**：即将上映按日期从早到晚，正在上映从晚到早
- **无海报占位符**：缺失海报的电影显示 🎬 图标
- **Toast 通知系统**：`alert()` 替换为右下角滑入通知，3 秒自动消失
- **空状态提示**：搜索无结果时显示 🔍 友好提示
- **移动端适配**：轮播按钮 44px 触控优化、表格横向滚动、详情网格自适应
- **行悬停反馈**、导航项间距调优、统计卡片间距调优

#### ⚡ 后端优化
- **批量 INSERT**：`executemany` 覆盖全部 6 个写入脚本（`export_emby`、`fetch_douban_top250`、`fetch_imdb_top250`、`sync_upcoming`、`sync_collections`、`import_douban`）
- **IMDB 内存优化**：删除 `all_ratings` 列表，流式累加计算全局平均分
- **配置抽取**：`MIN_VOTES`、`SCRIPT_TIMEOUT` 等提到 `config/__init__.py`
- **ON DUPLICATE KEY UPDATE**：修复 `(region, tmdb_id)` 唯一约束冲突
- **Fetch upcoming 参数优化**：`with_release_type` 过滤

#### 🐛 Bug 修复
- INNER JOIN 分支缺少 `ir` 联表导致筛选 IMDB/豆瓣时报 SQL 错误
- `replace_string_in_file` 工具对某些文件写入不生效（改用 Python 直接写入）

#### 📦 依赖变更
- 新增 `dbutils>=3.1.0`（连接池）

### v2.3.0 (2026-06-24)

全量优化：安全修复 + 数据完整性 + 代码重构 + 性能优化

#### 🔒 安全修复
- **XSS 修复**：所有 API 数据字段（标题、简介、演职人员等）统一 HTML 转义
- **SQL 注入修复**：ORDER BY 子句使用白名单映射表
- **图片代理校验**：改用 `urlparse` 严格校验 `scheme + netloc`

#### 💾 数据完整性
- 所有 DELETE+INSERT 操作添加事务保护（`begin`/`rollback`）
- Gunicorn 启动修复：`before_request` 懒初始化替代模块级代码
- 路径分隔符兼容：同时支持 Linux（`/`）和 Windows（`\\`）路径

#### 🧹 代码重构
- 新增 `scripts/db.py`：共享数据库层 + DBUtils 连接池（10 连接）
- 新增 `scripts/movie_utils.py`：统一电影解析、海报 URL 构建等工具函数
- 所有脚本统一通过 `db` 模块操作数据库，消除 7 处重复代码
- 清理死代码：`extract_douban_id_from_link` 别名等

#### ⚡ 性能优化
- **IMDB 排名查询提速 25 倍**：嵌套子查询 → `ROW_NUMBER()` 窗口函数 JOIN
- 数据库连接池复用，减少 TCP 建连开销

#### 📝 日志功能
- 实时流式日志：`subprocess.Popen` + `PYTHONUNBUFFERED` 逐行输出
- 管理页面日志区域实时显示脚本执行过程

#### 🎨 前端优化
- 展开详情双向动画（展开/收起均平滑过渡）
- 页面记忆：`localStorage` 保存当前页面，刷新后恢复
- 侧边栏布局优化：Logo 可点击返回电影页

#### 🐛 其他修复
- 豆瓣编辑按钮修复（`showEdit` 改用 DOM API 避免 onclick 转义问题）
- 豆瓣编辑行显示修复（`active` 类缺失导致隐藏）
- 模板缓存问题（`debug=False` 时需重启 Flask 刷新模板）
- 更新后页面不再强制刷新，停留在当前页面
