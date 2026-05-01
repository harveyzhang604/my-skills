#!/usr/bin/env bash
# cd-generator 主入口脚本 - 支持批量模式和完整模式

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

# 显示使用说明
show_usage() {
  cat <<EOF
cd-generator - Comic Drama Generator for Scene2Talk

使用方法：

  模式A：批量大纲模式（生成多个变体并评分）
    $0 --batch --theme "主题" [选项]

  模式B：完整生成模式（生成可用于 Scene2Talk 的完整内容）
    $0 --theme "主题" [选项]
    $0 --continue <task_dir>  # 继续已有任务

选项：
  --batch              启用批量大纲模式
  --theme <主题>       故事主题（必需）
  --batch-size <数量>  批量模式：生成变体数量（默认10）
  --genre <类型>       类型：workplace/romance/fantasy/family/revenge
  --level <难度>       语言难度：A2/B1/B2
  --chapters <数量>    章节数（默认6）
  --pages <数量>       每章页数（默认24）
  --continue <目录>    继续已有任务（用于批量模式选中后继续）

示例：

  # 批量生成10个故事大纲并评分
  $0 --batch --theme "设计师的第一步" --batch-size 10 --genre workplace --level B1

  # 生成完整漫剧（6章×24页）
  $0 --theme "设计师的第一步" --genre workplace --level B1

  # 继续已选中的任务
  $0 --continue /path/to/task_dir

EOF
}

# 检查参数
if [[ $# -eq 0 ]]; then
  show_usage
  exit 0
fi

# 解析参数
MODE="full"
THEME=""
BATCH_SIZE=10
GENRE="workplace"
LEVEL="B1"
CHAPTERS=6
PAGES=24
CONTINUE_DIR=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --batch)
      MODE="batch"
      shift
      ;;
    --theme)
      THEME="$2"
      shift 2
      ;;
    --batch-size)
      BATCH_SIZE="$2"
      shift 2
      ;;
    --genre)
      GENRE="$2"
      shift 2
      ;;
    --level)
      LEVEL="$2"
      shift 2
      ;;
    --chapters)
      CHAPTERS="$2"
      shift 2
      ;;
    --pages)
      PAGES="$2"
      shift 2
      ;;
    --continue)
      CONTINUE_DIR="$2"
      MODE="continue"
      shift 2
      ;;
    --help|-h)
      show_usage
      exit 0
      ;;
    *)
      echo "未知参数: $1"
      show_usage
      exit 1
      ;;
  esac
done

# 执行对应模式
case $MODE in
  batch)
    if [[ -z "$THEME" ]]; then
      echo "错误：批量模式必须指定 --theme"
      exit 1
    fi
    echo "🚀 启动批量大纲模式..."
    exec "$SCRIPT_DIR/batch_generate_outlines.sh" \
      --theme "$THEME" \
      --batch-size "$BATCH_SIZE" \
      --genre "$GENRE" \
      --level "$LEVEL" \
      --chapters "$CHAPTERS" \
      --pages "$PAGES"
    ;;

  continue)
    if [[ -z "$CONTINUE_DIR" ]]; then
      echo "错误：继续模式必须指定 --continue <task_dir>"
      exit 1
    fi
    if [[ ! -d "$CONTINUE_DIR" ]]; then
      echo "错误：任务目录不存在: $CONTINUE_DIR"
      exit 1
    fi
    echo "🚀 继续任务: $CONTINUE_DIR"
    echo "⚠️  请通过 Claude 调用完整流程，从第2步（详细剧本）开始"
    echo "   任务目录: $CONTINUE_DIR"
    ;;

  full)
    if [[ -z "$THEME" ]]; then
      echo "错误：完整模式必须指定 --theme"
      exit 1
    fi
    echo "🚀 启动完整生成模式..."
    echo "⚠️  请通过 Claude 调用 /cd-generator skill"
    echo "   主题: $THEME"
    echo "   类型: $GENRE"
    echo "   难度: $LEVEL"
    echo "   章节: $CHAPTERS"
    echo "   页数: $PAGES"
    ;;
esac
