#!/bin/bash

# ChatGPT Image Generator
# 单图入口：调用可复用 OpenCLI 图片服务，其他 skills 也可以直接复用
# scripts/opencli_image_service.py。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE="$SCRIPT_DIR/scripts/opencli_image_service.py"

PROMPT="${1:-东方美女抖音带货视频}"
OUTPUT_DIR="${2:-$HOME/Pictures/chatgpt}"
mkdir -p "$OUTPUT_DIR"

OUTPUT_FILE="$OUTPUT_DIR/chatgpt_image_$(date +%Y%m%d_%H%M%S).png"

echo "🎨 开始生成单张图片..."
echo "📝 提示词: $PROMPT"
echo "📁 输出文件: $OUTPUT_FILE"
echo ""

python3 "$SERVICE" generate \
  --prompt "$PROMPT" \
  --output "$OUTPUT_FILE" \
  --wait-schedule "60,60,60,60,60,120,180" \
  --repair-retries 2

if [ -s "$OUTPUT_FILE" ]; then
  echo ""
  echo "🎉 成功下载图片！"
  echo "📁 保存位置: $OUTPUT_FILE"
  exit 0
fi

echo ""
echo "⚠️ 图片尚未成功下载。上方 JSON 中包含 ChatGPT 链接，可用于手动查看。"
exit 1
