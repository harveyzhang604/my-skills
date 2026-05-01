#!/bin/bash

# 同步任务状态
# 用法: ./sync_task_status.sh <task_dir>
#
# 这个脚本把 image_links.json、images/、progress.json、README.md、final_output.json
# 统一到同一个事实来源：本地是否已经存在有效图片文件。

set -e

TASK_DIR="$1"
GUARD="/Users/zhanghua/.claude/skills/cd-generator/scripts/task_path_guard.py"

if [ -z "$TASK_DIR" ]; then
    echo "用法: $0 <task_dir>"
    exit 1
fi

TASK_DIR="$(python3 "$GUARD" "$TASK_DIR")"

export TASK_DIR
python3 << 'PYEOF'
import json
import os
import re
from datetime import datetime, timezone

task_dir = os.environ["TASK_DIR"]
images_dir = os.path.join(task_dir, "images")
storyboards_dir = os.path.join(task_dir, "storyboards")
links_file = os.path.join(task_dir, "image_links.json")
progress_file = os.path.join(task_dir, "data", "progress.json")
readme_file = os.path.join(task_dir, "README.md")
final_output_file = os.path.join(task_dir, "output", "final_output.json")
status_report_file = os.path.join(task_dir, "image_status_report.md")

os.makedirs(images_dir, exist_ok=True)
now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

def parse_chapter_page(filename):
    match = re.search(r"chapter(\d+)_page(\d+)", filename)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))

def image_size(filename):
    path = os.path.join(images_dir, filename)
    if not os.path.exists(path) or os.path.getsize(path) <= 0:
        return None
    size = os.path.getsize(path)
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.2f}M"
    return f"{size / 1024:.0f}K"

expected = {}

if os.path.isdir(storyboards_dir):
    for name in sorted(os.listdir(storyboards_dir)):
        if not name.endswith(".json"):
            continue
        parsed = parse_chapter_page(name)
        if parsed:
            chapter, page = parsed
            expected[(chapter, page)] = f"chapter{chapter}_page{page}.png"

if os.path.isdir(images_dir):
    for name in sorted(os.listdir(images_dir)):
        if not name.endswith(".png"):
            continue
        parsed = parse_chapter_page(name)
        if parsed:
            expected.setdefault(parsed, name)

links = load_json(links_file, {"images": []})
records = {}
for img in links.get("images", []):
    chapter = int(img.get("chapter", 0) or 0)
    page = int(img.get("page", 0) or 0)
    if chapter and page:
        key = (chapter, page)
        records[key] = img
        expected.setdefault(key, img.get("filename") or f"chapter{chapter}_page{page}.png")

synced = []
for key in sorted(expected):
    chapter, page = key
    filename = expected[key]
    record = dict(records.get(key, {}))
    record.setdefault("chapter", chapter)
    record.setdefault("page", page)
    record["filename"] = filename

    size = image_size(filename)
    if size:
        record["status"] = "completed"
        record["file_size"] = size
        record.setdefault("completed_at", now)
    elif record.get("status") == "completed":
        record["status"] = "pending"
        record["note"] = "状态曾为 completed，但本地图片文件缺失，已自动改回 pending"
    else:
        record["status"] = record.get("status") or "pending"

    synced.append(record)

links = {
    "last_synced_at": now,
    "images": synced,
}
save_json(links_file, links)

total = len(synced)
completed = sum(1 for item in synced if item.get("status") == "completed")
failed = sum(1 for item in synced if item.get("status") == "failed")
pending = total - completed - failed
image_status = "completed" if total and completed == total else ("failed" if failed and not pending else "pending")

progress = load_json(progress_file, {})
if progress:
    progress.setdefault("status", {})
    progress["status"]["images"] = image_status
    progress["image_summary"] = {
        "total": total,
        "completed": completed,
        "pending": pending,
        "failed": failed,
        "last_synced_at": now,
    }
    save_json(progress_file, progress)

if os.path.exists(final_output_file):
    final = load_json(final_output_file, None)
    if isinstance(final, dict):
        story = final.get("story", {})
        for chapter in story.get("chapters", []):
            chapter_num = chapter.get("chapter_number")
            for page_data in chapter.get("pages", []):
                page_num = page_data.get("page_number")
                filename = f"chapter{chapter_num}_page{page_num}.png"
                if image_size(filename):
                    page_data["image_url"] = filename
                    page_data["image_status"] = "completed"
                else:
                    page_data["image_status"] = "pending"
        save_json(final_output_file, final)

status_lines = [
    "<!-- CD_GENERATOR_STATUS_START -->",
    "## 图片状态同步",
    "",
    f"- 最后同步：{now}",
    f"- 图片总数：{total}",
    f"- 已完成：{completed}",
    f"- 生成中：{pending}",
    f"- 失败：{failed}",
    "",
    "| 页面 | 状态 | 文件 | 链接 |",
    "| --- | --- | --- | --- |",
]
for item in synced:
    label = f"第{item['chapter']}章第{item['page']}页"
    status = item.get("status", "pending")
    status_zh = {"completed": "已完成", "failed": "失败", "pending": "生成中", "retrying": "重试中"}.get(status, status)
    link = item.get("link") or "-"
    status_lines.append(f"| {label} | {status_zh} | `{item.get('filename', '-')}` | {link} |")
status_lines.extend(["", "<!-- CD_GENERATOR_STATUS_END -->", ""])
status_block = "\n".join(status_lines)

link_lines = ["## 图片生成链接", ""]
for index, item in enumerate(synced, start=1):
    link = item.get("link") or "-"
    status = item.get("status", "pending")
    status_zh = {"completed": "已完成", "failed": "失败", "pending": "生成中", "retrying": "重试中"}.get(status, status)
    link_lines.append(f"{index}. 第{item['chapter']}章第{item['page']}页（{status_zh}）: {link}")
link_lines.append("")
links_block = "\n".join(link_lines)

if os.path.exists(readme_file):
    with open(readme_file, "r", encoding="utf-8") as f:
        readme = f.read()

    readme = re.sub(r"图片数\*\*: \d+张（[^）]*）", f"图片数**: {total}张（已完成 {completed}/{total}）", readme)
    if image_status == "completed":
        readme = readme.replace("🔄 图片生成中（预计5-15分钟）", f"✅ 图片生成完成（{completed}/{total}）")
        readme = readme.replace("图片生成中，完成后会自动下载到此处", "图片已生成并同步到此处")

    links_pattern = r"## 图片生成链接\n\n(?:\d+\. .*\n)+"
    if re.search(links_pattern, readme):
        readme = re.sub(links_pattern, links_block, readme)

    pattern = r"<!-- CD_GENERATOR_STATUS_START -->.*?<!-- CD_GENERATOR_STATUS_END -->\n?"
    if re.search(pattern, readme, flags=re.S):
        readme = re.sub(pattern, status_block, readme, flags=re.S)
    else:
        readme = readme.rstrip() + "\n\n" + status_block

    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(readme)

with open(status_report_file, "w", encoding="utf-8") as f:
    f.write("# 图片状态报告\n\n")
    f.write(status_block.replace("<!-- CD_GENERATOR_STATUS_START -->\n", "").replace("<!-- CD_GENERATOR_STATUS_END -->\n", ""))

print(f"同步完成：总数 {total}，已完成 {completed}，生成中 {pending}，失败 {failed}")
PYEOF
