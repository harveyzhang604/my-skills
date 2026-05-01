#!/usr/bin/env bash
# cd-generator 批量模式包装脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查是否是批量模式
if [[ "${1:-}" == "--batch" ]]; then
  shift
  exec "$SCRIPT_DIR/batch_generate_outlines.sh" "$@"
fi

# 否则执行正常的 cd-generator 流程
echo "请使用 /cd-generator 调用完整流程"
echo "或使用 --batch 模式批量生成故事大纲："
echo "  $0 --batch --theme '主题' --batch-size 10"
