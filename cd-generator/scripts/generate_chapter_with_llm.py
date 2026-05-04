#!/usr/bin/env python3
"""
Generate detailed chapter scripts with chunked LLM calls.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from llm_json_client import OpenAICompatibleJSONClient
from generate_conversation_missions import normalize_mission


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def update_progress(task_dir, chapter_number, status, summary=None, error=None):
    progress_path = Path(task_dir) / "data" / "progress.json"
    progress = load_json(progress_path, default={})
    progress.setdefault("status", {})
    progress["status"]["chapter_scripts"] = status
    progress.setdefault("chapter_scripts", {})
    progress["chapter_scripts"][str(chapter_number)] = {
        "status": status,
        "updated_at": now_iso(),
    }
    if summary:
        progress["chapter_scripts"][str(chapter_number)]["summary"] = summary
    if error:
        progress["chapter_scripts"][str(chapter_number)]["error"] = error
    progress["updated_at"] = now_iso()
    save_json(progress_path, progress)


def story_from_outline(outline):
    return outline.get("story", outline)


def normalize_chapter_outline(story, chapter_number):
    chapters = story.get("chapter_outlines", [])
    for chapter in chapters:
        if int(chapter.get("chapter_number", 0)) == chapter_number:
            return chapter
    index = chapter_number - 1
    if 0 <= index < len(chapters):
        return chapters[index]
    raise ValueError(f"找不到第 {chapter_number} 章大纲")


def page_beats_for_range(chapter_outline, start_page, end_page):
    beats = chapter_outline.get("page_beats") or []
    if not beats:
        return [
            {"page_number": n, "beat": f"Continue chapter beat for page {n}"}
            for n in range(start_page, end_page + 1)
        ]
    selected = []
    for page_number in range(start_page, end_page + 1):
        beat = beats[(page_number - 1) % len(beats)]
        selected.append({"page_number": page_number, "beat": beat})
    return selected


def build_payload(args, story, chapter_outline, start_page, end_page, previous_summary):
    characters = story.get("characters", [])
    return {
        "story": {
            "title": story.get("title"),
            "title_en": story.get("title_en"),
            "genre": story.get("genre"),
            "language_level": story.get("language_level") or args.level,
            "summary": story.get("summary"),
            "characters": characters,
        },
        "chapter": {
            "chapter_number": args.chapter,
            "title": chapter_outline.get("title"),
            "title_en": chapter_outline.get("title_en"),
            "summary": chapter_outline.get("summary"),
            "key_conflict": chapter_outline.get("key_conflict"),
            "emotional_beat": chapter_outline.get("emotional_beat"),
        },
        "page_range": {"start": start_page, "end": end_page},
        "page_beats": page_beats_for_range(chapter_outline, start_page, end_page),
        "previous_summary": previous_summary,
        "constraints": {
            "language_level": args.level,
            "dialogue_lines_per_page": args.dialogues,
            "scene2talk_goal": (
                "Every page should support spoken English practice with concrete dialogue "
                "turns and visible action for later storyboard/image generation."
            ),
        },
    }


def validate_pages(result, start_page, end_page, language_level=None, chapter_num=1):
    pages = result.get("pages") if isinstance(result, dict) else None
    if not isinstance(pages, list):
        raise ValueError("模型输出缺少 pages[]")
    expected = list(range(start_page, end_page + 1))
    actual = [int(page.get("page_number", -1)) for page in pages]
    if actual != expected:
        raise ValueError(f"页码不匹配：期望 {expected}，实际 {actual}")
    for page in pages:
        dialogues = page.get("dialogues")
        if not isinstance(dialogues, list) or not dialogues:
            raise ValueError(f"第 {page.get('page_number')} 页缺少 dialogues[]")
        if not page.get("speaking_goal"):
            raise ValueError(f"第 {page.get('page_number')} 页缺少 speaking_goal")
        narrator_lines = 0
        for line in dialogues:
            if not line.get("speaker") or not line.get("text_en") or not line.get("text_zh"):
                raise ValueError(f"第 {page.get('page_number')} 页存在不完整对白")
            speaker = str(line.get("speaker_en") or line.get("speaker") or "").lower()
            if speaker in {"narrator", "system", "sfx"}:
                narrator_lines += 1
            word_count = len(str(line.get("text_en") or "").split())
            if word_count > 22:
                raise ValueError(
                    f"第 {page.get('page_number')} 页存在过长英文对白：{word_count} words"
                )
        if narrator_lines > max(1, len(dialogues) // 4):
            raise ValueError(f"第 {page.get('page_number')} 页旁白/系统类对白过多")
        mission = page.get("conversation_mission")
        if not isinstance(mission, dict):
            raise ValueError(f"第 {page.get('page_number')} 页缺少 conversation_mission")
        try:
            page["conversation_mission"] = normalize_mission(
                mission,
                chapter_num=chapter_num,
                page_num=int(page.get("page_number") or 0),
                scene_location=page.get("scene_location", ""),
                language_level=language_level or page.get("language_level") or "B1",
                vocabulary_focus=page.get("vocabulary_focus", []),
                estimated_turns=len(dialogues),
            )
        except Exception as exc:
            raise ValueError(
                f"第 {page.get('page_number')} 页 conversation_mission 无效：{exc}"
            ) from exc
    return pages


def summarize_pages(pages):
    if not pages:
        return ""
    parts = []
    for page in pages[-2:]:
        title = page.get("page_title") or f"Page {page.get('page_number')}"
        arc = page.get("emotional_arc") or ""
        parts.append(f"{title}: {arc}")
    return " | ".join(parts)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate one cd-generator chapter script through chunked LLM calls."
    )
    parser.add_argument("task_dir")
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--pages", type=int, default=None)
    parser.add_argument("--chunk-size", type=int, default=2)
    parser.add_argument("--level", default=None)
    parser.add_argument("--dialogues", type=int, default=12)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint if available")
    return parser.parse_args()


def load_checkpoint(task_dir, chapter_number):
    """Load checkpoint if exists."""
    checkpoint_path = Path(task_dir) / "scripts" / f"chapter{chapter_number}.checkpoint.json"
    if checkpoint_path.exists():
        return load_json(checkpoint_path)
    return None


def save_checkpoint(task_dir, chapter_number, all_pages, previous_summary):
    """Save checkpoint after each chunk."""
    checkpoint_path = Path(task_dir) / "scripts" / f"chapter{chapter_number}.checkpoint.json"
    checkpoint_data = {
        "pages": all_pages,
        "previous_summary": previous_summary,
        "last_page": len(all_pages),
        "updated_at": now_iso(),
    }
    save_json(checkpoint_path, checkpoint_data)


def remove_checkpoint(task_dir, chapter_number):
    """Remove checkpoint after successful completion."""
    checkpoint_path = Path(task_dir) / "scripts" / f"chapter{chapter_number}.checkpoint.json"
    if checkpoint_path.exists():
        checkpoint_path.unlink()


def main():
    args = parse_args()
    task_dir = Path(args.task_dir)
    outline_path = task_dir / "data" / "story_outline.json"
    output_path = task_dir / "scripts" / f"chapter{args.chapter}.json"

    print("⏳ shanyin-write：已收到 cd-generator 脚本调用，正在进入 chapter_script 模式", flush=True)
    print(f"   - 目标文件：{output_path}", flush=True)
    print(f"   - 章节：第 {args.chapter} 章", flush=True)

    try:
        if output_path.exists() and not args.force and not args.resume:
            print(f"✅ shanyin-write：第 {args.chapter} 章已存在，跳过：{output_path}", flush=True)
            return 0

        outline = load_json(outline_path)
        story = story_from_outline(outline)
        chapter_outline = normalize_chapter_outline(story, args.chapter)
        level = args.level or story.get("language_level") or "B1"
        args.level = level

        page_count = args.pages
        if page_count is None:
            page_count = len(chapter_outline.get("page_beats") or []) or int(story.get("pages_per_chapter") or 0) or 6

        # Check for checkpoint
        checkpoint = load_checkpoint(task_dir, args.chapter) if args.resume else None
        all_pages = []
        previous_summary = ""
        start_from = 1

        if checkpoint:
            all_pages = checkpoint.get("pages", [])
            previous_summary = checkpoint.get("previous_summary", "")
            start_from = checkpoint.get("last_page", 0) + 1
            print(f"📂 shanyin-write：从断点恢复，已完成 {len(all_pages)} 页，从第 {start_from} 页继续", flush=True)
        else:
            print("⏳ shanyin-write：正在读取故事大纲和章节连续性", flush=True)

        update_progress(task_dir, args.chapter, "running")

        client = OpenAICompatibleJSONClient()
        for start in range(start_from, page_count + 1, args.chunk_size):
            end = min(start + args.chunk_size - 1, page_count)
            print(f"⏳ shanyin-write：正在生成第 {args.chapter} 章 {start}-{end}/{page_count} 页", flush=True)
            payload = build_payload(args, story, chapter_outline, start, end, previous_summary)
            result = client.request_json("generate_chapter_pages", payload)
            pages = validate_pages(result, start, end, language_level=level, chapter_num=args.chapter)
            all_pages.extend(pages)
            previous_summary = summarize_pages(all_pages)

            # Save checkpoint after each successful chunk
            save_checkpoint(task_dir, args.chapter, all_pages, previous_summary)

            update_progress(
                task_dir,
                args.chapter,
                "running",
                summary={
                    "completed_pages": len(all_pages),
                    "total_pages": page_count,
                    "output": str(output_path),
                },
            )

        chapter = {
            "chapter_number": args.chapter,
            "title": chapter_outline.get("title"),
            "title_en": chapter_outline.get("title_en"),
            "summary": chapter_outline.get("summary"),
            "pages": all_pages,
        }
        print("⏳ shanyin-write：正在校验并写入章节 JSON", flush=True)
        save_json(output_path, chapter)

        # Remove checkpoint after successful completion
        remove_checkpoint(task_dir, args.chapter)

        dialogue_count = sum(len(page.get("dialogues", [])) for page in all_pages)
        summary = {
            "pages_count": len(all_pages),
            "dialogue_count": dialogue_count,
            "output": str(output_path),
        }
        update_progress(task_dir, args.chapter, "completed", summary=summary)
        print(f"✅ shanyin-write：第 {args.chapter} 章剧本已完成", flush=True)
        print(f"   - 页数：{summary['pages_count']}", flush=True)
        print(f"   - 对话数：{summary['dialogue_count']}", flush=True)
        return 0
    except Exception as exc:
        update_progress(task_dir, args.chapter, "failed", error=str(exc))
        print(f"❌ shanyin-write：第 {args.chapter} 章生成失败：{exc}", file=sys.stderr, flush=True)
        print(f"💡 提示：使用 --resume 参数可从断点继续生成", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
