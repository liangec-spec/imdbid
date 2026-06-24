#!/bin/bash
# 数据库备份脚本
# 使用方法: ./scripts/backup_db.sh [output_dir]
# 默认输出到项目根目录的 backups/ 文件夹

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${1:-$PROJECT_DIR/backups}"

mkdir -p "$OUTPUT_DIR"

BACKUP_FILE="$OUTPUT_DIR/db_$(date +%Y%m%d_%H%M%S).sql"

echo "正在备份数据库 douban_top250 → $BACKUP_FILE ..."

# 从 .env 加载数据库配置（如果存在）
if [ -f "$PROJECT_DIR/.env" ]; then
    eval "$(grep -E '^DB_(HOST|USER|PASSWORD|NAME)=' "$PROJECT_DIR/.env" | sed 's/^/export /')"
fi

DB_HOST="${DB_HOST:-localhost}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_NAME="${DB_NAME:-douban_top250}"

if [ -n "$DB_PASSWORD" ]; then
    mysqldump -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" > "$BACKUP_FILE"
else
    mysqldump -h "$DB_HOST" -u "$DB_USER" "$DB_NAME" > "$BACKUP_FILE"
fi

echo "✅ 备份完成: $(wc -c < "$BACKUP_FILE") 字节"
