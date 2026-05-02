#!/usr/bin/env python3
"""
Lightweight generated-image audit for cd-generator.

This does not judge visual semantics. It checks the file-level gates that must
hold before human or model visual review: expected files, readable PNGs, 16:9
shape, minimum size, and image_links status consistency.
"""

import argparse
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

from task_path_guard import require_task_dir


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path, default=None):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_png_size(path):
    with open(path, "rb") as f:
        header = f.read(24)
    if len(header) < 24 or not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not a PNG file")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def expected_pages(task_dir, chapter=None):
    storyboards_dir = task_dir / "storyboards"
    pages = []
    for path in sorted(storyboards_dir.glob("chapter*_page*.json")):
        stem = path.stem
        try:
            ch = int(stem.split("_page")[0].replace("chapter", ""))
            pg = int(stem.split("_page")[1])
        except (IndexError, ValueError):
            continue
        if chapter is not None and ch != chapter:
            continue
        pages.append((ch, pg))
    return pages


def link_records(task_dir):
    data = load_json(task_dir / "image_links.json", {"images": []}) or {"images": []}
    records = {}
    for item in data.get("images", []):
        try:
            key = (int(item.get("chapter", 0)), int(item.get("page", 0)))
        except (TypeError, ValueError):
            continue
        records[key] = item
    return records


def audit_image(task_dir, chapter, page, records):
    filename = f"chapter{chapter}_page{page}.png"
    path = task_dir / "images" / filename
    record = records.get((chapter, page), {})
    issues = []
    item = {
        "chapter": chapter,
        "page": page,
        "filename": filename,
        "exists": path.exists(),
        "status": record.get("status") or "missing_record",
        "issues": issues,
    }

    if not path.exists():
        issues.append({
            "severity": "warning",
            "code": "image_missing",
            "message": f"缺少图片文件 images/{filename}",
            "suggestion": "生成或下载该页图片后重新运行审查。",
        })
        return item

    size = path.stat().st_size
    item["file_size"] = size
    if size < 200_000:
        issues.append({
            "severity": "error",
            "code": "image_file_too_small",
            "message": f"图片文件过小：{size} bytes，可能下载失败或不是最终图。",
            "suggestion": "重新下载或重新生成该页图片。",
        })

    try:
        width, height = parse_png_size(path)
        item["width"] = width
        item["height"] = height
        item["aspect_ratio"] = round(width / height, 4) if height else None
    except Exception as exc:
        issues.append({
            "severity": "error",
            "code": "image_unreadable_png",
            "message": f"无法读取 PNG 尺寸：{exc}",
            "suggestion": "确认文件是有效 PNG，必要时重新生成。",
        })
        return item

    ratio = width / height if height else 0
    target = 16 / 9
    if abs(ratio - target) > 0.08:
        issues.append({
            "severity": "warning",
            "code": "image_not_16x9",
            "message": f"图片比例不是稳定 16:9：{width}x{height}",
            "suggestion": "重新生成时强化 16:9 widescreen landscape composition。",
        })

    if width < 1200 or height < 650:
        issues.append({
            "severity": "warning",
            "code": "image_resolution_low",
            "message": f"图片分辨率偏低：{width}x{height}",
            "suggestion": "如用于正式导入，建议使用更高分辨率图片。",
        })

    if record and record.get("status") != "completed":
        issues.append({
            "severity": "info",
            "code": "image_link_status_not_completed",
            "message": f"本地图片存在，但 image_links.json 状态为 {record.get('status')}",
            "suggestion": "运行 sync_task_status.sh 同步状态。",
        })

    return item


def parse_args():
    parser = argparse.ArgumentParser(description="Audit generated cd-generator image files.")
    parser.add_argument("task_dir")
    parser.add_argument("--chapter", type=int)
    parser.add_argument("--pages", nargs="*", type=int)
    parser.add_argument("--output")
    return parser.parse_args()


def main():
    args = parse_args()
    task_dir = require_task_dir(args.task_dir)
    pages = expected_pages(task_dir, args.chapter)
    if args.pages:
        wanted = set(args.pages)
        pages = [(chapter, page) for chapter, page in pages if page in wanted]

    records = link_records(task_dir)
    report = {
        "checked_at": now_iso(),
        "task_dir": str(task_dir),
        "images": [],
        "summary": {
            "expected_count": len(pages),
            "existing_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
        },
    }

    for chapter, page in pages:
        item = audit_image(task_dir, chapter, page, records)
        report["images"].append(item)
        if item["exists"]:
            report["summary"]["existing_count"] += 1
        for issue in item["issues"]:
            report["summary"][f"{issue['severity']}_count"] += 1

    output = Path(args.output) if args.output else task_dir / "quality" / "image_audit.json"
    save_json(output, report)

    print("🖼️ 图片文件审查")
    print(f"   - 预期：{report['summary']['expected_count']}")
    print(f"   - 已存在：{report['summary']['existing_count']}")
    print(f"   - 错误：{report['summary']['error_count']}")
    print(f"   - 警告：{report['summary']['warning_count']}")
    print(f"   - 信息：{report['summary']['info_count']}")
    for item in report["images"]:
        if not item["issues"]:
            continue
        print(f"⚠️ chapter{item['chapter']}_page{item['page']}: {len(item['issues'])} 个问题")
        for issue in item["issues"][:5]:
            print(f"   - [{issue['code']}] {issue['message']}")
    print(f"📄 报告已保存：{output}")
    return 1 if report["summary"]["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
