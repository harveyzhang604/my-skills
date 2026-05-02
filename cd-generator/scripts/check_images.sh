#!/bin/bash

# 检查并下载单个 ChatGPT 图片生成链接。
# 兼容旧入口，实际状态检查和下载统一调用 chatgpt-image skill 的服务。
# 用法: ./check_images.sh <chat_link> <output_dir> [filename]

set -e

CHAT_LINK="$1"
OUTPUT_DIR="$2"
FILENAME="${3:-chatgpt_image.png}"
SERVICE="/Users/zhanghua/.claude/skills/chatgpt-image/scripts/opencli_image_service.py"

if [ -z "$CHAT_LINK" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "用法: $0 <chat_link> <output_dir> [filename]"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "🔍 检查图片生成状态..."
echo "🔗 链接: $CHAT_LINK"
echo "📁 输出目录: $OUTPUT_DIR"
echo ""

status_json=$(python3 "$SERVICE" status --link "$CHAT_LINK" --repair-retries 1)
status=$(SERVICE_RESULT="$status_json" python3 << 'PYEOF'
import json
import os

try:
    data = json.loads(os.environ["SERVICE_RESULT"])
    print(data.get("status") or "PENDING")
except json.JSONDecodeError:
    print("PENDING")
PYEOF
)

echo "图片状态: $status"

if [[ "$status" == READY:* ]]; then
    echo "✅ 图片已生成，开始下载..."
    download_json=$(python3 "$SERVICE" download \
        --link "$CHAT_LINK" \
        --output "$OUTPUT_DIR/$FILENAME" \
        --repair-retries 1)
    ok=$(SERVICE_RESULT="$download_json" python3 << 'PYEOF'
import json
import os

try:
    data = json.loads(os.environ["SERVICE_RESULT"])
    print("1" if data.get("ok") and data.get("status") == "completed" else "0")
except json.JSONDecodeError:
    print("0")
PYEOF
)
    if [ "$ok" = "1" ]; then
        file_size=$(ls -lh "$OUTPUT_DIR/$FILENAME" | awk '{print $5}')
        echo "✓ 下载完成 ($file_size)"
        echo "📁 保存位置: $OUTPUT_DIR/$FILENAME"
        exit 0
    fi
    echo "❌ 下载失败"
    echo "$download_json"
    exit 1
fi

if [ "$status" = "ERROR" ]; then
    echo "❌ 生成失败"
    exit 3
fi

echo "⚠️ 图片未就绪"
exit 2
