#!/usr/bin/env python3
"""
Repair pages flagged by the oral-practice audit.
"""

import argparse
import json
import re
from pathlib import Path

from audit_oral_practice_fit import audit_task, save_json
from llm_json_client import OpenAICompatibleJSONClient


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_location(location):
    match = re.match(r"chapter(\d+)_page(\d+)$", location)
    if not match:
        raise ValueError(f"无法解析 location: {location}")
    return int(match.group(1)), int(match.group(2))


def collect_repair_targets(report):
    targets = {}
    for chapter in report.get("chapters", []):
        for issue in chapter.get("issues", []):
            if issue.get("severity") not in {"error", "warning"}:
                continue
            location = issue.get("location", "")
            if ".dialogues[" in location:
                location = location.split(".dialogues[", 1)[0]
            chapter_number, page_number = parse_location(location)
            targets.setdefault((chapter_number, page_number), []).append(issue)
    return targets


def find_page(chapter, page_number):
    for index, page in enumerate(chapter.get("pages", [])):
        if int(page.get("page_number", 0)) == page_number:
            return index, page
    raise ValueError(f"找不到第 {page_number} 页")


def validate_repaired_page(page, expected_number):
    if int(page.get("page_number", 0)) != expected_number:
        raise ValueError(f"修复后页码错误：{page.get('page_number')} != {expected_number}")
    if not page.get("speaking_goal"):
        raise ValueError("修复后仍缺少 speaking_goal")
    dialogues = page.get("dialogues")
    if not isinstance(dialogues, list) or len(dialogues) < 8:
        raise ValueError("修复后对白数量不足")
    for line in dialogues:
        if not line.get("speaker") or not line.get("speaker_en"):
            raise ValueError("修复后存在缺少 speaker 的对白")
        if not line.get("text_en") or not line.get("text_zh"):
            raise ValueError("修复后存在缺少中英文文本的对白")


def repair_page(client, story, chapter, page, issues):
    payload = {
        "story": {
            "title": story.get("title"),
            "title_en": story.get("title_en"),
            "genre": story.get("genre"),
            "language_level": story.get("language_level"),
            "summary": story.get("summary"),
            "characters": story.get("characters", []),
        },
        "chapter": {
            "chapter_number": chapter.get("chapter_number"),
            "title": chapter.get("title"),
            "title_en": chapter.get("title_en"),
            "summary": chapter.get("summary"),
        },
        "page": page,
        "issues": issues,
    }
    return client.request_json("repair_oral_practice_page", payload)


def parse_args():
    parser = argparse.ArgumentParser(description="Repair oral-practice warnings/errors in chapter scripts.")
    parser.add_argument("task_dir")
    parser.add_argument("--chapters", nargs="*", type=int)
    parser.add_argument("--max-pages", type=int, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    task_dir = Path(args.task_dir)
    outline = load_json(task_dir / "data" / "story_outline.json")
    story = outline.get("story", outline)

    report = audit_task(task_dir, args.chapters)
    targets = collect_repair_targets(report)
    if args.max_pages is not None:
        targets = dict(list(targets.items())[:args.max_pages])

    if not targets:
        print("✅ 没有需要修复的口语适配问题")
        return 0

    print(f"🛠️  准备修复 {len(targets)} 个页面")
    client = OpenAICompatibleJSONClient()

    for (chapter_number, page_number), issues in targets.items():
        chapter_path = task_dir / "scripts" / f"chapter{chapter_number}.json"
        chapter = load_json(chapter_path)
        page_index, page = find_page(chapter, page_number)
        print(f"⏳ 修复 chapter{chapter_number}_page{page_number}: {', '.join(i['code'] for i in issues)}")
        repaired = repair_page(client, story, chapter, page, issues)
        validate_repaired_page(repaired, page_number)
        chapter["pages"][page_index] = repaired
        save_json(chapter_path, chapter)
        print(f"✅ 已修复 chapter{chapter_number}_page{page_number}")

    repaired_report = audit_task(task_dir, args.chapters)
    report_path = task_dir / "quality" / "oral_practice_audit.json"
    save_json(report_path, repaired_report)
    summary = repaired_report["summary"]
    print("📣 修复后审查结果")
    print(f"   - 错误：{summary['error_count']}")
    print(f"   - 警告：{summary['warning_count']}")
    print(f"   - 报告：{report_path}")
    return 1 if summary["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
