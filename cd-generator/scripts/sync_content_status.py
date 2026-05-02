#!/usr/bin/env python3
"""Synchronize cd-generator content progress from files on disk."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from task_path_guard import require_task_dir


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def story_from_outline(task_dir: Path) -> dict:
    outline = load_json(task_dir / "data" / "story_outline.json", default={}) or {}
    return outline.get("story", outline) if isinstance(outline, dict) else {}


def expected_counts(story: dict) -> tuple[int, int, int]:
    chapters = int(story.get("total_chapters") or len(story.get("chapter_outlines") or []) or 0)
    total_pages = int(story.get("total_pages") or 0)
    pages_per_chapter = int(total_pages / chapters) if chapters and total_pages else 0
    if not pages_per_chapter:
        pages_per_chapter = max(
            [len(ch.get("page_beats") or []) for ch in story.get("chapter_outlines", [])] or [0]
        )
    return chapters, pages_per_chapter, chapters * pages_per_chapter


def chapter_page_counts(task_dir: Path) -> dict[str, dict]:
    result = {}
    for path in sorted((task_dir / "scripts").glob("chapter*.json")):
        match = re.search(r"chapter(\d+)\.json$", path.name)
        if not match:
            continue
        data = load_json(path, default={}) or {}
        pages = data.get("pages") or []
        result[match.group(1)] = {
            "pages_count": len(pages),
            "dialogue_count": sum(len(page.get("dialogues") or []) for page in pages),
            "output": str(path),
        }
    return result


def count_page_files(directory: Path, suffix: str) -> int:
    if not directory.exists():
        return 0
    return sum(1 for path in directory.glob(f"chapter*_page*{suffix}") if path.is_file())


def image_counts(task_dir: Path) -> dict:
    links = load_json(task_dir / "image_links.json", default={"images": []}) or {"images": []}
    records = links.get("images") or []
    completed = 0
    for record in records:
        filename = record.get("filename") or f"chapter{record.get('chapter')}_page{record.get('page')}.png"
        if record.get("status") == "completed" and (task_dir / "images" / filename).is_file():
            completed += 1
    return {
        "tracked": len(records),
        "completed": completed,
        "pending": max(0, len(records) - completed),
    }


def sync(task_dir: Path) -> dict:
    story = story_from_outline(task_dir)
    expected_chapters, pages_per_chapter, expected_pages = expected_counts(story)
    chapters = chapter_page_counts(task_dir)
    completed_chapters = sum(1 for item in chapters.values() if item["pages_count"] >= pages_per_chapter)
    script_pages = sum(item["pages_count"] for item in chapters.values())
    storyboard_count = count_page_files(task_dir / "storyboards", ".json")
    prompt_count = count_page_files(task_dir / "prompts", ".txt")
    prompt_zh_count = count_page_files(task_dir / "prompts_zh", ".txt")
    prompt_refs_count = count_page_files(task_dir / "prompts_with_refs", ".txt")
    final_output_exists = (task_dir / "output" / "final_output.json").is_file()
    preview_exists = (task_dir / "output" / "preview.html").is_file()
    images = image_counts(task_dir)

    progress_path = task_dir / "data" / "progress.json"
    progress = load_json(progress_path, default={}) or {}
    progress.setdefault("status", {})
    progress["content_expected"] = {
        "chapters": expected_chapters,
        "pages_per_chapter": pages_per_chapter,
        "pages": expected_pages,
    }
    progress["chapter_scripts"] = {
        chapter: {
            "status": "completed" if item["pages_count"] >= pages_per_chapter else "partial",
            "updated_at": progress.get("chapter_scripts", {}).get(chapter, {}).get("updated_at", now_iso()),
            "summary": item,
        }
        for chapter, item in sorted(chapters.items(), key=lambda pair: int(pair[0]))
    }
    progress["content_summary"] = {
        "script_chapters_completed": completed_chapters,
        "script_pages": script_pages,
        "storyboards": storyboard_count,
        "prompts": prompt_count,
        "prompts_zh": prompt_zh_count,
        "prompts_with_refs": prompt_refs_count,
        "final_output": final_output_exists,
        "preview": preview_exists,
        "images": images,
    }
    progress["status"]["chapter_scripts"] = "completed" if completed_chapters >= expected_chapters else "running"
    progress["status"]["storyboards"] = "completed" if storyboard_count >= expected_pages else "running"
    progress["status"]["prompts"] = "completed" if prompt_count >= expected_pages and prompt_zh_count >= expected_pages else "running"
    progress["status"]["prompts_with_refs"] = "completed" if prompt_refs_count >= expected_pages else "running"
    progress["status"]["integration"] = "completed" if final_output_exists else "pending"
    progress["status"]["preview"] = "completed" if preview_exists else "pending"
    progress["updated_at"] = now_iso()

    if progress["status"]["storyboards"] == "completed":
        progress.pop("storyboards_error", None)
    save_json(progress_path, progress)
    return progress


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize cd-generator content progress.")
    parser.add_argument("task_dir")
    args = parser.parse_args()
    progress = sync(require_task_dir(args.task_dir))
    summary = progress.get("content_summary", {})
    expected = progress.get("content_expected", {})
    print(
        "内容状态同步完成："
        f"剧本 {summary.get('script_pages', 0)}/{expected.get('pages', 0)} 页，"
        f"分镜 {summary.get('storyboards', 0)}/{expected.get('pages', 0)}，"
        f"增强提示词 {summary.get('prompts_with_refs', 0)}/{expected.get('pages', 0)}，"
        f"图片完成 {summary.get('images', {}).get('completed', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
