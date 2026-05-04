#!/usr/bin/env python3
"""
Generate per-page storyboard JSON with shanyin-direct style constraints.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from llm_json_client import OpenAICompatibleJSONClient


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


def update_progress(task_dir, status, summary=None, error=None):
    progress_path = Path(task_dir) / "data" / "progress.json"
    progress = load_json(progress_path, default={})
    progress.setdefault("status", {})
    progress["status"]["storyboards"] = status
    progress["updated_at"] = now_iso()
    if summary:
        progress["storyboards_summary"] = summary
    if error:
        progress["storyboards_error"] = error
    save_json(progress_path, progress)


def story_from_outline(outline):
    return outline.get("story", outline)


def find_page(chapter, page_number):
    for page in chapter.get("pages", []):
        if int(page.get("page_number", 0)) == page_number:
            return page
    raise ValueError(f"找不到第 {page_number} 页")


def visible_dialogues(page, limit=8):
    dialogues = []
    for line in page.get("dialogues", []):
        dialogues.append({
            "speaker": line.get("speaker"),
            "speaker_en": line.get("speaker_en"),
            "text_zh": line.get("text_zh"),
            "text_en": line.get("text_en"),
            "emotion": line.get("emotion"),
        })
    return dialogues[:limit]


def dialogue_text_pair(line):
    en = str(line.get("text_en") or "").strip()
    zh = str(line.get("text_zh") or "").strip()
    return en, zh


def is_readable_bubble(en, zh):
    return bool(en and zh and len(en.split()) <= 12 and len(zh) <= 20)


def bubble_story_score(line, index, page):
    en, zh = dialogue_text_pair(line)
    lower = en.lower()
    score = 0
    if index <= 1:
        score += 40
    if "?" in en or "？" in zh:
        score += 35
    task_markers = [
        "brief", "task", "need", "first", "start", "show", "clarify",
        "confirm", "help", "deadline", "change", "revise", "review",
        "plan", "next", "could you", "can you", "let's", "we should",
    ]
    if any(marker in lower for marker in task_markers):
        score += 32
    emotion_markers = [
        "nervous", "worried", "sorry", "stuck", "confused", "ready",
        "thank", "welcome", "understand", "i see", "i'm not sure",
    ]
    emotion = str(line.get("emotion") or "").lower()
    if any(marker in lower or marker in emotion for marker in emotion_markers):
        score += 22

    speaking_goal = str(page.get("speaking_goal") or "").lower()
    goal_words = {
        word
        for word in re.findall(r"[a-z]{4,}", speaking_goal)
        if word not in {"with", "from", "that", "this", "your", "about"}
    }
    if goal_words:
        overlap = sum(1 for word in goal_words if word in lower)
        score += min(overlap * 12, 36)
    if not is_readable_bubble(en, zh):
        score -= 100
    return score


def select_key_bubbles_for_image(page, max_bubbles=3):
    """
    从页面中选择最关键的双语对话，用于在图片气泡中显示。
    选择标准：
    1. 场景开场白（帮助理解场景）
    2. 关键信息或转折（推进剧情）
    3. 情感反应或心理活动（引导用户共情）

    返回格式：[(en_text, zh_text, speaker, emotion), ...]
    """
    dialogues = page.get("dialogues", [])
    if not dialogues:
        return []

    scored = []
    for index, line in enumerate(dialogues, start=1):
        en, zh = dialogue_text_pair(line)
        if not is_readable_bubble(en, zh):
            continue
        scored.append((bubble_story_score(line, index, page), index, line))

    if not scored:
        return []

    selected = []

    def add_line(line):
        en, zh = dialogue_text_pair(line)
        normalized = re.sub(r"\W+", "", en.lower())
        if any(re.sub(r"\W+", "", item[0].lower()) == normalized for item in selected):
            return
        speaker = line.get("speaker_en") or line.get("speaker") or ""
        emotion = line.get("emotion") or ""
        selected.append((en, zh, speaker, emotion))

    # 先放一个能定位场景/关系的开场短句，再放真正推动任务或冲突的句子。
    for _, _, line in scored[:2]:
        if len(selected) < 2:
            add_line(line)

    for _, _, line in sorted(scored, key=lambda item: (-item[0], item[1])):
        if len(selected) >= max_bubbles:
            break
        add_line(line)

    return selected[:max_bubbles]


def format_bubbles_for_prompt(bubbles):
    """
    将双语气泡列表格式化为图片提示词中的明确指令。

    例如：
    Speech bubbles with bilingual text:
    - LEFT zone: "Good morning! / 早上好！" (Lin Xiao)
    - CENTER zone: "Welcome to the team! / 欢迎加入团队！" (Sarah)
    """
    if not bubbles:
        return ""

    zones = ["LEFT zone", "CENTER zone", "RIGHT zone"]
    lines = ["Include 1-3 bilingual Chinese + English speech bubbles:"]

    for i, (en, zh, speaker, emotion) in enumerate(bubbles[:3]):
        zone = zones[i] if i < len(zones) else f"zone {i+1}"
        lines.append(f'  - {zone}: "{en} / {zh}" ({speaker})')

    return "\n".join(lines)


def build_payload(story, chapter, page, art_style):
    key_bubbles = select_key_bubbles_for_image(page, max_bubbles=3)
    bubble_instruction = format_bubbles_for_prompt(key_bubbles)

    return {
        "story": {
            "title": story.get("title"),
            "title_en": story.get("title_en"),
            "genre": story.get("genre"),
            "language_level": story.get("language_level"),
            "characters": story.get("characters", []),
        },
        "chapter": {
            "chapter_number": chapter.get("chapter_number"),
            "title": chapter.get("title"),
            "title_en": chapter.get("title_en"),
            "summary": chapter.get("summary"),
        },
        "page": {
            "page_number": page.get("page_number"),
            "page_title": page.get("page_title"),
            "scene_location": page.get("scene_location"),
            "time": page.get("time"),
            "weather": page.get("weather"),
            "emotional_arc": page.get("emotional_arc"),
            "speaking_goal": page.get("speaking_goal"),
            "dialogues": visible_dialogues(page),
            "key_bubbles": key_bubbles,
            "bubble_instruction": bubble_instruction,
        },
        "art_style": art_style,
        "scene2talk_constraints": {
            "aspect_ratio": "16:9 landscape widescreen",
            "composition": "left/center/right zones or diagonal split",
            "visible_text": "bilingual Chinese + English speech bubbles/captions for dialogue practice",
            "bubble_budget": "max 2 bilingual bubbles/captions per visible scene, max 6 in the whole image, default 1-3; only multi-scene, ensemble, or dream-montage pages should approach 6",
            "bubble_format": 'English above Chinese, e.g. "Good morning! / 早上好！"',
            "bubble_instruction": bubble_instruction,
            "ui_safety": "avoid the top 12% of the image for speech bubbles, faces, and key readable text; keep a 6% left/right edge margin for bubbles, faces, and important props",
        },
    }


def validate_storyboard(data, chapter_number, page_number):
    if int(data.get("chapter", 0)) != chapter_number:
        raise ValueError("chapter 字段不匹配")
    if int(data.get("page", 0)) != page_number:
        raise ValueError("page 字段不匹配")
    storyboard = data.get("storyboard")
    if not isinstance(storyboard, dict):
        raise ValueError("缺少 storyboard object")
    for key in ["composition", "left_zone", "center_zone", "right_zone", "image_prompt", "image_prompt_zh"]:
        if not str(storyboard.get(key) or "").strip():
            raise ValueError(f"storyboard.{key} 为空")

    prompt = storyboard.get("image_prompt", "")
    lower = prompt.lower()
    if not any(token in lower for token in ["16:9", "16x9", "widescreen", "landscape"]):
        raise ValueError("image_prompt 未明确 16:9/landscape/widescreen")
    if not (
        all(token in lower for token in ["left", "center", "right"])
        or "diagonal" in lower
    ):
        raise ValueError("image_prompt 未明确 left/center/right 或 diagonal 构图")
    if not has_bilingual_text_rule(prompt):
        raise ValueError("image_prompt 未明确中英双语气泡/字幕")


def normalize_storyboard_prompt(data, page=None):
    storyboard = data.setdefault("storyboard", {})
    prompt = remove_english_only_conflicts(str(storyboard.get("image_prompt") or "").strip())
    lower = prompt.lower()
    additions = []
    if not any(token in lower for token in ["16:9", "16x9", "widescreen", "landscape"]):
        additions.append("16:9 widescreen landscape composition")
    if not (
        all(token in lower for token in ["left", "center", "right"])
        or "diagonal" in lower
    ):
        additions.append("clear LEFT/CENTER/RIGHT horizontal zones")

    # 添加具体的气泡内容到提示词中
    if page:
        key_bubbles = select_key_bubbles_for_image(page, max_bubbles=3)
        if key_bubbles:
            bubble_lines = []
            zones = ["LEFT zone", "CENTER zone", "RIGHT zone"]
            for i, (en, zh, speaker, emotion) in enumerate(key_bubbles[:3]):
                zone = zones[i] if i < len(zones) else f"zone {i+1}"
                # 限制长度，确保简洁
                en_short = en[:60] if len(en) > 60 else en
                zh_short = zh[:40] if len(zh) > 40 else zh
                bubble_lines.append(f'{zone}: "{en_short} / {zh_short}"')

            bubble_instruction = " | ".join(bubble_lines)
            # 确保气泡内容被明确写入提示词
            if not has_specific_bubble_text(prompt, key_bubbles):
                additions.append(f'Include 1-3 bilingual Chinese + English speech bubbles/captions with EXACT visible text to guide the viewer through the scene background, character action, and task progress: {bubble_instruction}')

    if not has_bilingual_text_rule(prompt):
        additions.append('visible dialogue text should use bilingual Chinese + English speech bubbles, for example "I must go. / 我必须去。"')
    if not has_ui_safety_rule(prompt):
        additions.append("UI safety margins: avoid the top 12% of the image for speech bubbles, faces, and key readable text; keep a 6% left/right edge margin for bubbles, faces, and important props")
    if additions:
        prompt = f"{prompt}. " + ". ".join(additions) + "."
        storyboard["image_prompt"] = prompt
    return data


def has_specific_bubble_text(prompt, bubbles):
    """检查提示词是否已经包含具体的气泡文本"""
    if not bubbles:
        return True  # 没有气泡需要检查
    for en, zh, speaker, emotion in bubbles[:2]:
        # 检查英文或中文是否在提示词中
        en_words = en.split()[:4]  # 前4个单词
        zh_chars = zh[:6]  # 前6个字符
        if en_words and " ".join(en_words) in prompt:
            return True
        if zh_chars and zh_chars in prompt:
            return True
    return False


def remove_english_only_conflicts(prompt):
    replacements = [
        (r"\bEnglish text only in speech bubbles\.?", "Use bilingual Chinese + English text in speech bubbles."),
        (r"\ball visible text, signs, captions, and speech bubbles must be English only\.?", "Visible dialogue/caption text should use bilingual Chinese + English; keep any non-dialogue signs minimal and readable."),
        (r"\ball text in English only\b", "all dialogue/caption text in bilingual Chinese + English"),
        (r"\bAll text in English only\b", "All dialogue/caption text in bilingual Chinese + English"),
        (r"\bAll visible text in English only\b", "All visible dialogue/caption text in bilingual Chinese + English"),
        (r"\ball visible text in English only\b", "all visible dialogue/caption text in bilingual Chinese + English"),
        (r"\bvisible text must be in English\b", "visible dialogue/caption text should use bilingual Chinese + English"),
        (r"\ball readable text in English\b", "all readable dialogue/caption text in bilingual Chinese + English"),
        (r"\bshort English speech bubbles\b", "short bilingual Chinese + English speech bubbles"),
        (r"\bone short English speech bubble\b", "one short bilingual Chinese + English speech bubble"),
        (r"\bThree English speech bubbles\b", "Three short bilingual Chinese + English speech bubbles"),
        (r"\bEnglish speech bubbles\b", "bilingual Chinese + English speech bubbles"),
        (r"\bEnglish-only\b", "bilingual Chinese + English"),
        (r"\bno Chinese, no Japanese, no Korean, no pseudo text, no random glyphs, no unreadable text\.?", "no Japanese, no Korean, no pseudo text, no random glyphs, no unreadable text; dialogue/caption text should be bilingual Chinese + English."),
    ]
    sanitized = prompt
    for pattern, replacement in replacements:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(
        r"speech bubble\s+'([^']+)'\s+in English",
        "bilingual Chinese + English speech bubble",
        sanitized,
        flags=re.IGNORECASE,
    )
    previous = None
    while previous != sanitized:
        previous = sanitized
        sanitized = re.sub(
            r"bilingual Chinese \+ (?:bilingual Chinese \+ )+English",
            "bilingual Chinese + English",
            sanitized,
            flags=re.IGNORECASE,
        )
    sanitized = re.sub(r"\s{2,}", " ", sanitized).strip()
    return sanitized


def has_bilingual_text_rule(prompt):
    lower = prompt.lower()
    return (
        "bilingual" in lower
        or "chinese + english" in lower
        or "chinese and english" in lower
        or re.search(r'"[^"]*[A-Za-z][^"]*/[^"]*[\u4e00-\u9fff][^"]*"', prompt)
    )


def has_ui_safety_rule(prompt):
    lower = prompt.lower()
    has_top = (
        "top 12%" in lower
        or "top twelve percent" in lower
        or "顶部 12%" in prompt
        or "顶部12%" in prompt
    )
    has_side = (
        "6% left/right" in lower
        or "left/right edge margin" in lower
        or "left and right 6%" in lower
        or "左右 6%" in prompt
        or "左右6%" in prompt
    )
    return has_top and has_side


def parse_args():
    parser = argparse.ArgumentParser(description="Generate shanyin-direct storyboard JSON for cd-generator pages.")
    parser.add_argument("task_dir")
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--pages", nargs="*", type=int)
    parser.add_argument("--art-style", default="modern manga style")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    task_dir = Path(args.task_dir)
    outline = load_json(task_dir / "data" / "story_outline.json")
    story = story_from_outline(outline)
    chapter_path = task_dir / "scripts" / f"chapter{args.chapter}.json"
    chapter = load_json(chapter_path)
    pages = args.pages or [int(page.get("page_number")) for page in chapter.get("pages", [])]

    print("⏳ shanyin-direct：已收到 cd-generator 脚本调用，正在进入 storyboard 模式", flush=True)
    print(f"   - 章节：{args.chapter}", flush=True)
    print(f"   - 页数：{len(pages)}", flush=True)

    client = OpenAICompatibleJSONClient()
    completed = 0
    try:
        update_progress(task_dir, "running")
        for page_number in pages:
            output_path = task_dir / "storyboards" / f"chapter{args.chapter}_page{page_number}.json"
            if output_path.exists() and not args.force:
                print(f"✅ shanyin-direct：已存在，跳过 chapter{args.chapter}_page{page_number}", flush=True)
                completed += 1
                continue
            page = find_page(chapter, page_number)
            print(f"⏳ shanyin-direct：正在生成 chapter{args.chapter}_page{page_number} 分镜", flush=True)
            payload = build_payload(story, chapter, page, args.art_style)
            storyboard = client.request_json("generate_storyboard_page", payload)
            storyboard = normalize_storyboard_prompt(storyboard, page)
            validate_storyboard(storyboard, args.chapter, page_number)
            save_json(output_path, storyboard)
            completed += 1
            update_progress(
                task_dir,
                "running",
                summary={"completed": completed, "total": len(pages), "chapter": args.chapter},
            )
            print(f"✅ shanyin-direct：chapter{args.chapter}_page{page_number} 已完成", flush=True)
        update_progress(task_dir, "completed", summary={"completed": completed, "total": len(pages), "chapter": args.chapter})
        print("✅ shanyin-direct：分镜生成完成", flush=True)
        return 0
    except Exception as exc:
        update_progress(task_dir, "failed", error=str(exc))
        print(f"❌ shanyin-direct：分镜生成失败：{exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
