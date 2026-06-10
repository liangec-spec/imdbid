"""
集中配置模块
支持环境变量覆盖，敏感信息不硬编码
"""
import os

# 数据库配置
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "douban_top250"),
    "charset": "utf8mb4",
}

# Emby 服务器配置
EMBY_CONFIG = {
    "server": os.getenv("EMBY_SERVER", "http://localhost:8096"),
    "api_key": os.getenv("EMBY_API_KEY", ""),
    "parent_id": os.getenv("EMBY_PARENT_ID", ""),
}

# IMDB 数据集 URL
IMDB_DATASETS = {
    "ratings": "https://datasets.imdbws.com/title.ratings.tsv.gz",
    "basics": "https://datasets.imdbws.com/title.basics.tsv.gz",
}

# Emby 导出字段
EXPORT_FIELDS = [
    "title", "original_title", "year", "imdb_id", "imdb_url", "tmdb_id",
    "rating", "community_rating", "vote_count", "runtime", "overview",
    "release_date", "genres", "studios", "countries", "directors", "actors",
    "path", "size", "container", "video_codec", "audio_codec", "video_resolution",
    "date_added", "date_modified", "tags", "official_rating", "production_year",
    "imdb_rating", "imdb_votes",
]

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据目录
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
