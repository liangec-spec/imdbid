-- Emby 电影管理系统 - 数据库结构
-- 数据库名: douban_top250
-- 注意: 数据库由 MySQL Docker 镜像自动创建 (MYSQL_DATABASE 环境变量)

USE douban_top250;

-- Emby 电影表
CREATE TABLE IF NOT EXISTS emby_movies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) COMMENT '中文标题',
    original_title VARCHAR(255) COMMENT '原始标题',
    year INT COMMENT '年份',
    imdb_id VARCHAR(20) COMMENT 'IMDB ID',
    imdb_url VARCHAR(255) COMMENT 'IMDB 链接',
    tmdb_id VARCHAR(20) COMMENT 'TMDB ID',
    rating DECIMAL(3,1) COMMENT 'Emby 评分',
    community_rating DECIMAL(3,1) COMMENT '社区评分',
    vote_count INT COMMENT '投票数',
    runtime INT COMMENT '时长(分钟)',
    overview TEXT COMMENT '简介',
    release_date DATE COMMENT '上映日期',
    genres VARCHAR(500) COMMENT '类型',
    studios VARCHAR(500) COMMENT '制片厂',
    countries VARCHAR(500) COMMENT '国家',
    directors VARCHAR(500) COMMENT '导演',
    actors TEXT COMMENT '演员',
    path TEXT COMMENT '文件路径',
    size BIGINT COMMENT '文件大小',
    container VARCHAR(50) COMMENT '容器格式',
    video_codec VARCHAR(50) COMMENT '视频编码',
    audio_codec VARCHAR(50) COMMENT '音频编码',
    video_resolution VARCHAR(20) COMMENT '分辨率',
    date_added DATE COMMENT '添加日期',
    date_modified DATE COMMENT '修改日期',
    tags VARCHAR(255) COMMENT '标签',
    official_rating VARCHAR(100) COMMENT '分级',
    production_year INT COMMENT '制作年份',
    imdb_rating DECIMAL(3,1) COMMENT 'IMDB 评分',
    imdb_votes INT COMMENT 'IMDB 投票数',
    poster_url VARCHAR(500) COMMENT '封面图片 URL',
    INDEX idx_imdb_id (imdb_id),
    INDEX idx_title (title)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Emby 电影数据';

-- IMDB Top 250 表
CREATE TABLE IF NOT EXISTS imdb_top250 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) COMMENT '电影名称',
    imdb_id VARCHAR(20) NOT NULL COMMENT 'IMDB ID',
    UNIQUE KEY uk_imdb_id (imdb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='IMDB Top 250';

-- 豆瓣 Top 250 表
CREATE TABLE IF NOT EXISTS douban_top250 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    douban_id VARCHAR(20) COMMENT '豆瓣 Subject ID',
    ranking INT COMMENT '排名',
    title VARCHAR(255) COMMENT '电影名称',
    douban_link VARCHAR(255) COMMENT '豆瓣链接',
    imdb_id VARCHAR(20) COMMENT 'IMDB ID',
    UNIQUE KEY uk_douban_id (douban_id),
    INDEX idx_imdb_id (imdb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='豆瓣 Top 250';

-- 豆瓣-IMDB 手动关联映射表
CREATE TABLE IF NOT EXISTS douban_imdb_mapping (
    id INT AUTO_INCREMENT PRIMARY KEY,
    douban_id VARCHAR(20) COMMENT '豆瓣 Subject ID',
    douban_ranking INT NOT NULL COMMENT '豆瓣排名',
    douban_title VARCHAR(255) NOT NULL COMMENT '豆瓣电影名',
    imdb_id VARCHAR(20) NOT NULL COMMENT '关联的 IMDB ID',
    note VARCHAR(500) COMMENT '备注说明',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_douban_id (douban_id),
    INDEX idx_imdb_id (imdb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='豆瓣-IMDB 手动关联映射';

-- 电影合集表
CREATE TABLE IF NOT EXISTS emby_collections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    emby_id VARCHAR(50) NOT NULL COMMENT 'Emby 合集 ID',
    name VARCHAR(255) NOT NULL COMMENT '合集名称',
    tmdb_id VARCHAR(20) COMMENT 'TMDB 合集 ID',
    child_count INT DEFAULT 0 COMMENT 'Emby 中的电影数',
    total_count INT DEFAULT 0 COMMENT 'TMDB 中的电影总数',
    missing_count INT DEFAULT 0 COMMENT '未收录电影数',
    overview TEXT COMMENT '简介',
    poster_url VARCHAR(500) COMMENT '合集海报 URL',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_emby_id (emby_id),
    INDEX idx_tmdb_id (tmdb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='电影合集';

-- 合集电影表
CREATE TABLE IF NOT EXISTS emby_collection_movies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    collection_id INT NOT NULL COMMENT '合集 ID',
    tmdb_id VARCHAR(20) COMMENT 'TMDB 电影 ID',
    name VARCHAR(255) COMMENT '电影名称',
    original_title VARCHAR(255) COMMENT '原始名称',
    year INT COMMENT '年份',
    rating DECIMAL(3,1) COMMENT 'Emby 评分',
    imdb_rating DECIMAL(3,1) COMMENT 'IMDB 评分',
    imdb_votes INT COMMENT 'IMDB 投票数',
    imdb_id VARCHAR(20) COMMENT 'IMDB ID',
    overview TEXT COMMENT '简介',
    genres VARCHAR(500) COMMENT '类型',
    directors VARCHAR(500) COMMENT '导演',
    actors TEXT COMMENT '演员',
    studios VARCHAR(500) COMMENT '制片厂',
    video_codec VARCHAR(50) COMMENT '视频编码',
    audio_codec VARCHAR(50) COMMENT '音频编码',
    size BIGINT COMMENT '文件大小',
    video_resolution VARCHAR(20) COMMENT '分辨率',
    path TEXT COMMENT '文件路径',
    poster_url VARCHAR(500) COMMENT '电影海报 URL',
    in_emby TINYINT(1) DEFAULT 0 COMMENT '是否在 Emby 中',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_collection (collection_id),
    INDEX idx_tmdb_id (tmdb_id),
    INDEX idx_in_emby (in_emby),
    FOREIGN KEY (collection_id) REFERENCES emby_collections(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='合集电影';

-- 即将上映电影表
CREATE TABLE IF NOT EXISTS upcoming_movies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    region VARCHAR(10) NOT NULL COMMENT '地区 (CN/US)',
    tmdb_id VARCHAR(20) NOT NULL COMMENT 'TMDB 电影 ID',
    title VARCHAR(255) COMMENT '中文标题',
    original_title VARCHAR(255) COMMENT '原始标题',
    release_date DATE COMMENT '上映日期',
    rating DECIMAL(3,1) COMMENT '评分',
    popularity DECIMAL(10,4) COMMENT '热度',
    overview TEXT COMMENT '简介',
    poster_url VARCHAR(500) COMMENT '海报 URL',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_region_tmdb (region, tmdb_id),
    INDEX idx_region (region),
    INDEX idx_release_date (release_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='即将上映电影';
