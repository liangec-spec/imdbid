#!/usr/bin/env python3
"""
豆瓣 Top 250 爬虫
爬取豆瓣电影 Top 250 列表，并通过 IMDB Suggestion API 获取 IMDB ID
"""
import csv
import json
import os
import re
import sys
import time
from urllib.parse import quote

import requests

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG, DATA_DIR

import pymysql

BASE_URL = "https://movie.douban.com/top250"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://movie.douban.com/",
}

client = requests.Session()
client.headers.update(HEADERS)


def fetch_top250_list():
    """爬取豆瓣 Top 250 列表"""
    movies = [None] * 250

    for start in range(0, 250, 25):
        url = f"{BASE_URL}?start={start}&filter="
        print(f"爬取列表: {url}")

        try:
            resp = client.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"请求失败: {e}")
            continue

        # 解析 HTML
        # 实际结构:
        # <div class="pic">
        #     <em>1</em>
        #     <a href="https://movie.douban.com/subject/1292052/">
        #         <img ... alt="肖申克的救赎" ...>
        #     </a>
        # </div>

        items = re.findall(
            r'<em>(\d+)</em>.*?<a href="(https://movie\.douban\.com/subject/\d+/)".*?alt="(.*?)"',
            resp.text,
            re.DOTALL
        )

        for rank_str, link, name in items:
            rank = int(rank_str)
            if 1 <= rank <= 250:
                movies[rank - 1] = {"name": name, "link": link, "imdb_id": ""}

        time.sleep(1)  # 避免请求过快

    return [m for m in movies if m is not None]


def extract_douban_id(link):
    """从豆瓣链接提取 subject ID"""
    match = re.search(r"/subject/(\d+)", link)
    return match.group(1) if match else ""


def get_douban_info(douban_id):
    """通过豆瓣 API 获取英文片名和年份"""
    api_url = f"https://movie.douban.com/j/subject_abstract?subject_id={douban_id}"

    try:
        resp = client.get(api_url, timeout=15)
        data = resp.json()
    except Exception:
        return "", ""

    title = data.get("subject", {}).get("title", "")
    year = data.get("subject", {}).get("release_year", "")

    # 提取英文名
    en_title = extract_english_title(title)
    return en_title, year


def extract_english_title(title):
    """从 '中文 English Name (年份)' 中提取英文名"""
    # 去掉年份部分
    title = re.sub(r"\s*[\(（]\d{4}[\)）]\s*$", "", title)

    # 提取英文字母部分
    matches = re.findall(r"[A-Za-z][A-Za-z\s\:\'\-\!\.]+", title)
    if not matches:
        return ""

    # 取最长的英文片段
    longest = ""
    for m in matches:
        m = m.strip()
        if len(m) > len(longest):
            longest = m

    return longest.strip()


def search_imdb(title, year):
    """通过 IMDB Suggestion API 搜索 IMDB ID"""
    # 清理标题
    query = title.lower().replace(" ", "_").replace(":", "").replace("'", "").replace("-", "_").replace(".", "")

    if not query:
        return ""

    first_char = query[0]
    api_url = f"https://v2.sg.media-imdb.com/suggestion/{first_char}/{quote(query)}.json"

    try:
        resp = requests.get(api_url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=15)
        data = resp.json()
    except Exception:
        return ""

    # 匹配年份
    target_year = int(year) if year.isdigit() else 0
    title_lower = title.lower()

    best_match = ""
    best_score = 0

    for item in data.get("d", []):
        item_id = item.get("id", "")
        if not item_id.startswith("tt"):
            continue

        score = 0
        item_title_lower = item.get("l", "").lower()

        # 标题相似度
        if item_title_lower == title_lower:
            score += 100
        elif title_lower in item_title_lower or item_title_lower in title_lower:
            score += 50

        # 年份匹配
        item_year = item.get("y", 0)
        if target_year > 0 and item_year == target_year:
            score += 80
        elif target_year > 0 and abs(item_year - target_year) <= 1:
            score += 30

        if score > best_score:
            best_score = score
            best_match = item_id

    return best_match if best_score >= 50 else ""


def save_to_csv(movies, filename):
    """保存到 CSV"""
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["排名", "电影名称", "豆瓣链接", "IMDB ID"])
        for i, movie in enumerate(movies, 1):
            writer.writerow([i, movie["name"], movie["link"], movie["imdb_id"]])
    print(f"\n✅ 已导出到 {filename}")


def save_to_mysql(movies):
    """写入 MySQL"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM douban_top250")
            deleted = cur.rowcount

            sql = "INSERT INTO douban_top250 (ranking, title, douban_link, imdb_id) VALUES (%s, %s, %s, %s)"
            for i, movie in enumerate(movies, 1):
                imdb_id = movie["imdb_id"] if movie["imdb_id"] else None
                cur.execute(sql, (i, movie["name"], movie["link"], imdb_id))

            conn.commit()
            print(f"MySQL: 删除旧记录 {deleted} 条，插入新记录 {len(movies)} 条")
    finally:
        conn.close()


def main():
    print("=== 豆瓣 Top 250 爬虫 ===\n")

    # 第一步：爬取列表
    print("第一步：爬取豆瓣 Top 250 列表...")
    movies = fetch_top250_list()
    print(f"✅ 成功爬取 {len(movies)} 部电影\n")

    # 第二步：获取 IMDB ID
    print("第二步：获取 IMDB ID...")
    success_count = 0
    for i, movie in enumerate(movies):
        print(f"  [{i+1}/{len(movies)}] {movie['name']} ... ", end="", flush=True)

        douban_id = extract_douban_id(movie["link"])
        if not douban_id:
            print("无法提取豆瓣 ID")
            continue

        en_title, year = get_douban_info(douban_id)
        if not en_title:
            print("无法获取英文片名")
            continue

        imdb_id = search_imdb(en_title, year)
        if imdb_id:
            movie["imdb_id"] = imdb_id
            print(f"IMDB: {imdb_id}")
            success_count += 1
        else:
            print("IMDB: 未找到")

        time.sleep(0.5)  # 避免请求过快

    print(f"\n✅ 成功获取 {success_count}/{len(movies)} 部电影的 IMDB ID\n")

    # 第三步：保存结果
    csv_path = os.path.join(DATA_DIR, "douban_top250.csv")
    save_to_csv(movies, csv_path)
    save_to_mysql(movies)


if __name__ == "__main__":
    main()
