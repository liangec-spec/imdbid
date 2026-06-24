"""
共享电影工具函数
统一管理：海报 URL 构建、Emby 电影解析、路径提取、LIKE 转义。
"""
import os

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"


def build_poster_url(tmdb_path, size="w300"):
    """统一构建 TMDB 海报 URL"""
    if not tmdb_path:
        return None
    return f"{TMDB_IMAGE_BASE}/{size}{tmdb_path}"


def parse_emby_movie(item, server=""):
    """从 Emby API 响应解析统一电影字典
    
    参数:
        item: Emby API 返回的电影 JSON 对象
        server: Emby 服务器地址（用于构建海报 URL）
    
    返回:
        统一格式的电影字典
    """
    provider_ids = item.get("ProviderIds", {})
    media_sources = item.get("MediaSources", [{}])[0] if item.get("MediaSources") else {}
    video_stream = next((s for s in item.get("MediaStreams", []) if s.get("Type") == "Video"), {})
    audio_stream = next((s for s in item.get("MediaStreams", []) if s.get("Type") == "Audio"), {})

    # 演职人员
    people = item.get("People", [])
    directors = "|".join([p.get("Name", "") for p in people if p.get("Type") == "Director"])
    actors = "|".join([p.get("Name", "") for p in people if p.get("Type") == "Actor"][:10])

    # 制片国家
    tag_items = item.get("TagItems", [])
    countries = "|".join([t.get("Name", "") for t in tag_items if t.get("Type") == "Country"])
    tags = "|".join([t.get("Name", "") for t in tag_items if t.get("Type") != "Country"])

    # 时长（ticks → 分钟）
    runtime_ticks = item.get("RuntimeTicks", 0)
    runtime_minutes = int(runtime_ticks / 600000000) if runtime_ticks else 0

    # 日期处理
    def _split_date(val):
        if not val:
            return None
        return val.split("T")[0]

    imdb_id = provider_ids.get("Imdb", "")

    # 海报 URL
    image_tags = item.get("ImageTags", {})
    primary_tag = image_tags.get("Primary", "")
    emby_id = item.get("Id", "")
    poster_url = ""
    if primary_tag and server:
        poster_url = f"{server}/Items/{emby_id}/Images/Primary?tag={primary_tag}"

    return {
        "title": item.get("Name", ""),
        "original_title": item.get("OriginalTitle", ""),
        "year": item.get("ProductionYear", ""),
        "production_year": item.get("ProductionYear", ""),
        "official_rating": item.get("OfficialRating", ""),
        "imdb_id": imdb_id,
        "imdb_url": f"https://www.imdb.com/title/{imdb_id}" if imdb_id else "",
        "tmdb_id": provider_ids.get("Tmdb", ""),
        "rating": item.get("CommunityRating", ""),
        "community_rating": item.get("CommunityRating", ""),
        "vote_count": item.get("VoteCount", ""),
        "runtime": runtime_minutes,
        "overview": (item.get("Overview", "") or "").replace("\n", " ").replace("\r", " "),
        "release_date": _split_date(item.get("ReleaseDate", "")),
        "genres": "|".join(item.get("Genres", [])),
        "studios": "|".join([s.get("Name", "") for s in item.get("Studios", [])]),
        "countries": countries,
        "directors": directors,
        "actors": actors,
        "path": media_sources.get("Path", ""),
        "size": media_sources.get("Size", ""),
        "container": media_sources.get("Container", ""),
        "video_codec": video_stream.get("Codec", ""),
        "audio_codec": audio_stream.get("Codec", ""),
        "video_resolution": (
            f"{video_stream.get('Width', '')}x{video_stream.get('Height', '')}"
            if video_stream.get("Width") else ""
        ),
        "date_added": _split_date(item.get("DateCreated", "")),
        "date_modified": _split_date(item.get("DateModified", "")),
        "tags": tags,
        "imdb_rating": "",
        "imdb_votes": "",
        "poster_url": poster_url,
    }


def parse_collection_movie(item):
    """解析合集内的电影（Emby API 返回的简化格式）"""
    people = item.get("People", [])
    media_sources = item.get("MediaSources", [{}])[0] if item.get("MediaSources") else {}
    video_stream = next((s for s in item.get("MediaStreams", []) if s.get("Type") == "Video"), {})
    audio_stream = next((s for s in item.get("MediaStreams", []) if s.get("Type") == "Audio"), {})

    return {
        "emby_id": item.get("Id"),
        "name": item.get("Name", ""),
        "original_title": item.get("OriginalTitle", ""),
        "year": item.get("ProductionYear"),
        "rating": item.get("CommunityRating"),
        "imdb_id": item.get("ProviderIds", {}).get("Imdb", ""),
        "tmdb_id": item.get("ProviderIds", {}).get("Tmdb", ""),
        "overview": item.get("Overview", ""),
        "genres": "|".join(item.get("Genres", [])),
        "directors": "|".join([p.get("Name", "") for p in people if p.get("Type") == "Director"]),
        "actors": "|".join([p.get("Name", "") for p in people if p.get("Type") == "Actor"][:10]),
        "studios": "|".join([s.get("Name", "") for s in item.get("Studios", [])]),
        "video_codec": video_stream.get("Codec", ""),
        "audio_codec": audio_stream.get("Codec", ""),
        "size": media_sources.get("Size"),
        "video_resolution": (
            f"{video_stream.get('Width', '')}x{video_stream.get('Height', '')}"
            if video_stream.get("Width") else ""
        ),
        "path": media_sources.get("Path", ""),
        "in_emby": True,
    }


def extract_location(path):
    """从文件路径中提取位置信息（兼容 Linux 和 Windows）"""
    if not path:
        return ""
    normalized = path.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    return parts[3] if len(parts) > 3 else parts[0] if parts else ""


def escape_like(s):
    """SQL LIKE 查询转义 — 转义 % 和 _"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
