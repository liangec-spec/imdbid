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
    genres VARCHAR(255) COMMENT '类型',
    studios VARCHAR(255) COMMENT '制片厂',
    countries VARCHAR(255) COMMENT '国家',
    directors VARCHAR(255) COMMENT '导演',
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
    official_rating VARCHAR(20) COMMENT '分级',
    production_year INT COMMENT '制作年份',
    imdb_rating DECIMAL(3,1) COMMENT 'IMDB 评分',
    imdb_votes INT COMMENT 'IMDB 投票数',
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
    ranking INT COMMENT '排名',
    title VARCHAR(255) COMMENT '电影名称',
    douban_link VARCHAR(255) COMMENT '豆瓣链接',
    imdb_id VARCHAR(20) COMMENT 'IMDB ID',
    INDEX idx_imdb_id (imdb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='豆瓣 Top 250';
