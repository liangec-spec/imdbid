"""
共享数据库模块 — 连接池 + 统一查询接口
所有脚本统一通过此模块操作数据库。
"""
import os
import pymysql
from dbutils.pooled_db import PooledDB

# 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 延迟导入 DB_CONFIG（避免 import 时依赖 .env）
_DB_CONFIG = None

def _get_config():
    global _DB_CONFIG
    if _DB_CONFIG is None:
        from config import DB_CONFIG
        _DB_CONFIG = DB_CONFIG
    return _DB_CONFIG


_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        cfg = _get_config().copy()
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            mincached=2,
            maxcached=10,
            blocking=True,
            **cfg
        )
    return _pool


def get_connection():
    """从连接池获取一个连接（使用后务必 close() 归还）"""
    return _get_pool().connection()


def query(sql, args=None, dict_cursor=True):
    """查询并返回字典列表（默认）或元组列表"""
    conn = get_connection()
    try:
        cursor_class = pymysql.cursors.DictCursor if dict_cursor else None
        with conn.cursor(cursor_class) as cur:
            cur.execute(sql, args)
            return cur.fetchall()
    finally:
        conn.close()


def execute(sql, args=None):
    """执行写操作并返回影响行数（自动提交）"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def executemany(sql, args_list):
    """批量执行（自动提交）"""
    if not args_list:
        return 0
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, args_list)
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
