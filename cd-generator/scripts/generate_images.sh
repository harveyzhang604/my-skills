#!/bin/bash

# 兼容入口：批量图片生成统一交给 smart_image_manager.sh。
# smart_image_manager.sh 负责批量、质检、状态记录；单张 OpenCLI 生图能力由
# chatgpt-image/scripts/opencli_image_service.py 提供。

set -e

TASK_DIR="$1"

if [ -z "$TASK_DIR" ]; then
    echo "用法: $0 <task_dir>"
    exit 1
fi

exec /Users/zhanghua/.claude/skills/cd-generator/scripts/smart_image_manager.sh "$TASK_DIR"
