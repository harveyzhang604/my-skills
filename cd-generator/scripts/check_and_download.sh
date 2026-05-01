#!/bin/bash

# 检查并下载图片脚本
# 用法: ./check_and_download.sh <task_dir>

set +e

TASK_DIR="$1"
GUARD="/Users/zhanghua/.claude/skills/cd-generator/scripts/task_path_guard.py"

if [ -z "$TASK_DIR" ]; then
    echo "用法: $0 <task_dir>"
    exit 1
fi

TASK_DIR="$(python3 "$GUARD" "$TASK_DIR")"

IMAGE_LINKS_FILE="$TASK_DIR/image_links.json"
IMAGES_DIR="$TASK_DIR/images"

is_browser_attach_error() {
    local output="$1"
    echo "$output" | grep -Eqi "Cannot access a chrome-extension:// URL of different extension|Detached while handling command|attach failed"
}

repair_opencli_browser() {
    echo "   🔧 OpenCLI 浏览器会话异常，重启自动化窗口并检查 doctor"
    opencli browser close 2>&1 > /dev/null || true
    opencli doctor 2>&1 > /dev/null || true
    sleep 5
}

if [ ! -f "$IMAGE_LINKS_FILE" ]; then
    echo "错误：未找到图片链接记录文件: $IMAGE_LINKS_FILE"
    exit 1
fi

echo "🔍 开始检查图片生成状态..."
echo ""

# 读取所有待检查的图片
total=$(cat "$IMAGE_LINKS_FILE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data['images']))")
completed=0
failed=0
pending=0

for i in $(seq 0 $((total - 1))); do
    # 提取图片信息
    info=$(cat "$IMAGE_LINKS_FILE" | python3 -c "import sys, json; data=json.load(sys.stdin); img=data['images'][$i]; print(f\"{img['chapter']}|{img['page']}|{img['link']}|{img['filename']}|{img['status']}\")")

    IFS='|' read -r chapter page link filename status <<< "$info"

    # 跳过已完成的
    if [ "$status" = "completed" ]; then
        ((completed++))
        continue
    fi

    echo "📄 第${chapter}章 第${page}页"
    echo "   🔗 $link"

    # 打开页面检查。OpenCLI 偶尔会停在 chrome-extension:// 页面，先修复再重试一次。
    open_result=$(opencli browser open "$link" 2>&1)
    open_code=$?
    if [ $open_code -ne 0 ] && is_browser_attach_error "$open_result"; then
        repair_opencli_browser
        open_result=$(opencli browser open "$link" 2>&1)
        open_code=$?
    fi
    if [ $open_code -ne 0 ]; then
        echo "   ⏳ OpenCLI 暂时无法打开链接，保留为待检查"
        ((pending++))
        echo ""
        continue
    fi
    sleep 5

    # 检查状态
    check_result=$(opencli browser eval "
(() => {
  const bodyText = document.body.innerText;

  // 检查错误信息
  if (bodyText.includes('I was unable to generate') ||
      bodyText.includes('encountered an error') ||
      bodyText.includes('抱歉')) {
    return 'ERROR';
  }

  // 检查图片
  let img = document.querySelector('img[src*=\"chatgpt.com/backend-api/\"]');
  if (!img) img = document.querySelector('img[alt=\"Generated image\"]');

  if (img && img.complete && img.naturalWidth > 0) {
    return 'READY:' + img.naturalWidth + 'x' + img.naturalHeight;
  }

  return 'PENDING';
})()
" 2>&1)
    check_code=$?
    if [ $check_code -ne 0 ] && is_browser_attach_error "$check_result"; then
        repair_opencli_browser
        opencli browser open "$link" 2>&1 > /dev/null
        sleep 5
        check_result=$(opencli browser eval "
(() => {
  const bodyText = document.body.innerText;
  if (bodyText.includes('I was unable to generate') ||
      bodyText.includes('encountered an error') ||
      bodyText.includes('抱歉')) {
    return 'ERROR';
  }
  let img = document.querySelector('img[src*=\"chatgpt.com/backend-api/\"]');
  if (!img) img = document.querySelector('img[alt=\"Generated image\"]');
  if (img && img.complete && img.naturalWidth > 0) {
    return 'READY:' + img.naturalWidth + 'x' + img.naturalHeight;
  }
  return 'PENDING';
})()
" 2>&1)
    fi

    if echo "$check_result" | grep -q "^READY:"; then
        echo "   ✅ 图片已生成，开始下载..."
        download_started_at=$(date +%s)

        # 下载图片
        opencli browser eval "
(async () => {
  let img = document.querySelector('img[src*=\"chatgpt.com/backend-api/\"]');
  if (!img) img = document.querySelector('img[alt=\"Generated image\"]');
  if (!img) return 'No image';

  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  const dataUrl = canvas.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = 'chatgpt_image.png';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  return 'Downloaded';
})()
" 2>&1 > /dev/null

        sleep 3

        # 只认本次下载开始后的 PNG，避免误拿 Downloads 里的旧图。
        latest_download=$(DOWNLOAD_STARTED_AT="$download_started_at" python3 << 'PYEOF'
import os
from pathlib import Path

started_at = float(os.environ["DOWNLOAD_STARTED_AT"])
downloads = Path.home() / "Downloads"
candidates = []
for path in downloads.glob("*.png"):
    try:
        stat = path.stat()
    except OSError:
        continue
    if stat.st_mtime >= started_at - 1:
        candidates.append((stat.st_mtime, path))
if candidates:
    print(max(candidates)[1])
PYEOF
)
        if [ -n "$latest_download" ]; then
            mv "$latest_download" "$IMAGES_DIR/$filename"
            file_size=$(ls -lh "$IMAGES_DIR/$filename" | awk '{print $5}')
            echo "   ✓ 下载完成 ($file_size)"

            # 更新状态
            python3 << EOF
import json
with open("$IMAGE_LINKS_FILE", "r") as f:
data = json.load(f)
data["images"][$i]["status"] = "completed"
data["images"][$i]["completed_at"] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
data["images"][$i]["last_checked_at"] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
data["images"][$i]["file_size"] = "$file_size"
with open("$IMAGE_LINKS_FILE", "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
EOF
            ((completed++))
        else
            echo "   ❌ 下载失败"
            ((failed++))
        fi

    elif echo "$check_result" | grep -q "ERROR"; then
        echo "   ❌ 生成失败"

        # 更新状态为失败
        python3 << EOF
import json
with open("$IMAGE_LINKS_FILE", "r") as f:
data = json.load(f)
data["images"][$i]["status"] = "failed"
data["images"][$i]["failed_at"] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
data["images"][$i]["last_checked_at"] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
with open("$IMAGE_LINKS_FILE", "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
EOF
        ((failed++))

    else
        echo "   ⏳ 仍在生成中..."
        python3 << EOF
import json
with open("$IMAGE_LINKS_FILE", "r") as f:
    data = json.load(f)
data["images"][$i]["last_checked_at"] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
with open("$IMAGE_LINKS_FILE", "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
EOF
        ((pending++))
    fi

    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 检查完成"
echo "   总计: $total 张"
echo "   ✅ 已完成: $completed 张"
echo "   ❌ 失败: $failed 张"
echo "   ⏳ 生成中: $pending 张"
echo ""

if [ $failed -gt 0 ]; then
    echo "⚠️  有 $failed 张图片生成失败，需要重新生成"
    echo "   运行以下命令查看失败的图片："
    echo "   cat $IMAGE_LINKS_FILE | python3 -c \"import sys, json; data=json.load(sys.stdin); [print(f'第{img[\\\"chapter\\\"]}章第{img[\\\"page\\\"]}页: {img[\\\"link\\\"]}') for img in data['images'] if img['status']=='failed']\""
fi

if [ $pending -gt 0 ]; then
    echo "⏰ 还有 $pending 张图片正在生成中"
    echo "   建议1分钟后再次运行此脚本"
fi
