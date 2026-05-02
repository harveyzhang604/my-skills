#!/usr/bin/env python3
"""
Generate story_outline.json with the shared OpenAI-compatible JSON client.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from llm_json_client import OpenAICompatibleJSONClient


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def update_progress(task_dir, status, summary=None, error=None):
    progress_path = Path(task_dir) / "data" / "progress.json"
    progress = load_json(progress_path, {})
    progress.setdefault("status", {})
    progress["status"]["story_planning"] = status
    progress["updated_at"] = now_iso()
    if summary:
        progress["story_planning_summary"] = summary
    if error:
        progress["story_planning_error"] = error
    save_json(progress_path, progress)


def validate_outline(outline, total_chapters):
    if not isinstance(outline, dict):
        raise ValueError("模型输出不是 JSON object")
    story = outline.get("story")
    if not isinstance(story, dict):
        raise ValueError("缺少 story object")
    chapters = story.get("chapter_outlines")
    if not isinstance(chapters, list) or not chapters:
        raise ValueError("缺少 story.chapter_outlines[]")
    if total_chapters and len(chapters) != total_chapters:
        raise ValueError(
            f"章节数量不匹配：期望 {total_chapters}，实际 {len(chapters)}"
        )
    for key in ["title", "title_en", "genre", "language_level", "summary"]:
        if not story.get(key):
            raise ValueError(f"story.{key} 为空")


def build_payload(args):
    return {
        "story_theme": args.theme,
        "genre": args.genre,
        "language_level": args.level,
        "total_chapters": args.chapters,
        "pages_per_chapter": args.pages,
        "art_style": args.art_style,
        "variant": args.variant,
        "target_file": str(Path(args.task_dir) / "data" / "story_outline.json"),
        "scene2talk_goal": (
            "Generate a comic-drama outline for mobile English speaking practice. "
            "Every chapter should later support short dialogue turns, clarification, "
            "negotiation, repair, emotional reaction, and practical spoken English."
        ),
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate cd-generator story_outline.json through an LLM."
    )
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--theme", required=True)
    parser.add_argument("--genre", default="workplace")
    parser.add_argument("--level", default="B1")
    parser.add_argument("--chapters", type=int, default=6)
    parser.add_argument("--pages", type=int, default=24)
    parser.add_argument("--variant", type=int, default=1)
    parser.add_argument("--art-style", default="manga")
    return parser.parse_args()


def main():
    args = parse_args()
    task_dir = Path(args.task_dir)
    outline_path = task_dir / "data" / "story_outline.json"

    print("⏳ shanyin-write：已收到 cd-generator 脚本调用，正在进入 story_outline 模式", flush=True)
    print(f"   - 目标文件：{outline_path}", flush=True)
    print(f"   - 范围：{args.chapters} 章，每章 {args.pages} 页，变体 {args.variant}", flush=True)

    try:
        update_progress(task_dir, "running")

        print("⏳ shanyin-write：正在规划角色、冲突和口语练习目标", flush=True)
        payload = build_payload(args)
        client = OpenAICompatibleJSONClient()

        print("⏳ shanyin-write：正在生成章节弧线和 page beats", flush=True)
        outline = client.request_json("generate_story_outline", payload)

        print("⏳ shanyin-write：正在校验 story_outline.json 结构", flush=True)
        validate_outline(outline, args.chapters)
        save_json(outline_path, outline)

        story = outline["story"]
        summary = {
            "title": story.get("title"),
            "title_en": story.get("title_en"),
            "character_count": len(story.get("characters", [])),
            "total_chapters": len(story.get("chapter_outlines", [])),
            "output": str(outline_path),
        }
        update_progress(task_dir, "completed", summary=summary)

        print("✅ shanyin-write：故事大纲已生成", flush=True)
        print(f"   - 故事标题：{summary['title']} / {summary['title_en']}", flush=True)
        print(f"   - 角色数量：{summary['character_count']}", flush=True)
        print(f"   - 章节数：{summary['total_chapters']}", flush=True)
        return 0
    except Exception as exc:
        update_progress(task_dir, "failed", error=str(exc))
        print(f"❌ shanyin-write：故事大纲生成失败：{exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
