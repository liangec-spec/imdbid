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

from flask import Flask, render_template, jsonify, request
import pymysql

# 添加项目根目录到 path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
from config import DB_CONFIG, DATA_DIR

app = Flask(__name__)

# 脚本路径（相对于项目根目录）
SCRIPTS = {
    "emby": os.path.join(PROJECT_ROOT, "scripts", "export_emby.py"),
    "imdb": os.path.join(PROJECT_ROOT, "scripts", "fetch_imdb_top250.py"),
    "douban": os.path.join(PROJECT_ROOT, "scripts", "fetch_douban_top250.py"),
}

# 映射文件路径
MAPPING_FILE = os.path.join(DATA_DIR, "douban_mapping.json")

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


def execute(sql, args=None):
    """执行数据库写操作"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            conn.commit()
            return cur.rowcount
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


# ========== 映射文件管理 ==========

def load_mapping():
    """从文件加载映射数据"""
    if not os.path.exists(MAPPING_FILE):
        return {"version": 1, "updated_at": None, "mappings": {}}
    try:
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"version": 1, "updated_at": None, "mappings": {}}


def save_mapping(data):
    """保存映射数据到文件"""
    os.makedirs(os.path.dirname(MAPPING_FILE), exist_ok=True)
    data["updated_at"] = datetime.now().isoformat()
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sync_mapping_to_db():
    """从文件同步映射到数据库"""
    data = load_mapping()
    mappings = data.get("mappings", {})

    # 清空表
    execute("DELETE FROM douban_imdb_mapping")

    # 批量插入
    if mappings:
        sql = "INSERT INTO douban_imdb_mapping (douban_ranking, douban_title, imdb_id, note) VALUES (%s, %s, %s, %s)"
        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cur:
                for ranking, info in mappings.items():
                    cur.execute(sql, (
                        int(ranking),
                        info.get("title", ""),
                        info.get("imdb_id", ""),
                        info.get("note", ""),
                    ))
            conn.commit()
        finally:
            conn.close()

    return len(mappings)


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
    """获取 Top 250 完整列表（包含手动关联和是否在 Emby 中）"""
    type = request.args.get("type", "imdb", type=str)

    if type == "douban":
        movies = query("""
            SELECT
                m.ranking, m.title, m.douban_link,
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
            LEFT JOIN douban_imdb_mapping map ON m.ranking = map.douban_ranking
            LEFT JOIN emby_movies e ON (
                (map.imdb_id IS NOT NULL AND map.imdb_id != '' AND map.imdb_id = e.imdb_id)
                OR (m.imdb_id IS NOT NULL AND m.imdb_id != '' AND m.imdb_id = e.imdb_id)
            )
            ORDER BY m.ranking
        """)
    else:
        movies = query("""
            SELECT
                i.title, i.imdb_id,
                e.year, e.imdb_rating, e.imdb_votes,
                e.video_resolution,
                CASE
                    WHEN e.video_resolution IS NULL THEN NULL
                    WHEN CAST(SUBSTRING_INDEX(e.video_resolution, 'x', 1) AS UNSIGNED) >= 3000 THEN '4K'
                    WHEN CAST(SUBSTRING_INDEX(e.video_resolution, 'x', 1) AS UNSIGNED) >= 1000 THEN '1080p'
                    WHEN CAST(SUBSTRING_INDEX(e.video_resolution, 'x', 1) AS UNSIGNED) >= 700 THEN '720p'
                    ELSE e.video_resolution
                END AS resolution,
                CASE WHEN e.imdb_id IS NOT NULL THEN 1 ELSE 0 END AS in_emby
            FROM imdb_top250 i
            LEFT JOIN emby_movies e ON i.imdb_id = e.imdb_id
            ORDER BY e.imdb_rating DESC
        """)

    return jsonify({"movies": movies})


# ========== 映射管理 API ==========

@app.route("/api/mapping")
def api_mapping_get():
    """获取所有映射"""
    data = load_mapping()
    return jsonify(data)


@app.route("/api/mapping", methods=["POST"])
def api_mapping_save():
    """保存映射（同时更新文件和数据库）"""
    req = request.get_json()
    ranking = req.get("ranking")
    title = req.get("title", "")
    imdb_id = req.get("imdb_id", "").strip()
    note = req.get("note", "")

    if not ranking or not imdb_id:
        return jsonify({"status": "error", "message": "缺少必要参数"}), 400

    # 验证 IMDB ID 格式
    if not imdb_id.startswith("tt"):
        return jsonify({"status": "error", "message": "IMDB ID 格式错误，应以 tt 开头"}), 400

    # 更新文件
    data = load_mapping()
    data["mappings"][str(ranking)] = {
        "title": title,
        "imdb_id": imdb_id,
        "note": note,
        "updated_at": datetime.now().isoformat(),
    }
    save_mapping(data)

    # 更新数据库
    execute("""
        INSERT INTO douban_imdb_mapping (douban_ranking, douban_title, imdb_id, note)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE imdb_id = VALUES(imdb_id), note = VALUES(note)
    """, (ranking, title, imdb_id, note))

    return jsonify({"status": "ok", "message": "保存成功"})


@app.route("/api/mapping/<int:ranking>", methods=["DELETE"])
def api_mapping_delete(ranking):
    """删除映射"""
    # 更新文件
    data = load_mapping()
    if str(ranking) in data["mappings"]:
        del data["mappings"][str(ranking)]
        save_mapping(data)

    # 更新数据库
    execute("DELETE FROM douban_imdb_mapping WHERE douban_ranking = %s", (ranking,))

    return jsonify({"status": "ok", "message": "删除成功"})


@app.route("/api/mapping/sync", methods=["POST"])
def api_mapping_sync():
    """从文件同步到数据库"""
    count = sync_mapping_to_db()
    return jsonify({"status": "ok", "message": f"同步完成，共 {count} 条记录"})


@app.route("/api/mapping/export")
def api_mapping_export():
    """导出映射数据"""
    data = load_mapping()
    return jsonify(data)


if __name__ == "__main__":
    # 启动时同步映射到数据库
    sync_mapping_to_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
