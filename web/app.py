#!/usr/bin/env python3
"""
Emby 电影管理 Web 界面
"""
import os
import sys
import subprocess
import threading

from flask import Flask, render_template, jsonify
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
    "douban_bin": os.path.join(PROJECT_ROOT, "douban-scraper", "douban-scraper"),
    "douban_import": os.path.join(PROJECT_ROOT, "scripts", "import_douban.py"),
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
    douban_missing = query("""
        SELECT m.ranking, m.title, m.imdb_id, m.douban_link
        FROM douban_top250 m
        WHERE NOT EXISTS (
            SELECT 1 FROM emby_movies e
            WHERE e.title LIKE CONCAT(m.title, '%')
               OR m.title LIKE CONCAT(e.title, '%')
        )
        ORDER BY m.ranking
    """)

    imdb_missing = query("""
        SELECT i.imdb_id, i.title
        FROM imdb_top250 i
        WHERE i.imdb_id NOT IN (SELECT imdb_id FROM emby_movies WHERE imdb_id IS NOT NULL AND imdb_id != '')
        ORDER BY i.id
    """)

    douban_total = query("SELECT COUNT(*) AS c FROM douban_top250")[0]["c"]
    imdb_total = query("SELECT COUNT(*) AS c FROM imdb_top250")[0]["c"]

    emby_movies = query("""
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
                WHERE m.title LIKE CONCAT(e.title, '%')
                   OR e.title LIKE CONCAT(m.title, '%')
            ) THEN 1 ELSE 0 END AS in_douban250
        FROM emby_movies e
        LEFT JOIN imdb_top250 i ON e.imdb_id = i.imdb_id
        ORDER BY e.title
    """)

    return render_template(
        "index.html",
        douban_missing=douban_missing,
        imdb_missing=imdb_missing,
        douban_total=douban_total,
        imdb_total=imdb_total,
        emby_movies=emby_movies,
    )


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

    def run_douban():
        douban_dir = os.path.join(PROJECT_ROOT, "douban-scraper")

        # 先运行 Go 爬虫
        update_status("douban", "running", "正在爬取豆瓣数据...")
        try:
            r1 = subprocess.run(
                [SCRIPTS["douban_bin"]], capture_output=True, text=True,
                timeout=300, cwd=douban_dir,
            )
            if r1.returncode != 0:
                update_status("douban", "error", "爬取失败: " + r1.stderr[-200:])
                return

            # 再导入数据库
            update_status("douban", "running", "正在导入数据库...")
            r2 = subprocess.run(
                [sys.executable, SCRIPTS["douban_import"]],
                capture_output=True, text=True, timeout=60,
            )
            if r2.returncode == 0:
                output = r2.stdout.strip()
                last_line = output.split("\n")[-1] if output else "完成"
                update_status("douban", "done", last_line)
            else:
                update_status("douban", "error", "导入失败: " + r2.stderr[-200:])
        except Exception as e:
            update_status("douban", "error", str(e))

    thread = threading.Thread(target=run_douban)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/status")
def get_status():
    with status_lock:
        return jsonify(task_status)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
