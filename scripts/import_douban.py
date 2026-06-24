#!/usr/bin/env python3
"""
将豆瓣 Top 250 CSV 导入 MySQL 数据库
用法: python import_douban.py [csv文件路径]
"""
import csv
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG
from scripts import db


def import_csv(csv_path: str):
    """导入豆瓣 Top 250 CSV 到数据库"""
    if not os.path.exists(csv_path):
        print(f"错误：文件不存在: {csv_path}")
        sys.exit(1)

    # 读取 CSV
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"读取 CSV: {len(rows)} 条记录")

    # 写入 MySQL
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM douban_top250")
            deleted = cur.rowcount

            sql = "INSERT INTO douban_top250 (ranking, title, douban_link, imdb_id) VALUES (%s, %s, %s, %s)"
            for r in rows:
                imdb_id = r.get("IMDB ID", "").strip()
                cur.execute(sql, (
                    int(r["排名"]),
                    r["电影名称"],
                    r["豆瓣链接"],
                    imdb_id if imdb_id else None,
                ))

            conn.commit()
            print(f"MySQL: 删除旧记录 {deleted} 条，插入新记录 {len(rows)} 条")
    except Exception as e:
        conn.rollback()
        print(f"MySQL: 写入失败，已回滚: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "douban-scraper/top250.csv"
    import_csv(csv_path)
