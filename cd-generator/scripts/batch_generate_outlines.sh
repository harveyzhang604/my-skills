#!/usr/bin/env bash
# 批量生成故事大纲并评分

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_BASE="$SKILL_DIR/output"

# 默认参数
BATCH_SIZE=10
THEME=""
GENRE="workplace"
LANGUAGE_LEVEL="B1"
TOTAL_CHAPTERS=6
PAGES_PER_CHAPTER=24

# 解析参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --batch-size)
      BATCH_SIZE="$2"
      shift 2
      ;;
    --theme)
      THEME="$2"
      shift 2
      ;;
    --genre)
      GENRE="$2"
      shift 2
      ;;
    --level)
      LANGUAGE_LEVEL="$2"
      shift 2
      ;;
    --chapters)
      TOTAL_CHAPTERS="$2"
      shift 2
      ;;
    --pages)
      PAGES_PER_CHAPTER="$2"
      shift 2
      ;;
    *)
      echo "未知参数: $1"
      exit 1
      ;;
  esac
done

if [[ -z "$THEME" ]]; then
  echo "错误：必须指定 --theme"
  echo "用法：$0 --theme '主题' [--batch-size 10] [--genre workplace] [--level B1]"
  exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 批量生成故事大纲"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "主题：$THEME"
echo "类型：$GENRE"
echo "语言难度：$LANGUAGE_LEVEL"
echo "批量数：$BATCH_SIZE"
echo "章节数：$TOTAL_CHAPTERS"
echo "每章页数：$PAGES_PER_CHAPTER"
echo ""

BATCH_ID="$(date +%Y%m%d_%H%M%S)_batch_${THEME// /_}"
BATCH_DIR="$OUTPUT_BASE/$BATCH_ID"
mkdir -p "$BATCH_DIR"

TASK_DIRS=()

# 生成多个故事大纲
for i in $(seq 1 "$BATCH_SIZE"); do
  echo "━━━ 生成第 $i/$BATCH_SIZE 个故事大纲 ━━━"

  TASK_ID="$(date +%Y%m%d_%H%M%S)_${THEME// /_}_v${i}"
  TASK_DIR="$OUTPUT_BASE/$TASK_ID"

  mkdir -p "$TASK_DIR"/{data,scripts,storyboards,prompts,prompts_zh,missions,images,output,quality}

  # 创建进度文件
  cat > "$TASK_DIR/data/progress.json" <<EOF
{
  "workflow": "Comic Drama Generation - Outline Only",
  "theme": "$THEME",
  "variant": $i,
  "total_chapters": $TOTAL_CHAPTERS,
  "pages_per_chapter": $PAGES_PER_CHAPTER,
  "status": {
    "story_planning": "pending"
  },
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

  echo "📁 任务目录：$TASK_DIR"
  echo "🎬 调用 shanyin-write 生成故事大纲..."

  # 这里需要调用 shanyin-write skill
  # 由于是在脚本中，我们创建一个临时提示文件
  cat > "$TASK_DIR/data/outline_request.txt" <<EOF
请使用 shanyin-write 的 cd-generator Mode 生成故事大纲。

**输入参数**：
- story_theme: "$THEME"
- genre: "$GENRE"
- language_level: "$LANGUAGE_LEVEL"
- total_chapters: $TOTAL_CHAPTERS
- pages_per_chapter: $PAGES_PER_CHAPTER
- art_style: "manga"
- variant: $i (第${i}个变体，请在情节、角色、冲突设计上有所不同)

**输出要求**：
- 直接输出 JSON 格式的 story_outline.json
- 不要 Markdown 解释
- 不要暂停确认
- 每个变体应该有不同的故事角度、角色设定或冲突设计

**目标文件**：$TASK_DIR/data/story_outline.json
EOF

  echo "   ⚠️  需要手动调用 /shanyin-write 或通过 Claude 生成"
  echo "   📄 请求文件：$TASK_DIR/data/outline_request.txt"

  TASK_DIRS+=("$TASK_DIR")

  # 避免过快生成导致时间戳重复
  sleep 2
done

# 保存批次信息
cat > "$BATCH_DIR/batch_info.json" <<EOF
{
  "batch_id": "$BATCH_ID",
  "theme": "$THEME",
  "genre": "$GENRE",
  "language_level": "$LANGUAGE_LEVEL",
  "batch_size": $BATCH_SIZE,
  "total_chapters": $TOTAL_CHAPTERS,
  "pages_per_chapter": $PAGES_PER_CHAPTER,
  "task_dirs": [
$(printf '    "%s"' "${TASK_DIRS[0]}")
$(for dir in "${TASK_DIRS[@]:1}"; do printf ',\n    "%s"' "$dir"; done)
  ],
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 批次目录已创建"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "批次目录：$BATCH_DIR"
echo "任务数量：${#TASK_DIRS[@]}"
echo ""
echo "📝 下一步："
echo "1. 为每个任务生成故事大纲（调用 /shanyin-write）"
echo "2. 运行评分脚本："
echo "   python3 $SCRIPT_DIR/score_story_outline.py ${TASK_DIRS[*]}"
echo ""
