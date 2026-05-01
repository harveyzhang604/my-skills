#!/bin/bash

# 从 storyboards/ 提取英文图片提示词和中文图片提示词
# 用法: ./save_prompts.sh <task_dir>
#
# 约定：
# - prompts/      保存英文 image_prompt，用于实际图片生成
# - prompts_zh/   保存中文 image_prompt_zh，用于 HTML 预览和人工审稿

set -e

TASK_DIR="$1"
GUARD="/Users/zhanghua/.claude/skills/cd-generator/scripts/task_path_guard.py"

if [ -z "$TASK_DIR" ]; then
    echo "用法: $0 <task_dir>"
    exit 1
fi

TASK_DIR="$(python3 "$GUARD" "$TASK_DIR")"

STORYBOARDS_DIR="$TASK_DIR/storyboards"
PROMPTS_DIR="$TASK_DIR/prompts"
PROMPTS_ZH_DIR="$TASK_DIR/prompts_zh"

if [ ! -d "$STORYBOARDS_DIR" ]; then
    echo "错误：未找到分镜目录: $STORYBOARDS_DIR"
    exit 1
fi

mkdir -p "$PROMPTS_DIR" "$PROMPTS_ZH_DIR"

export TASK_DIR STORYBOARDS_DIR PROMPTS_DIR PROMPTS_ZH_DIR
python3 << 'PYEOF'
import json
import os
import sys

storyboards_dir = os.environ["STORYBOARDS_DIR"]
prompts_dir = os.environ["PROMPTS_DIR"]
prompts_zh_dir = os.environ["PROMPTS_ZH_DIR"]

saved = 0
missing_zh = []

for filename in sorted(os.listdir(storyboards_dir)):
    if not filename.endswith(".json"):
        continue

    path = os.path.join(storyboards_dir, filename)
    stem = filename[:-5]

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    storyboard = data.get("storyboard", {})
    prompt_en = (storyboard.get("image_prompt") or "").strip()
    prompt_zh = (storyboard.get("image_prompt_zh") or "").strip()

    if not prompt_en:
        print(f"错误：{filename} 缺少 storyboard.image_prompt")
        sys.exit(1)

    if not prompt_zh:
        missing_zh.append(filename)
        prompt_zh = "【缺少中文图片提示词】请在分镜 JSON 中补充 storyboard.image_prompt_zh。"

    with open(os.path.join(prompts_dir, f"{stem}.txt"), "w", encoding="utf-8") as f:
        f.write(prompt_en + "\n")

    with open(os.path.join(prompts_zh_dir, f"{stem}.txt"), "w", encoding="utf-8") as f:
        f.write(prompt_zh + "\n")

    saved += 1

print(f"已保存 {saved} 组提示词：英文 prompts/，中文 prompts_zh/")
if missing_zh:
    print("警告：以下分镜缺少 image_prompt_zh，已写入占位提醒：")
    for item in missing_zh:
        print(f"- {item}")
    sys.exit(2)
PYEOF
