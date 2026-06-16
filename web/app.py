#!/usr/bin/env python3
"""
Emby 电影管理 Web 界面
"""
import json
import os
import sys
import subprocess
import threading
from datetime import datetime

import requests
from flask import Flask, render_template, jsonify, request
import pymysql

# 添加项目根目录到 path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
from config import DB_CONFIG, DATA_DIR, EMBY_CONFIG, TMDB_API_KEY

app = Flask(__name__)

# 脚本路径
SCRIPTS = {
    "emby": os.path.join(PROJECT_ROOT, "scripts", "export_emby.py"),
    "imdb": os.path.join(PROJECT_ROOT, "scripts", "fetch_imdb_top250.py"),
    "douban": os.path.join(PROJECT_ROOT, "scripts", "fetch_douban_top250.py"),
    "collections": os.path.join(PROJECT_ROOT, "scripts", "sync_collections.py"),
}

# 映射文件路径
MAPPING_FILE = os.path.join(DATA_DIR, "douban_mapping.json")

# Emby 合集配置
EMBY_COLLECTIONS_PARENT_ID = os.getenv("EMBY_COLLECTIONS_PARENT_ID", "43626")

# 任务状态
task_status = {"emby": None, "imdb": None, "douban": None, "collections": None}
status_lock = threading.Lock()


def query(sql, args=None):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


def execute(sql, args=None):
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            conn.commit()
            return cur.rowcount
    finally:
        conn.close()


def update_status(task_name, status, message):
    with status_lock:
        task_status[task_name] = {"status": status, "message": message}


def run_task(task_name, cmd, cwd=None):
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


# ========== 映射文件管理 ==========

def load_mapping():
    if not os.path.exists(MAPPING_FILE):
        return {"version": 2, "updated_at": None, "mappings": {}}
    try:
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 兼容旧版本（key 是 ranking）
            if data.get("version", 1) == 1:
                return {"version": 2, "updated_at": data.get("updated_at"), "mappings": {}}
            return data
    except Exception:
        return {"version": 2, "updated_at": None, "mappings": {}}


def save_mapping(data):
    os.makedirs(os.path.dirname(MAPPING_FILE), exist_ok=True)
    data["updated_at"] = datetime.now().isoformat()
    data["version"] = 2
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sync_mapping_to_db():
    data = load_mapping()
    mappings = data.get("mappings", {})
    execute("DELETE FROM douban_imdb_mapping")
    if mappings:
        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cur:
                for douban_id, info in mappings.items():
                    # 先查找 ranking
                    cur.execute("SELECT ranking FROM douban_top250 WHERE douban_id = %s", (douban_id,))
                    row = cur.fetchone()
                    ranking = row[0] if row else 0
                    cur.execute(
                        "INSERT INTO douban_imdb_mapping (douban_id, douban_ranking, douban_title, imdb_id, note) VALUES (%s, %s, %s, %s, %s)",
                        (douban_id, ranking, info.get("title", ""), info.get("imdb_id", ""), info.get("note", ""))
                    )
            conn.commit()
        finally:
            conn.close()
    return len(mappings)


@app.route("/")
def index():
    douban_total = query("SELECT COUNT(*) AS c FROM douban_top250")[0]["c"]
    imdb_total = query("SELECT COUNT(*) AS c FROM imdb_top250")[0]["c"]
    emby_total = query("SELECT COUNT(*) AS c FROM emby_movies")[0]["c"]

    douban_missing_count = query("""
        SELECT COUNT(*) AS c FROM douban_top250 m
        WHERE NOT EXISTS (
            SELECT 1 FROM emby_movies e
            WHERE e.imdb_id = COALESCE(
                (SELECT map.imdb_id FROM douban_imdb_mapping map WHERE map.douban_id = m.douban_id),
                m.imdb_id
            ) OR e.title LIKE CONCAT(m.title, '%')
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
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("search", "", type=str)
    sort_by = request.args.get("sort_by", "imdb_rating", type=str)
    sort_order = request.args.get("sort_order", "desc", type=str)
    filter_type = request.args.get("filter", "all", type=str)
    per_page = min(per_page, 100)

    where_clauses = []
    params = []
    if search:
        where_clauses.append("(e.title LIKE %s OR e.original_title LIKE %s OR e.imdb_id LIKE %s)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    sort_fields = {
        "title": "e.title", "year": "e.year", "rating": "e.rating",
        "imdb_rating": "e.imdb_rating", "imdb_votes": "e.imdb_votes",
        "date_added": "e.date_added",
    }
    order_field = sort_fields.get(sort_by, "e.imdb_rating")
    order_dir = "DESC" if sort_order == "desc" else "ASC"

    if filter_type in ("imdb", "both"):
        imdb_join = "INNER JOIN imdb_top250 i ON e.imdb_id = i.imdb_id"
    else:
        imdb_join = "LEFT JOIN imdb_top250 i ON e.imdb_id = i.imdb_id"

    douban_filter = ""
    if filter_type in ("douban", "both"):
        douban_filter = """AND EXISTS (
            SELECT 1 FROM douban_top250 d
            LEFT JOIN douban_imdb_mapping map ON d.douban_id = map.douban_id
            WHERE COALESCE(map.imdb_id, d.imdb_id) = e.imdb_id
               OR d.title LIKE CONCAT(e.title, '%%')
        )"""

    count_sql = f"SELECT COUNT(*) AS total FROM emby_movies e {imdb_join} WHERE {where_sql} {douban_filter}"
    total = query(count_sql, params)[0]["total"]

    offset = (page - 1) * per_page
    data_sql = f"""
        SELECT
            e.title, e.original_title, e.year, e.imdb_id, e.tmdb_id, e.rating,
            e.imdb_rating, e.imdb_votes, e.genres, e.studios, e.countries,
            e.directors, e.actors, e.overview, e.runtime, e.release_date,
            e.official_rating, e.video_codec, e.audio_codec, e.size,
            e.path, e.tags, e.date_added, e.video_resolution,
            CASE
                WHEN e.path LIKE '%%2160p%%' THEN '4K'
                WHEN e.path LIKE '%%1080p%%' THEN '1080p'
                WHEN e.path LIKE '%%720p%%' THEN '720p'
                WHEN e.path LIKE '%%480p%%' THEN '480p'
                ELSE IFNULL(e.video_resolution, '-')
            END AS resolution_label,
            SUBSTRING_INDEX(SUBSTRING_INDEX(e.path, '\\\\', 4), '\\\\', -1) AS location,
            CASE WHEN i.imdb_id IS NOT NULL THEN 1 ELSE 0 END AS in_imdb250,
            CASE WHEN EXISTS (
                SELECT 1 FROM douban_top250 d
                LEFT JOIN douban_imdb_mapping map ON d.douban_id = map.douban_id
                WHERE COALESCE(map.imdb_id, d.imdb_id) = e.imdb_id
                   OR d.title LIKE CONCAT(e.title, '%%')
            ) THEN 1 ELSE 0 END AS in_douban250
        FROM emby_movies e {imdb_join}
        WHERE {where_sql} {douban_filter}
        ORDER BY {order_field} {order_dir}
        LIMIT %s OFFSET %s
    """
    movies = query(data_sql, params + [per_page, offset])
    return jsonify({
        "movies": movies, "total": total, "page": page,
        "per_page": per_page, "total_pages": (total + per_page - 1) // per_page,
    })


@app.route("/api/movies/missing")
def api_missing_movies():
    type = request.args.get("type", "imdb", type=str)
    if type == "douban":
        movies = query("""
            SELECT m.ranking, m.title, m.douban_id, m.imdb_id, m.douban_link
            FROM douban_top250 m
            WHERE NOT EXISTS (
                SELECT 1 FROM emby_movies e
                WHERE e.imdb_id = COALESCE(
                    (SELECT map.imdb_id FROM douban_imdb_mapping map WHERE map.douban_id = m.douban_id),
                    m.imdb_id
                ) OR e.title LIKE CONCAT(m.title, '%')
            )
            ORDER BY m.ranking
        """)
    else:
        movies = query("""
            SELECT i.imdb_id, i.title FROM imdb_top250 i
            WHERE i.imdb_id NOT IN (SELECT imdb_id FROM emby_movies WHERE imdb_id IS NOT NULL AND imdb_id != '')
            ORDER BY i.id
        """)
    return jsonify({"movies": movies})


@app.route("/api/top250")
def api_top250():
    type = request.args.get("type", "imdb", type=str)
    if type == "douban":
        movies = query("""
            SELECT
                m.ranking, m.title, m.douban_id, m.douban_link,
                CASE
                    WHEN map.imdb_id IS NOT NULL AND map.imdb_id != '' THEN map.imdb_id
                    ELSE m.imdb_id
                END AS imdb_id,
                e.year, e.imdb_rating,
                CASE
                    WHEN map.imdb_id IS NOT NULL AND map.imdb_id != '' THEN 'manual'
                    WHEN m.imdb_id IS NOT NULL AND m.imdb_id != '' THEN 'auto'
                    ELSE 'none'
                END AS imdb_source,
                CASE WHEN EXISTS (
                    SELECT 1 FROM emby_movies e2
                    WHERE (map.imdb_id IS NOT NULL AND map.imdb_id != '' AND map.imdb_id = e2.imdb_id)
                       OR (m.imdb_id IS NOT NULL AND m.imdb_id != '' AND m.imdb_id = e2.imdb_id)
                       OR e2.title LIKE CONCAT(m.title, '%%')
                       OR m.title LIKE CONCAT(e2.title, '%%')
                ) THEN 1 ELSE 0 END AS in_emby
            FROM douban_top250 m
            LEFT JOIN douban_imdb_mapping map ON m.douban_id = map.douban_id
            LEFT JOIN emby_movies e ON (
                (map.imdb_id IS NOT NULL AND map.imdb_id != '' AND map.imdb_id = e.imdb_id)
                OR (m.imdb_id IS NOT NULL AND m.imdb_id != '' AND m.imdb_id = e.imdb_id)
            )
            ORDER BY m.ranking
        """)
    else:
        rows = query("""
            SELECT
                ROW_NUMBER() OVER (ORDER BY i.id) AS `rank`,
                i.title, i.imdb_id, e.year,
                e.imdb_rating AS rating,
                e.imdb_votes AS votes,
                CASE
                    WHEN e.path LIKE '%%2160p%%' THEN '4K'
                    WHEN e.path LIKE '%%1080p%%' THEN '1080p'
                    WHEN e.path LIKE '%%720p%%' THEN '720p'
                    WHEN e.path LIKE '%%480p%%' THEN '480p'
                    ELSE NULL
                END AS resolution,
                CASE WHEN e.imdb_id IS NOT NULL THEN 1 ELSE 0 END AS in_emby
            FROM imdb_top250 i
            LEFT JOIN emby_movies e ON i.imdb_id = e.imdb_id
            ORDER BY i.id
        """)
        movies = []
        for r in rows:
            r['rating'] = float(r['rating']) if r['rating'] else None
            r['votes'] = int(r['votes']) if r['votes'] else None
            movies.append(r)
    return jsonify({"movies": movies})


# ========== 映射管理 API ==========

@app.route("/api/mapping")
def api_mapping_get():
    data = load_mapping()
    return jsonify(data)


@app.route("/api/mapping", methods=["POST"])
def api_mapping_save():
    req = request.get_json()
    douban_id = req.get("douban_id", "").strip()
    title = req.get("title", "")
    imdb_id = req.get("imdb_id", "").strip()
    note = req.get("note", "")

    if not douban_id or not imdb_id:
        return jsonify({"status": "error", "message": "缺少必要参数"}), 400
    if not imdb_id.startswith("tt"):
        return jsonify({"status": "error", "message": "IMDB ID 格式错误，应以 tt 开头"}), 400

    data = load_mapping()
    data["mappings"][douban_id] = {
        "title": title, "imdb_id": imdb_id, "note": note,
        "updated_at": datetime.now().isoformat(),
    }
    save_mapping(data)

    # 查找 ranking
    row = query("SELECT ranking FROM douban_top250 WHERE douban_id = %s", (douban_id,))
    ranking = row[0]["ranking"] if row else 0

    execute("""
        INSERT INTO douban_imdb_mapping (douban_id, douban_ranking, douban_title, imdb_id, note)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE imdb_id = VALUES(imdb_id), note = VALUES(note)
    """, (douban_id, ranking, title, imdb_id, note))

    return jsonify({"status": "ok", "message": "保存成功"})


@app.route("/api/mapping/<douban_id>", methods=["DELETE"])
def api_mapping_delete(douban_id):
    data = load_mapping()
    if douban_id in data["mappings"]:
        del data["mappings"][douban_id]
        save_mapping(data)
    execute("DELETE FROM douban_imdb_mapping WHERE douban_id = %s", (douban_id,))
    return jsonify({"status": "ok", "message": "删除成功"})


@app.route("/api/mapping/sync", methods=["POST"])
def api_mapping_sync():
    count = sync_mapping_to_db()
    return jsonify({"status": "ok", "message": f"同步完成，共 {count} 条记录"})


@app.route("/api/update/emby", methods=["POST"])
def update_emby():
    with status_lock:
        s = task_status.get("emby") or {}
        if s.get("status") == "running":
            return jsonify({"status": "busy", "message": "任务正在执行中"})
    thread = threading.Thread(target=run_task, args=("emby", [sys.executable, SCRIPTS["emby"], "--mysql"]))
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/update/imdb", methods=["POST"])
def update_imdb():
    with status_lock:
        s = task_status.get("imdb") or {}
        if s.get("status") == "running":
            return jsonify({"status": "busy", "message": "任务正在执行中"})
    thread = threading.Thread(target=run_task, args=("imdb", [sys.executable, SCRIPTS["imdb"]]))
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/update/douban", methods=["POST"])
def update_douban():
    with status_lock:
        s = task_status.get("douban") or {}
        if s.get("status") == "running":
            return jsonify({"status": "busy", "message": "任务正在执行中"})
    thread = threading.Thread(target=run_task, args=("douban", [sys.executable, SCRIPTS["douban"]]))
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/update/collections", methods=["POST"])
def update_collections():
    with status_lock:
        s = task_status.get("collections") or {}
        if s.get("status") == "running":
            return jsonify({"status": "busy", "message": "任务正在执行中"})
    thread = threading.Thread(target=run_task, args=("collections", [sys.executable, SCRIPTS["collections"]]))
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/status")
def get_status():
    with status_lock:
        return jsonify(task_status)


# ========== 合集管理 API ==========

@app.route("/api/collections")
def api_collections():
    """从数据库获取合集列表"""
    rows = query("""
        SELECT id, emby_id, name, tmdb_id, child_count, total_count, missing_count, overview
        FROM emby_collections
        ORDER BY name
    """)
    return jsonify({"collections": rows, "total": len(rows)})


@app.route("/api/collections/<int:collection_id>")
def api_collection_detail(collection_id):
    """从数据库获取合集内的电影，关联 emby_movies 获取完整信息"""
    movies = query("""
        SELECT c.name, c.original_title, c.year, c.rating, c.imdb_rating, c.imdb_votes,
               c.imdb_id, c.tmdb_id, c.overview, c.genres, c.directors, c.actors, c.studios,
               c.video_codec, c.audio_codec, c.size, c.video_resolution, c.path, c.in_emby,
               e.imdb_rating AS emby_imdb_rating, e.imdb_votes AS emby_imdb_votes
        FROM emby_collection_movies c
        LEFT JOIN emby_movies e ON c.imdb_id = e.imdb_id
        WHERE c.collection_id = %s
        ORDER BY c.in_emby DESC, c.year ASC
    """, (collection_id,))

    # 补充 IMDB 评分
    for m in movies:
        if not m.get("imdb_rating") and m.get("emby_imdb_rating"):
            m["imdb_rating"] = m["emby_imdb_rating"]
        if not m.get("imdb_votes") and m.get("emby_imdb_votes"):
            m["imdb_votes"] = m["emby_imdb_votes"]

        # 计算分辨率标签和位置
        path = m.get("path") or ""
        if "2160p" in path:
            m["resolution_label"] = "4K"
        elif "1080p" in path:
            m["resolution_label"] = "1080p"
        elif "720p" in path:
            m["resolution_label"] = "720p"
        else:
            m["resolution_label"] = m.get("video_resolution", "-")

        # 提取位置
        if path:
            parts = path.split("\\")
            m["location"] = parts[3] if len(parts) > 3 else "-"
        else:
            m["location"] = "-"

    owned = [m for m in movies if m["in_emby"]]
    missing = [m for m in movies if not m["in_emby"]]

    return jsonify({
        "movies": owned,
        "missing": missing,
    })


# 启动时同步映射数据（Gunicorn 和直接运行都会执行）
sync_mapping_to_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
