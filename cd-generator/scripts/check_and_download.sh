#!/bin/bash

# 兼容入口：检查并下载一批图片。
# 真实 OpenCLI 状态检查和下载统一由 chatgpt-image skill 的服务提供。

set -e

TASK_DIR="$1"
GUARD="/Users/zhanghua/.claude/skills/cd-generator/scripts/task_path_guard.py"
SERVICE="/Users/zhanghua/.claude/skills/chatgpt-image/scripts/opencli_image_service.py"

if [ -z "$TASK_DIR" ]; then
    echo "用法: $0 <task_dir>"
    exit 1
fi

TASK_DIR="$(python3 "$GUARD" "$TASK_DIR")"
IMAGE_LINKS_FILE="$TASK_DIR/image_links.json"
IMAGES_DIR="$TASK_DIR/images"

if [ ! -f "$IMAGE_LINKS_FILE" ]; then
    echo "错误：未找到图片链接记录文件: $IMAGE_LINKS_FILE"
    exit 1
fi

mkdir -p "$IMAGES_DIR"

echo "🔍 开始检查图片生成状态..."
echo ""

total=$(IMAGE_LINKS_FILE="$IMAGE_LINKS_FILE" python3 << 'PYEOF'
import json
import os

with open(os.environ["IMAGE_LINKS_FILE"], encoding="utf-8") as f:
    data = json.load(f)
print(len(data.get("images", [])))
PYEOF
)

completed=0
failed=0
pending=0

for i in $(seq 0 $((total - 1))); do
    info=$(IMAGE_LINKS_FILE="$IMAGE_LINKS_FILE" INDEX="$i" python3 << 'PYEOF'
import json
import os

with open(os.environ["IMAGE_LINKS_FILE"], encoding="utf-8") as f:
    data = json.load(f)
img = data["images"][int(os.environ["INDEX"])]
print("\n".join([
    str(img.get("chapter", "")),
    str(img.get("page", "")),
    str(img.get("link", "")),
    str(img.get("filename", "")),
    str(img.get("status", "")),
]))
PYEOF
)
    chapter=$(echo "$info" | sed -n '1p')
    page=$(echo "$info" | sed -n '2p')
    link=$(echo "$info" | sed -n '3p')
    filename=$(echo "$info" | sed -n '4p')
    status=$(echo "$info" | sed -n '5p')

    if [ "$status" = "completed" ] && [ -s "$IMAGES_DIR/$filename" ]; then
        ((completed+=1))
        continue
    fi

    echo "📄 第${chapter}章 第${page}页"
    echo "   🔗 $link"

    if [ -z "$link" ] || [ "$link" = "None" ]; then
        echo "   ⏳ 无链接，保留待处理"
        ((pending+=1))
        echo ""
        continue
    fi

    status_json=$(python3 "$SERVICE" status --link "$link" --repair-retries 1 2>&1 || true)
    image_status=$(SERVICE_RESULT="$status_json" python3 << 'PYEOF'
import json
import os

try:
    data = json.loads(os.environ["SERVICE_RESULT"])
    print(data.get("status") or "PENDING")
except json.JSONDecodeError:
    print("PENDING")
PYEOF
)

    if [[ "$image_status" == READY:* ]]; then
        echo "   ✅ 图片已生成，开始下载..."
        download_json=$(python3 "$SERVICE" download \
            --link "$link" \
            --output "$IMAGES_DIR/$filename" \
            --repair-retries 1 2>&1 || true)
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
            file_size=$(ls -lh "$IMAGES_DIR/$filename" | awk '{print $5}')
            IMAGE_LINKS_FILE="$IMAGE_LINKS_FILE" INDEX="$i" FILE_SIZE="$file_size" STATUS="completed" python3 << 'PYEOF'
import json
import os
from datetime import datetime, timezone

path = os.environ["IMAGE_LINKS_FILE"]
index = int(os.environ["INDEX"])
now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
with open(path, encoding="utf-8") as f:
    data = json.load(f)
data["images"][index]["status"] = os.environ["STATUS"]
data["images"][index]["completed_at"] = now
data["images"][index]["last_checked_at"] = now
data["images"][index]["file_size"] = os.environ["FILE_SIZE"]
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
PYEOF
            echo "   ✓ 下载完成 ($file_size)"
            ((completed+=1))
        else
            echo "   ❌ 下载失败"
            ((failed+=1))
        fi
    elif [ "$image_status" = "ERROR" ]; then
        echo "   ❌ 生成失败"
        IMAGE_LINKS_FILE="$IMAGE_LINKS_FILE" INDEX="$i" STATUS="failed" python3 << 'PYEOF'
import json
import os
from datetime import datetime, timezone

path = os.environ["IMAGE_LINKS_FILE"]
index = int(os.environ["INDEX"])
now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
with open(path, encoding="utf-8") as f:
    data = json.load(f)
data["images"][index]["status"] = os.environ["STATUS"]
data["images"][index]["failed_at"] = now
data["images"][index]["last_checked_at"] = now
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
PYEOF
        ((failed+=1))
    else
        echo "   ⏳ 仍在生成中..."
        IMAGE_LINKS_FILE="$IMAGE_LINKS_FILE" INDEX="$i" python3 << 'PYEOF'
import json
import os
from datetime import datetime, timezone

path = os.environ["IMAGE_LINKS_FILE"]
index = int(os.environ["INDEX"])
now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
with open(path, encoding="utf-8") as f:
    data = json.load(f)
data["images"][index]["last_checked_at"] = now
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
PYEOF
        ((pending+=1))
    fi
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 检查完成"
echo "   总计: $total 张"
echo "   ✅ 已完成: $completed 张"
echo "   ❌ 失败: $failed 张"
echo "   ⏳ 生成中: $pending 张"
