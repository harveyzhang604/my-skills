#!/bin/bash

# 图片生成管理脚本
# 用法: ./generate_images.sh <task_dir>

set -e

TASK_DIR="$1"
GUARD="/Users/zhanghua/.claude/skills/cd-generator/scripts/task_path_guard.py"

if [ -z "$TASK_DIR" ]; then
    echo "用法: $0 <task_dir>"
    exit 1
fi

TASK_DIR="$(python3 "$GUARD" "$TASK_DIR")"

IMAGES_DIR="$TASK_DIR/images"
STORYBOARDS_DIR="$TASK_DIR/storyboards"
IMAGE_LINKS_FILE="$TASK_DIR/image_links.json"

mkdir -p "$IMAGES_DIR"

echo "🎨 开始批量生成图片..."
echo "📁 任务目录: $TASK_DIR"
echo ""

# 初始化图片链接记录文件
echo "{\"images\": []}" > "$IMAGE_LINKS_FILE"

# 遍历所有分镜文件
for storyboard_file in "$STORYBOARDS_DIR"/*.json; do
    if [ ! -f "$storyboard_file" ]; then
        continue
    fi

    filename=$(basename "$storyboard_file")
    chapter=$(echo "$filename" | grep -o 'chapter[0-9]*' | grep -o '[0-9]*')
    page=$(echo "$filename" | grep -o 'page[0-9]*' | grep -o '[0-9]*')

    echo "📄 处理: 第${chapter}章 第${page}页"

    # 提取图片提示词
    prompt=$(cat "$storyboard_file" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['storyboard']['image_prompt'])" 2>/dev/null || echo "")

    if [ -z "$prompt" ]; then
        echo "   ⚠️  未找到提示词，跳过"
        continue
    fi

    echo "   📝 提示词: ${prompt:0:80}..."

    # 提交图片生成请求
    echo "   📤 提交生成请求..."
    result=$(opencli chatgpt image "$prompt" --verbose 2>&1)

    # 提取链接
    link=$(echo "$result" | grep "link:" | sed 's/.*link: 🔗 //' | head -1)

    if [ -z "$link" ]; then
        echo "   ❌ 提交失败"
        continue
    fi

    echo "   ✅ 已提交: $link"

    # 记录链接
    python3 << EOF
import json
with open("$IMAGE_LINKS_FILE", "r") as f:
    data = json.load(f)
data["images"].append({
    "chapter": $chapter,
    "page": $page,
    "filename": "chapter${chapter}_page${page}.png",
    "link": "$link",
    "prompt": $(echo "$prompt" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))"),
    "status": "pending",
    "submitted_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
})
with open("$IMAGE_LINKS_FILE", "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
EOF

    echo ""
    sleep 2  # 避免请求过快
done

echo "✅ 所有图片生成请求已提交"
echo "📋 链接记录: $IMAGE_LINKS_FILE"
echo ""
echo "⏰ 请等待1分钟后运行检查脚本："
echo "   ./check_and_download.sh $TASK_DIR"
