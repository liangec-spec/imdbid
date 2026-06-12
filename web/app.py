#!/usr/bin/env python3
"""
Emby 电影管理 Web 界面
"""
import os
import sys
import subprocess
import threading

from flask import Flask, render_template, jsonify, request
import pymysql

# 添加项目根目录到 path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
from config import DB_CONFIG

app = Flask(__name__)

# 脚本路径（相对于项目根目录）
SCRIPTS = {
    "emby": os.path.join(PROJECT_ROOT, "scripts", "export_emby.py"),
    "imdb": os.path.join(PROJECT_ROOT, "scripts", "fetch_imdb_top250.py"),
    "douban": os.path.join(PROJECT_ROOT, "scripts", "fetch_douban_top250.py"),
}

# 任务状态（线程安全）
task_status = {"emby": None, "imdb": None, "douban": None}
status_lock = threading.Lock()


def query(sql, args=None):
    """执行数据库查询"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


def update_status(task_name, status, message):
    """线程安全地更新任务状态"""
    with status_lock:
        task_status[task_name] = {"status": status, "message": message}


def run_task(task_name, cmd, cwd=None):
    """后台运行任务"""
    update_status(task_name, "running", "执行中...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=cwd)
        if result.returncode == 0:
            output = result.stdout.strip()
            last_line = output.split("\n")[-1] if output else "完成"
            update_status(task_name, "done", last_line)
        else:
            update_status(task_name, "error", result.stderr[-200:])
    except Exception as e:
        update_status(task_name, "error", str(e))


@app.route("/")
def index():
    # 统计数据
    douban_total = query("SELECT COUNT(*) AS c FROM douban_top250")[0]["c"]
    imdb_total = query("SELECT COUNT(*) AS c FROM imdb_top250")[0]["c"]
    emby_total = query("SELECT COUNT(*) AS c FROM emby_movies")[0]["c"]

    douban_missing_count = query("""
        SELECT COUNT(*) AS c FROM douban_top250 m
        WHERE NOT EXISTS (
            SELECT 1 FROM emby_movies e
            WHERE e.title LIKE CONCAT(m.title, '%')
               OR m.title LIKE CONCAT(e.title, '%')
        )
    """)[0]["c"]

    imdb_missing_count = query("""
        SELECT COUNT(*) AS c FROM imdb_top250 i
        WHERE i.imdb_id NOT IN (SELECT imdb_id FROM emby_movies WHERE imdb_id IS NOT NULL AND imdb_id != '')
    """)[0]["c"]

    return render_template(
        "index.html",
        douban_total=douban_total,
        imdb_total=imdb_total,
        emby_total=emby_total,
        douban_missing_count=douban_missing_count,
        imdb_missing_count=imdb_missing_count,
    )


@app.route("/api/movies")
def api_movies():
    """分页获取电影列表"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("search", "", type=str)
    sort_by = request.args.get("sort_by", "imdb_rating", type=str)
    sort_order = request.args.get("sort_order", "desc", type=str)
    filter_type = request.args.get("filter", "all", type=str)

    # 限制每页数量
    per_page = min(per_page, 100)

    # 构建查询
    where_clauses = []
    params = []

    if search:
        where_clauses.append("(e.title LIKE %s OR e.original_title LIKE %s OR e.imdb_id LIKE %s)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # 排序字段映射
    sort_fields = {
        "title": "e.title",
        "year": "e.year",
        "rating": "e.rating",
        "imdb_rating": "e.imdb_rating",
        "imdb_votes": "e.imdb_votes",
    }
    order_field = sort_fields.get(sort_by, "e.imdb_rating")
    order_dir = "DESC" if sort_order == "desc" else "ASC"

    # 构建篩选 JOIN 和 WHERE
    if filter_type in ("imdb", "both"):
        imdb_join = "INNER JOIN imdb_top250 i ON e.imdb_id = i.imdb_id"
    else:
        imdb_join = "LEFT JOIN imdb_top250 i ON e.imdb_id = i.imdb_id"

    douban_filter = ""
    if filter_type in ("douban", "both"):
        douban_filter = """AND EXISTS (
            SELECT 1 FROM douban_top250 m
            WHERE m.title LIKE CONCAT(e.title, '%%') OR e.title LIKE CONCAT(m.title, '%%')
        )"""

    # 获取总数
    count_sql = "SELECT COUNT(*) AS total FROM emby_movies e {} WHERE {} {}".format(imdb_join, where_sql, douban_filter)
    total = query(count_sql, params)[0]["total"]

    # 获取分页数据
    offset = (page - 1) * per_page

    data_sql = """
        SELECT
            e.title, e.original_title, e.year, e.imdb_id, e.rating,
            e.imdb_rating, e.imdb_votes,
            e.genres, e.directors, e.video_resolution,
            CASE
                WHEN CAST(SUBSTRING_INDEX(e.video_resolution, 'x', 1) AS UNSIGNED) >= 3000 THEN '4K'
                WHEN CAST(SUBSTRING_INDEX(e.video_resolution, 'x', 1) AS UNSIGNED) >= 1000 THEN '1080p'
                WHEN CAST(SUBSTRING_INDEX(e.video_resolution, 'x', 1) AS UNSIGNED) >= 700 THEN '720p'
                ELSE IFNULL(e.video_resolution, '-')
            END AS resolution_label,
            CASE WHEN i.imdb_id IS NOT NULL THEN 1 ELSE 0 END AS in_imdb250,
            CASE WHEN EXISTS (
                SELECT 1 FROM douban_top250 m
                WHERE m.title LIKE CONCAT(e.title, '%%')
                   OR e.title LIKE CONCAT(m.title, '%%')
            ) THEN 1 ELSE 0 END AS in_douban250
        FROM emby_movies e
        {}
        WHERE {} {}
        ORDER BY {} {}
        LIMIT %s OFFSET %s
    """.format(imdb_join, where_sql, douban_filter, order_field, order_dir)
    movies = query(data_sql, params + [per_page, offset])

    return jsonify({
        "movies": movies,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@app.route("/api/movies/missing")
def api_missing_movies():
    """获取缺失电影列表"""
    type = request.args.get("type", "imdb", type=str)

    if type == "douban":
        movies = query("""
            SELECT m.ranking, m.title, m.imdb_id, m.douban_link
            FROM douban_top250 m
            WHERE NOT EXISTS (
                SELECT 1 FROM emby_movies e
                WHERE e.title LIKE CONCAT(m.title, '%')
                   OR m.title LIKE CONCAT(e.title, '%')
            )
            ORDER BY m.ranking
        """)
    else:
        movies = query("""
            SELECT i.imdb_id, i.title
            FROM imdb_top250 i
            WHERE i.imdb_id NOT IN (SELECT imdb_id FROM emby_movies WHERE imdb_id IS NOT NULL AND imdb_id != '')
            ORDER BY i.id
        """)

    return jsonify({"movies": movies})


@app.route("/api/update/emby", methods=["POST"])
def update_emby():
    with status_lock:
        s = task_status.get("emby") or {}
        if s.get("status") == "running":
            return jsonify({"status": "busy", "message": "任务正在执行中"})

    thread = threading.Thread(
        target=run_task,
        args=("emby", [sys.executable, SCRIPTS["emby"], "--mysql"]),
    )
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/update/imdb", methods=["POST"])
def update_imdb():
    with status_lock:
        s = task_status.get("imdb") or {}
        if s.get("status") == "running":
            return jsonify({"status": "busy", "message": "任务正在执行中"})

    thread = threading.Thread(
        target=run_task,
        args=("imdb", [sys.executable, SCRIPTS["imdb"]]),
    )
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/update/douban", methods=["POST"])
def update_douban():
    with status_lock:
        s = task_status.get("douban") or {}
        if s.get("status") == "running":
            return jsonify({"status": "busy", "message": "任务正在执行中"})

    thread = threading.Thread(
        target=run_task,
        args=("douban", [sys.executable, SCRIPTS["douban"]]),
    )
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/status")
def get_status():
    with status_lock:
        return jsonify(task_status)


@app.route("/api/top250")
def api_top250():
    """获取 Top 250 完整列表（包含是否在 Emby 中）"""
    type = request.args.get("type", "imdb", type=str)

    if type == "douban":
        movies = query("""
            SELECT
                m.ranking, m.title, m.douban_link, m.imdb_id,
                CASE WHEN e.imdb_id IS NOT NULL OR e.title IS NOT NULL THEN 1 ELSE 0 END AS in_emby
            FROM douban_top250 m
            LEFT JOIN emby_movies e ON (
                m.imdb_id = e.imdb_id
                OR e.title LIKE CONCAT(m.title, '%%')
                OR m.title LIKE CONCAT(e.title, '%%')
            )
            ORDER BY m.ranking
        """)
    else:
        movies = query("""
            SELECT
                i.title, i.imdb_id,
                e.imdb_rating AS rating,
                CASE WHEN e.imdb_id IS NOT NULL THEN 1 ELSE 0 END AS in_emby
            FROM imdb_top250 i
            LEFT JOIN emby_movies e ON i.imdb_id = e.imdb_id
            ORDER BY e.imdb_rating DESC
        """)

    return jsonify({"movies": movies})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
