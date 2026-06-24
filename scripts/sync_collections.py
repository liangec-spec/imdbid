#!/usr/bin/env python3
"""
同步 Emby 电影合集到数据库
从 Emby API 获取合集数据，从 TMDB 获取完整电影列表，对比 Emby 库找出未收录电影
"""
import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG, EMBY_CONFIG, TMDB_API_KEY
from scripts import db
from scripts.movie_utils import parse_collection_movie, build_poster_url

EMBY_COLLECTIONS_PARENT_ID = os.getenv("EMBY_COLLECTIONS_PARENT_ID", "43626")


def get_emby_collections(server, api_key):
    """从 Emby 获取合集列表"""
    print("从 Emby 获取合集列表...")
    resp = requests.get(
        f"{server}/Items",
        params={
            "ParentId": EMBY_COLLECTIONS_PARENT_ID,
            "Recursive": "true",
            "Fields": "Name,ProviderIds,ChildCount,Overview",
            "api_key": api_key,
            "Limit": 200,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    collections = []
    for item in data.get("Items", []):
        collections.append({
            "emby_id": item.get("Id"),
            "name": item.get("Name", ""),
            "tmdb_id": item.get("ProviderIds", {}).get("Tmdb", ""),
            "child_count": item.get("ChildCount", 0),
            "overview": item.get("Overview", ""),
        })
    print(f"  获取 {len(collections)} 个合集")
    return collections


def get_emby_collection_movies(server, api_key, collection_id):
    """从 Emby 获取合集内的电影"""
    resp = requests.get(
        f"{server}/Items",
        params={
            "ParentId": collection_id,
            "Fields": "Name,OriginalTitle,ProductionYear,ProviderIds,CommunityRating,Overview,Genres,People,MediaSources,MediaStreams",
            "api_key": api_key,
            "Limit": 100,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    movies = []
    for item in data.get("Items", []):
        movies.append(parse_collection_movie(item))
    return movies


def get_tmdb_collection_movies(tmdb_id):
    """从 TMDB 获取合集完整电影列表"""
    # 验证 tmdb_id 是数字
    if not tmdb_id or not tmdb_id.isdigit():
        return [], None

    resp = requests.get(
        f"https://api.themoviedb.org/3/collection/{tmdb_id}",
        params={"api_key": TMDB_API_KEY, "language": "zh-CN"},
        timeout=15,
    )
    if resp.status_code == 404:
        return [], None
    resp.raise_for_status()
    data = resp.json()

    # 合集海报
    poster_url = build_poster_url(data.get("poster_path", ""))

    movies = []
    for part in data.get("parts", []):
        movies.append({
            "tmdb_id": str(part.get("id", "")),
            "name": part.get("title", ""),
            "original_title": part.get("original_title", ""),
            "year": int(part.get("release_date", "")[:4]) if part.get("release_date") else None,
            "rating": part.get("vote_average"),
            "overview": part.get("overview", ""),
            "poster_url": build_poster_url(part.get("poster_path", "")) or "",
            "in_emby": False,
        })
    return movies, poster_url


def sync_collections():
    """同步合集数据到数据库"""
    server = EMBY_CONFIG["server"]
    api_key = EMBY_CONFIG["api_key"]

    if not server or not api_key:
        print("错误：未配置 Emby 服务器")
        return

    # 获取 Emby 合集
    collections = get_emby_collections(server, api_key)

    conn = db.get_connection()
    try:
        conn.begin()
        with conn.cursor() as cur:
            # 清空旧数据
            cur.execute("DELETE FROM emby_collection_movies")
            cur.execute("DELETE FROM emby_collections")

            for col in collections:
                emby_id = col["emby_id"]
                tmdb_id = col["tmdb_id"] if col["tmdb_id"] and col["tmdb_id"].isdigit() else None

                print(f"\n处理合集: {col['name']}")

                # 获取 Emby 中的电影
                emby_movies = get_emby_collection_movies(server, api_key, emby_id)
                emby_tmdb_ids = {m["tmdb_id"] for m in emby_movies if m["tmdb_id"]}

                # 获取 TMDB 完整列表
                tmdb_movies = []
                collection_poster = None
                if tmdb_id:
                    try:
                        tmdb_movies, collection_poster = get_tmdb_collection_movies(tmdb_id)
                    except Exception as e:
                        print(f"  TMDB API 错误: {e}")

                # 合并数据：Emby 中的 + TMDB 中未收录的
                all_movies = []
                for m in emby_movies:
                    all_movies.append(m)

                missing_count = 0
                for tmdb_m in tmdb_movies:
                    if tmdb_m["tmdb_id"] not in emby_tmdb_ids:
                        all_movies.append(tmdb_m)
                        missing_count += 1

                # 插入合集
                cur.execute(
                    """INSERT INTO emby_collections
                    (emby_id, name, tmdb_id, child_count, total_count, missing_count, overview, poster_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (emby_id, col["name"], tmdb_id, col["child_count"],
                     len(tmdb_movies), missing_count, col["overview"], collection_poster)
                )

                # 获取刚插入的合集 ID
                cur.execute("SELECT id FROM emby_collections WHERE emby_id = %s", (emby_id,))
                collection_db_id = cur.fetchone()[0]

                # 插入电影
                for m in all_movies:
                    cur.execute(
                        """INSERT INTO emby_collection_movies
                        (collection_id, tmdb_id, name, original_title, year, rating,
                         imdb_rating, imdb_votes, imdb_id, overview, genres, directors,
                         actors, studios, video_codec, audio_codec, size, video_resolution,
                         path, in_emby, poster_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (collection_db_id, m.get("tmdb_id"), m.get("name"), m.get("original_title"),
                         m.get("year"), m.get("rating"), m.get("imdb_rating"), m.get("imdb_votes"),
                         m.get("imdb_id"), m.get("overview"), m.get("genres"), m.get("directors"),
                         m.get("actors"), m.get("studios"), m.get("video_codec"), m.get("audio_codec"),
                         m.get("size"), m.get("video_resolution"), m.get("path"),
                         1 if m.get("in_emby") else 0, m.get("poster_url"))
                    )

                print(f"  已收录: {len(emby_movies)}, 未收录: {missing_count}")

            conn.commit()
            print(f"\n✅ 同步完成，共 {len(collections)} 个合集")
    except Exception as e:
        conn.rollback()
        print(f"同步失败，已回滚: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    sync_collections()
