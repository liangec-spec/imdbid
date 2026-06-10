#!/usr/bin/env python3
"""
从 IMDB 公开数据集动态获取 Top 250 电影
使用贝叶斯加权公式计算排名
内存优化版本：使用流式处理
"""
import csv
import gzip
import io
import os
import sys

import requests
import pymysql

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG, IMDB_DATASETS, DATA_DIR

# 最少投票数（过滤冷门电影）
MIN_VOTES = 25000


def download_and_process_ratings():
    """下载并处理评分数据，只保留符合条件的记录"""
    print(f"下载评分数据...")
    r = requests.get(IMDB_DATASETS["ratings"], timeout=120)
    r.raise_for_status()

    rating_map = {}
    all_ratings = []

    with gzip.open(io.BytesIO(r.content), "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            try:
                votes = int(row.get("numVotes", 0))
                avg = float(row.get("averageRating", 0))
                if votes >= MIN_VOTES:
                    tconst = row["tconst"]
                    rating_map[tconst] = {"rating": avg, "votes": votes}
                    all_ratings.append(avg)
            except (ValueError, TypeError):
                continue

    print(f"  投票数 >= {MIN_VOTES} 的电影: {len(rating_map)} 部")

    # 计算全局平均分 C
    C = sum(all_ratings) / len(all_ratings) if all_ratings else 0
    print(f"  全局平均分 C = {C:.2f}")

    return rating_map, C


def process_basics_and_rank(rating_map, C):
    """流式处理 basics 数据，计算加权评分"""
    print(f"下载 basics 数据...")
    r = requests.get(IMDB_DATASETS["basics"], timeout=120)
    r.raise_for_status()

    m = MIN_VOTES
    movies = []

    with gzip.open(io.BytesIO(r.content), "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row.get("titleType") != "movie":
                continue

            tid = row.get("tconst", "")
            if tid not in rating_map:
                continue

            R = rating_map[tid]["rating"]
            v = rating_map[tid]["votes"]
            WR = (v / (v + m)) * R + (m / (v + m)) * C

            movies.append({
                "imdb_id": tid,
                "title": row.get("primaryTitle", ""),
                "original_title": row.get("originalTitle", ""),
                "year": row.get("startYear", ""),
                "rating": R,
                "votes": v,
                "weighted_rating": round(WR, 4),
            })

    # 按加权评分排序，取前 250
    movies.sort(key=lambda x: (-x["weighted_rating"], -x["votes"]))
    top250 = movies[:250]

    # 添加排名
    for i, movie in enumerate(top250):
        movie["ranking"] = i + 1

    print(f"  Top 250 已生成，评分范围: {top250[-1]['rating']} ~ {top250[0]['rating']}")
    return top250


def save_to_csv(movies, filename):
    """保存到 CSV"""
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ranking", "title", "imdb_id", "rating", "votes", "year"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(movies)
    print(f"已保存到 {filename}")


def save_to_mysql(movies):
    """写入 MySQL"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM imdb_top250")
            deleted = cur.rowcount

            sql = "INSERT INTO imdb_top250 (title, imdb_id) VALUES (%s, %s)"
            for m in movies:
                cur.execute(sql, (m["title"], m["imdb_id"]))

            conn.commit()
            print(f"MySQL: 删除旧记录 {deleted} 条，插入新记录 {len(movies)} 条")
    finally:
        conn.close()


def main():
    # 流式处理，减少内存占用
    rating_map, C = download_and_process_ratings()

    # 释放不需要的数据
    import gc
    gc.collect()

    movies = process_basics_and_rank(rating_map, C)

    # 打印前 10
    print("\n--- Top 10 ---")
    for m in movies[:10]:
        print(f"{m['ranking']:>3}. {m['title']:<45} {m['imdb_id']}  ⭐{m['rating']}  ({m['votes']}票)")

    csv_path = os.path.join(DATA_DIR, "imdb_top250.csv")
    save_to_csv(movies, csv_path)
    save_to_mysql(movies)


if __name__ == "__main__":
    main()
