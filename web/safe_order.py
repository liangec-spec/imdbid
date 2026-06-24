"""
ORDER BY 白名单安全映射表
用于防止 SQL 注入，仅允许预定义的值参与 ORDER BY 拼接。
"""
UPCOMING_ORDER_MAP = {
    "upcoming": "release_date ASC",
    "now_playing": "popularity DESC",
}
