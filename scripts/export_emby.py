#!/usr/bin/env python3
"""
Emby 电影导出工具
从 Emby 服务器获取电影数据，匹配 IMDB 评分，保存到 CSV 和 MySQL
"""
import csv
import gzip
import io
import json
import os
import sys
import argparse
from typing import List, Dict

import requests
import pymysql

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG, EMBY_CONFIG, EXPORT_FIELDS, IMDB_DATASETS, DATA_DIR

# Emby API 可获取的字段
EMBY_API_FIELDS = [
    "Name", "OriginalTitle", "ProductionYear", "OfficialRating", "Overview",
    "ReleaseDate", "RuntimeTicks", "CommunityRating", "VoteCount", "Genres",
    "Studios", "TagItems", "People", "MediaSources", "Path", "DateCreated",
    "DateModified", "ProviderIds", "VideoBitrate", "AudioBitrate", "Container",
    "VideoCodec", "AudioCodec", "VideoResolution", "MediaStreams", "Size"
]


def download_imdb_ratings() -> Dict:
    """从 IMDB 公开数据集下载评分数据"""
    print("正在下载 IMDB 评分数据集...")
    r = requests.get(IMDB_DATASETS["ratings"], timeout=120)
    r.raise_for_status()

    rating_map = {}
    with gzip.open(io.BytesIO(r.content), "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            try:
                tconst = row.get("tconst", "")
                avg = float(row.get("averageRating", 0))
                votes = int(row.get("numVotes", 0))
                if tconst:
                    rating_map[tconst] = {"rating": avg, "votes": votes}
            except (ValueError, TypeError):
                continue

    print(f"已读取 {len(rating_map)} 条 IMDB 评分记录")
    return rating_map


def get_all_movies(server: str, api_key: str, parent_id: str) -> List[Dict]:
    """从 Emby 服务器获取所有电影"""
    movies = []
    start_index = 0
    page_size = 100

    while True:
        url = f"{server}/Items"
        params = {
            "ParentId": parent_id,
            "IncludeItemTypes": "Movie",
            "Recursive": "true",
            "Fields": ",".join(EMBY_API_FIELDS),
            "StartIndex": start_index,
            "Limit": page_size,
            "api_key": api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            items = data.get("Items", [])
            if not items:
                break

            for item in items:
                movies.append(parse_movie(item, server))

            start_index += page_size
            if len(items) < page_size:
                break
            print(f"已获取 {len(movies)} 条电影数据...")

        except Exception as e:
            print(f"请求出错: {e}")
            break

    return movies


def parse_movie(item: Dict, server: str = "") -> Dict:
    """解析 Emby 返回的电影数据"""
    provider_ids = item.get("ProviderIds", {})
    media_sources = item.get("MediaSources", [{}])[0] if item.get("MediaSources") else {}
    video_stream = next((s for s in item.get("MediaStreams", []) if s.get("Type") == "Video"), {})
    audio_stream = next((s for s in item.get("MediaStreams", []) if s.get("Type") == "Audio"), {})

    # 处理演职人员
    people = item.get("People", [])
    directors = [p.get("Name") for p in people if p.get("Type") == "Director"]
    actors = [p.get("Name") for p in people if p.get("Type") == "Actor"]

    # 处理国家（从 TagItems 中筛选类型为 Country 的）
    tag_items = item.get("TagItems", [])
    countries = [t.get("Name") for t in tag_items if t.get("Type") == "Country"]
    tags = [t.get("Name") for t in tag_items if t.get("Type") != "Country"]

    # 处理时长
    runtime_ticks = item.get("RuntimeTicks", 0)
    runtime_minutes = int(runtime_ticks / 600000000) if runtime_ticks else 0

    # 处理日期（空字符串转为 None，否则 MySQL DATE 类型报错）
    release_date = item.get("ReleaseDate", "")
    release_date = release_date.split("T")[0] if release_date else None

    date_created = item.get("DateCreated", "")
    date_created = date_created.split("T")[0] if date_created else None

    date_modified = item.get("DateModified", "")
    date_modified = date_modified.split("T")[0] if date_modified else None

    imdb_id = provider_ids.get("Imdb", "")

    # 生成封面 URL
    image_tags = item.get("ImageTags", {})
    primary_tag = image_tags.get("Primary", "")
    emby_id = item.get("Id", "")
    poster_url = f"{server}/Items/{emby_id}/Images/Primary?tag={primary_tag}" if primary_tag and server else ""

    return {
        "title": item.get("Name", ""),
        "original_title": item.get("OriginalTitle", ""),
        "year": item.get("ProductionYear", ""),
        "production_year": item.get("ProductionYear", ""),
        "official_rating": item.get("OfficialRating", ""),
        "imdb_id": imdb_id,
        "imdb_url": f"https://www.imdb.com/title/{imdb_id}" if imdb_id else "",
        "tmdb_id": provider_ids.get("Tmdb", ""),
        "rating": item.get("CommunityRating", ""),
        "community_rating": item.get("CommunityRating", ""),
        "vote_count": item.get("VoteCount", ""),
        "runtime": runtime_minutes,
        "overview": item.get("Overview", "").replace("\n", " ").replace("\r", " "),
        "release_date": release_date,
        "genres": "|".join(item.get("Genres", [])),
        "studios": "|".join([s.get("Name") for s in item.get("Studios", [])]),
        "countries": "|".join(countries),
        "directors": "|".join(directors),
        "actors": "|".join(actors[:10]),
        "path": media_sources.get("Path", ""),
        "size": media_sources.get("Size", ""),
        "container": media_sources.get("Container", ""),
        "video_codec": video_stream.get("Codec", ""),
        "audio_codec": audio_stream.get("Codec", ""),
        "video_resolution": f"{video_stream.get('Width', '')}x{video_stream.get('Height', '')}" if video_stream.get("Width") else "",
        "date_added": date_created,
        "date_modified": date_modified,
        "tags": "|".join(tags),
        "imdb_rating": "",
        "imdb_votes": "",
        "poster_url": poster_url,
    }


def save_to_csv(movies: List[Dict], filename: str):
    """保存到 CSV"""
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(movies)
    print(f"\n导出完成！共 {len(movies)} 条电影数据，已保存到 {filename}")


def save_to_mysql(movies: List[Dict]):
    """写入 MySQL"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM emby_movies")
            deleted = cur.rowcount

            sql = """INSERT INTO emby_movies (
                title, original_title, year, imdb_id, imdb_url, tmdb_id,
                rating, community_rating, vote_count, runtime, overview,
                release_date, genres, studios, countries, directors, actors,
                path, size, container, video_codec, audio_codec, video_resolution,
                date_added, date_modified, tags, official_rating, production_year,
                imdb_rating, imdb_votes, poster_url
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )"""

            def val(v):
                return v if v != "" else None

            for m in movies:
                cur.execute(sql, (
                    m.get("title"), m.get("original_title"), val(m.get("year")),
                    m.get("imdb_id"), m.get("imdb_url"), m.get("tmdb_id"),
                    val(m.get("rating")), val(m.get("community_rating")), val(m.get("vote_count")),
                    val(m.get("runtime")), m.get("overview"), m.get("release_date"),
                    m.get("genres"), m.get("studios"), m.get("countries"),
                    m.get("directors"), m.get("actors"), m.get("path"),
                    val(m.get("size")), m.get("container"), m.get("video_codec"),
                    m.get("audio_codec"), m.get("video_resolution"),
                    m.get("date_added"), m.get("date_modified"), m.get("tags"),
                    m.get("official_rating"), val(m.get("production_year")),
                    val(m.get("imdb_rating")), val(m.get("imdb_votes")),
                    m.get("poster_url") or None,
                ))

            conn.commit()
            print(f"已写入 MySQL：删除旧记录 {deleted} 条，插入新记录 {len(movies)} 条")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Emby 电影导出工具")
    parser.add_argument("--output", "-o", default=os.path.join(DATA_DIR, "emby_movies.csv"), help="输出 CSV 路径")
    parser.add_argument("--server", "-s", help="Emby 服务器地址")
    parser.add_argument("--apikey", "-k", help="Emby API 密钥")
    parser.add_argument("--parentid", "-p", help="媒体库 ID")
    parser.add_argument("--mysql", "-m", action="store_true", help="同时写入 MySQL")
    parser.add_argument("--no-imdb", action="store_true", help="不获取 IMDB 评分")

    args = parser.parse_args()

    # 使用命令行参数或环境变量
    server = args.server or EMBY_CONFIG["server"]
    api_key = args.apikey or EMBY_CONFIG["api_key"]
    parent_id = args.parentid or EMBY_CONFIG["parent_id"]

    if not api_key:
        print("错误：未设置 Emby API Key，请通过 --apikey 参数或 EMBY_API_KEY 环境变量设置")
        sys.exit(1)

    if not parent_id:
        print("错误：未设置媒体库 ID，请通过 --parentid 参数或 EMBY_PARENT_ID 环境变量设置")
        sys.exit(1)

    print("=== Emby 电影导出工具 ===")
    print(f"服务器: {server}")
    print(f"媒体库 ID: {parent_id}")
    print()

    # 获取电影数据
    movies = get_all_movies(server, api_key, parent_id)
    if not movies:
        print("未获取到任何电影数据")
        return

    # 获取 IMDB 评分
    if not args.no_imdb:
        try:
            rating_map = download_imdb_ratings()
            matched = 0
            for movie in movies:
                imdb_id = movie.get("imdb_id", "").strip()
                if imdb_id and imdb_id in rating_map:
                    movie["imdb_rating"] = str(rating_map[imdb_id]["rating"])
                    movie["imdb_votes"] = str(rating_map[imdb_id]["votes"])
                    matched += 1
            print(f"已匹配 {matched}/{len(movies)} 部电影的 IMDB 评分")
        except Exception as e:
            print(f"获取 IMDB 评分失败: {e}")

    # 保存结果
    save_to_csv(movies, args.output)
    if args.mysql:
        save_to_mysql(movies)


if __name__ == "__main__":
    main()
