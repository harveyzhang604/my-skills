#!/usr/bin/env python3
"""
Audit generated chapter scripts for oral-practice fit.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


MOVE_MARKERS = [
    "can ",
    "could ",
    "please",
    "let's",
    "i think",
    "i need",
    "help",
    "sorry",
    "wait",
    "why",
    "what",
    "how",
    "are you",
    "do you",
    "should we",
    "we need",
    "tell me",
    "say that",
    "understand",
    "mean",
    "try",
    "promise",
    "agree",
    "ready",
]

STAGE_SPEAKERS = {"narrator", "system", "sfx"}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def count_conversation_moves(dialogues):
    moves = 0
    for line in dialogues:
        text = str(line.get("text_en") or "")
        low = text.lower()
        if "?" in text or any(marker in low for marker in MOVE_MARKERS):
            moves += 1
    return moves


def audit_page(chapter_number, page):
    issues = []
    dialogues = page.get("dialogues") or []
    page_number = page.get("page_number")
    location = f"chapter{chapter_number}_page{page_number}"

    if not page.get("speaking_goal"):
        issues.append({
            "severity": "error",
            "code": "missing_speaking_goal",
            "location": location,
            "message": "缺少 speaking_goal，无法判断本页练什么口语。",
            "suggestion": "补充一个具体沟通任务，例如澄清、请求帮助、表达担心、做决定。",
        })

    if len(dialogues) < 8:
        issues.append({
            "severity": "error",
            "code": "too_few_dialogues",
            "location": location,
            "message": f"本页只有 {len(dialogues)} 句对白，口语练习量不足。",
            "suggestion": "补到至少 8-12 句；正式页建议 12-16 句。",
        })

    stage_count = 0
    long_lines = []
    for index, line in enumerate(dialogues, start=1):
        speaker = str(line.get("speaker_en") or line.get("speaker") or "").strip().lower()
        if speaker in STAGE_SPEAKERS:
            stage_count += 1
        text_en = str(line.get("text_en") or "").strip()
        text_zh = str(line.get("text_zh") or "").strip()
        if not text_en or not text_zh:
            issues.append({
                "severity": "error",
                "code": "missing_dialogue_text",
                "location": f"{location}.dialogues[{index}]",
                "message": "对白缺少 text_en 或 text_zh。",
                "suggestion": "补齐中英文对白。",
            })
        word_count = len(text_en.split())
        if word_count > 22:
            long_lines.append((index, word_count, text_en))

    if stage_count > max(1, len(dialogues) // 4):
        issues.append({
            "severity": "warning",
            "code": "too_much_stage_speaker",
            "location": location,
            "message": f"旁白/系统类对白过多：{stage_count}/{len(dialogues)}。",
            "suggestion": "把旁白信息改成角色之间可说出口的对话。",
        })

    for index, word_count, text in long_lines:
        issues.append({
            "severity": "warning",
            "code": "english_line_too_long",
            "location": f"{location}.dialogues[{index}]",
            "message": f"英文句子过长：{word_count} words。",
            "suggestion": f"拆成更短、更适合跟读的口语句：{text}",
        })

    moves = count_conversation_moves(dialogues)
    if moves < 3:
        issues.append({
            "severity": "warning",
            "code": "few_conversation_moves",
            "location": location,
            "message": f"本页可练的对话动作偏少：{moves} 个。",
            "suggestion": "增加提问、澄清、确认理解、请求帮助、表达担心、建议或承诺。",
        })

    return {
        "location": location,
        "dialogue_count": len(dialogues),
        "conversation_moves": moves,
        "speaking_goal": page.get("speaking_goal"),
        "issues": issues,
    }


def audit_task(task_dir, chapters=None):
    task_dir = Path(task_dir)
    scripts_dir = task_dir / "scripts"
    chapter_files = sorted(scripts_dir.glob("chapter*.json"))
    if chapters:
        wanted = {int(chapter) for chapter in chapters}
        chapter_files = [
            path for path in chapter_files
            if int(path.stem.replace("chapter", "")) in wanted
        ]

    report = {
        "checked_at": now_iso(),
        "task_dir": str(task_dir),
        "chapters": [],
        "summary": {
            "chapter_count": 0,
            "page_count": 0,
            "dialogue_count": 0,
            "error_count": 0,
            "warning_count": 0,
        },
    }

    for chapter_file in chapter_files:
        chapter = load_json(chapter_file)
        chapter_number = chapter.get("chapter_number") or int(chapter_file.stem.replace("chapter", ""))
        pages = chapter.get("pages") or []
        chapter_report = {
            "chapter_number": chapter_number,
            "title": chapter.get("title"),
            "title_en": chapter.get("title_en"),
            "file": str(chapter_file),
            "pages": [],
            "issues": [],
        }
        for page in pages:
            page_report = audit_page(chapter_number, page)
            chapter_report["pages"].append(page_report)
            chapter_report["issues"].extend(page_report["issues"])
            report["summary"]["page_count"] += 1
            report["summary"]["dialogue_count"] += page_report["dialogue_count"]
        report["chapters"].append(chapter_report)
        report["summary"]["chapter_count"] += 1

    for chapter in report["chapters"]:
        for issue in chapter["issues"]:
            if issue["severity"] == "error":
                report["summary"]["error_count"] += 1
            elif issue["severity"] == "warning":
                report["summary"]["warning_count"] += 1

    return report


def print_summary(report):
    summary = report["summary"]
    print("📣 口语练习适配审查")
    print(f"   - 章节：{summary['chapter_count']}")
    print(f"   - 页数：{summary['page_count']}")
    print(f"   - 对话：{summary['dialogue_count']}")
    print(f"   - 错误：{summary['error_count']}")
    print(f"   - 警告：{summary['warning_count']}")
    for chapter in report["chapters"]:
        if not chapter["issues"]:
            print(f"✅ 第{chapter['chapter_number']}章：通过")
            continue
        print(f"⚠️ 第{chapter['chapter_number']}章：{len(chapter['issues'])} 个问题")
        for issue in chapter["issues"][:10]:
            print(f"   - {issue['location']} [{issue['code']}]: {issue['message']}")


def parse_args():
    parser = argparse.ArgumentParser(description="Audit chapter scripts for oral-practice fit.")
    parser.add_argument("task_dir")
    parser.add_argument("--chapters", nargs="*", type=int)
    parser.add_argument("--output")
    return parser.parse_args()


def main():
    args = parse_args()
    report = audit_task(args.task_dir, args.chapters)
    output = Path(args.output) if args.output else Path(args.task_dir) / "quality" / "oral_practice_audit.json"
    save_json(output, report)
    print_summary(report)
    print(f"📄 报告已保存：{output}")
    return 1 if report["summary"]["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
