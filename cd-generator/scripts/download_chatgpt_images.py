#!/usr/bin/env python3
"""Download generated ChatGPT images via the reusable chatgpt-image service."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from task_path_guard import require_task_dir

SERVICE = Path("/Users/zhanghua/.claude/skills/chatgpt-image/scripts/opencli_image_service.py")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def call_service(*args):
    proc = subprocess.run(
        [sys.executable, str(SERVICE), *args],
        text=True,
        capture_output=True,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {"ok": False, "status": "service_error", "error": output[-1000:]}
    data["_returncode"] = proc.returncode
    return data


def main():
    parser = argparse.ArgumentParser(description="Download ready ChatGPT images for a cd-generator task.")
    parser.add_argument("task_dir")
    parser.add_argument("images_dir", nargs="?")
    parser.add_argument("--chapters", default="1,2,3,4")
    parser.add_argument("--repair-retries", type=int, default=1)
    args = parser.parse_args()

    task_dir = require_task_dir(args.task_dir)
    images_dir = Path(args.images_dir).expanduser().resolve(strict=False) if args.images_dir else task_dir / "images"
    task_root = task_dir.resolve(strict=False)
    if not str(images_dir).startswith(str(task_root) + "/"):
        raise SystemExit(f"错误：images_dir must be inside task_dir: {task_root}")
    images_dir.mkdir(parents=True, exist_ok=True)

    links_path = task_dir / "image_links.json"
    data = load_json(links_path)
    chapters = {int(item.strip()) for item in args.chapters.split(",") if item.strip()}
    images = [item for item in data.get("images", []) if int(item.get("chapter", 0) or 0) in chapters]

    downloaded = 0
    already_exists = 0
    not_ready = 0
    failed = 0

    print(f"共 {len(images)} 张，开始逐个检查下载...")
    print("")

    for idx, img in enumerate(images, 1):
        chapter = int(img.get("chapter", 0) or 0)
        page = int(img.get("page", 0) or 0)
        link = img.get("link", "")
        filename = img.get("filename") or f"chapter{chapter}_page{page}.png"
        output_path = images_dir / filename

        if output_path.exists() and output_path.stat().st_size > 0:
            already_exists += 1
            print(f"[{idx:2d}/{len(images)}] 第{chapter}章第{page:2d}页: ✓ 已存在")
            continue
        if not link:
            not_ready += 1
            print(f"[{idx:2d}/{len(images)}] 第{chapter}章第{page:2d}页: ⏳ 无链接")
            continue

        status = call_service("status", "--link", link, "--repair-retries", str(args.repair_retries))
        image_status = status.get("status") or "PENDING"
        if not image_status.startswith("READY:"):
            not_ready += 1
            print(f"[{idx:2d}/{len(images)}] 第{chapter}章第{page:2d}页: ⏳ {image_status}")
            continue

        result = call_service(
            "download",
            "--link",
            link,
            "--output",
            str(output_path),
            "--repair-retries",
            str(args.repair_retries),
        )
        if result.get("ok") and result.get("status") == "completed" and output_path.exists():
            img["status"] = "completed"
            img["completed_at"] = result.get("completed_at")
            img["file_size"] = output_path.stat().st_size
            downloaded += 1
            print(f"[{idx:2d}/{len(images)}] 第{chapter}章第{page:2d}页: ✅")
        else:
            failed += 1
            img["last_download_error"] = result.get("error", "download failed")
            print(f"[{idx:2d}/{len(images)}] 第{chapter}章第{page:2d}页: ❌ {img['last_download_error'][:80]}")

    save_json(links_path, data)
    print("")
    print("=" * 50)
    print(f"✅ 本次新下载: {downloaded} 张")
    print(f"✓ 已存在: {already_exists} 张")
    print(f"⏳ 未就绪: {not_ready} 张")
    print(f"❌ 失败: {failed} 张")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
