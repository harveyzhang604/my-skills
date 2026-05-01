#!/usr/bin/env python3
"""Integrate cd-generator intermediate artifacts into final_output.json."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from task_path_guard import require_task_dir


def load_json(path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def image_records(task_dir):
    records = {}
    links = load_json(task_dir / "image_links.json", {"images": []}) or {"images": []}
    for item in links.get("images", []):
        chapter = item.get("chapter")
        page = item.get("page")
        if chapter is None or page is None:
            continue
        records[(int(chapter), int(page))] = item
    return records


def integrate(task_dir):
    task_dir = Path(task_dir)
    outline_path = task_dir / "data" / "story_outline.json"
    outline = load_json(outline_path, {})
    story = outline.get("story", outline) if isinstance(outline, dict) else {}
    if not story:
        raise RuntimeError(f"Missing or empty story outline: {outline_path}")

    scripts_dir = task_dir / "scripts"
    chapters = []
    records = image_records(task_dir)
    for script_path in sorted(scripts_dir.glob("chapter*.json")):
        chapter = load_json(script_path)
        if not isinstance(chapter, dict):
            continue
        chapter_num = int(chapter.get("chapter_number") or len(chapters) + 1)
        for page_data in chapter.get("pages", []) or []:
            page_num = int(page_data.get("page_number") or 0)
            if not page_num:
                continue
            image_file = f"chapter{chapter_num}_page{page_num}.png"
            local_image = task_dir / "images" / image_file
            record = records.get((chapter_num, page_num), {})
            if local_image.exists() and local_image.stat().st_size > 0:
                page_data["image_url"] = image_file
                page_data["image_status"] = "completed"
            else:
                page_data["image_status"] = record.get("status") or "pending"
            if record.get("generation_mode"):
                page_data["image_generation_mode"] = record["generation_mode"]
        chapters.append(chapter)

    story["chapters"] = chapters
    story["total_chapters"] = story.get("total_chapters") or len(chapters)
    story["total_pages"] = sum(len(chapter.get("pages", []) or []) for chapter in chapters)
    story["total_dialogues"] = sum(
        len(page.get("dialogues", []) or [])
        for chapter in chapters
        for page in chapter.get("pages", []) or []
    )

    final_data = {
        "story": story,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    save_json(task_dir / "output" / "final_output.json", final_data)

    progress_path = task_dir / "data" / "progress.json"
    progress = load_json(progress_path, {})
    if isinstance(progress, dict):
        progress.setdefault("status", {})
        progress["status"]["integration"] = "completed"
        progress["integration_summary"] = {
            "final_output": "output/final_output.json",
            "chapters": story["total_chapters"],
            "pages": story["total_pages"],
            "dialogues": story["total_dialogues"],
        }
        save_json(progress_path, progress)

    return final_data


def main():
    parser = argparse.ArgumentParser(description="Build final_output.json for a cd-generator task.")
    parser.add_argument("task_dir")
    args = parser.parse_args()
    final_data = integrate(require_task_dir(args.task_dir))
    story = final_data["story"]
    print("Integration complete")
    print(f"chapters={story.get('total_chapters')} pages={story.get('total_pages')} dialogues={story.get('total_dialogues')}")


if __name__ == "__main__":
    main()
