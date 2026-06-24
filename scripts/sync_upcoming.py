#!/usr/bin/env python3
"""
同步即将上映电影到数据库
从 TMDB API 获取中国和美国即将上映的电影，存入数据库
"""
import os
import sys
import json
from datetime import datetime, timedelta

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG, TMDB_API_KEY
from scripts import db
from scripts.movie_utils import build_poster_url


def fetch_upcoming(region, limit=50):
    """从 TMDB 获取即将上映电影"""
    today = datetime.now().strftime("%Y-%m-%d")
    one_year = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

    lang = "zh" if region == "CN" else "en"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "zh-CN",
        "with_original_language": lang,
        "primary_release_date.gte": today,
        "primary_release_date.lte": one_year,
        "sort_by": "popularity.desc",
    }

    all_movies = []
    for page in range(1, 6):
        params["page"] = page
        resp = requests.get(
            "https://api.themoviedb.org/3/discover/movie",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        for m in data.get("results", []):
            all_movies.append({
                "tmdb_id": str(m.get("id", "")),
                "title": m.get("title", ""),
                "original_title": m.get("original_title", ""),
                "release_date": m.get("release_date") or None,
                "rating": m.get("vote_average", 0),
                "popularity": m.get("popularity", 0),
                "overview": m.get("overview", ""),
                "poster_url": build_poster_url(m.get("poster_path", "")) or "",
            })
        if len(data.get("results", [])) < 20:
            break

    # 按上映日期排序
    all_movies.sort(key=lambda x: x.get("release_date") or "9999")
    return all_movies[:limit]


def save_to_db(category, region, movies):
    """保存到数据库"""
    conn = db.get_connection()
    try:
        conn.begin()
        with conn.cursor() as cur:
            # 删除该类别/地区的旧数据
            cur.execute("DELETE FROM upcoming_movies WHERE region = %s AND category = %s", (region, category))
            deleted = cur.rowcount

            # 插入新数据
            sql = """
                INSERT INTO upcoming_movies
                (category, region, tmdb_id, title, original_title, release_date, rating, popularity, overview, poster_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            for m in movies:
                cur.execute(sql, (
                    category,
                    region,
                    m["tmdb_id"],
                    m["title"],
                    m["original_title"],
                    m["release_date"],
                    m["rating"],
                    m["popularity"],
                    m["overview"],
                    m["poster_url"],
                ))

            conn.commit()
            print(f"  {region}/{category}: 删除 {deleted} 条，插入 {len(movies)} 条")
    except Exception as e:
        conn.rollback()
        print(f"  {region}/{category}: 写入失败，已回滚: {e}")
        raise
    finally:
        conn.close()


def fetch_now_playing(region, limit=50):
    """从 TMDB 获取正在上映电影"""
    params = {
        "api_key": TMDB_API_KEY,
        "language": "zh-CN",
        "region": region,
    }

    all_movies = []
    for page in range(1, 4):
        params["page"] = page
        resp = requests.get(
            "https://api.themoviedb.org/3/movie/now_playing",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        for m in data.get("results", []):
            all_movies.append({
                "tmdb_id": str(m.get("id", "")),
                "title": m.get("title", ""),
                "original_title": m.get("original_title", ""),
                "release_date": m.get("release_date") or None,
                "rating": m.get("vote_average", 0),
                "popularity": m.get("popularity", 0),
                "overview": m.get("overview", ""),
                "poster_url": build_poster_url(m.get("poster_path", "")) or "",
            })
        if len(data.get("results", [])) < 20:
            break

    # 按热度排序
    all_movies.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    return all_movies[:limit]


def sync_upcoming():
    """同步即将上映和正在上映电影"""
    if not TMDB_API_KEY:
        print("错误：未配置 TMDB API Key")
        return

    print("同步电影数据...")

    for region in ["CN", "US"]:
        # 即将上映
        print(f"\n获取 {region} 即将上映电影...")
        try:
            movies = fetch_upcoming(region, limit=50)
            save_to_db("upcoming", region, movies)
        except Exception as e:
            print(f"  {region} 同步失败: {e}")

        # 正在上映
        print(f"\n获取 {region} 正在上映电影...")
        try:
            movies = fetch_now_playing(region, limit=50)
            save_to_db("now_playing", region, movies)
        except Exception as e:
            print(f"  {region} 同步失败: {e}")

    print("\n✅ 同步完成")


if __name__ == "__main__":
    sync_upcoming()
