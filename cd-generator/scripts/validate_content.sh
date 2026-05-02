#!/bin/bash

# 漫剧内容质检脚本
# 用法: ./validate_content.sh <task_dir>
#
# 硬结构检查本地完成；口语自然度、翻译完整度、角色一致性、
# A2/B1/B2 难度是否跑偏等语义判断统一交给大模型。

set -e

TASK_DIR="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GUARD="/Users/zhanghua/.claude/skills/cd-generator/scripts/task_path_guard.py"

if [ -z "$TASK_DIR" ]; then
    echo "用法: $0 <task_dir>"
    exit 1
fi

TASK_DIR="$(python3 "$GUARD" "$TASK_DIR")"

export TASK_DIR
export SCRIPT_DIR
python3 << 'PYEOF'
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.environ["SCRIPT_DIR"])
from llm_json_client import OpenAICompatibleJSONClient

task_dir = os.environ["TASK_DIR"]
final_file = os.path.join(task_dir, "output", "final_output.json")
outline_file = os.path.join(task_dir, "data", "story_outline.json")
scripts_dir = os.path.join(task_dir, "scripts")
storyboards_dir = os.path.join(task_dir, "storyboards")
missions_dir = os.path.join(task_dir, "missions")
quality_dir = os.path.join(task_dir, "quality")
json_report = os.path.join(quality_dir, "content_quality_report.json")
md_report = os.path.join(quality_dir, "content_quality_report.md")

os.makedirs(quality_dir, exist_ok=True)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def normalize_name(name):
    return re.sub(r"\s+", " ", (name or "").strip()).lower()

def is_stage_direction(text):
    stripped = (text or "").strip()
    return stripped.startswith("(") and stripped.endswith(")")

def image_prompt_mentions_16x9(prompt):
    text = (prompt or "").lower()
    return any(token in text for token in ["16:9", "16x9", "landscape", "wide horizontal", "widescreen"])

def image_prompt_mentions_widescreen_zones(prompt):
    text = (prompt or "").lower()
    return (
        any(token in text for token in ["left", "center", "centre", "right", "zone", "zones", "diagonal", "split", "vertical zones"])
        and not all(token in text for token in ["top:", "middle:", "bottom:"])
    )

def image_prompt_mentions_bilingual_text(prompt):
    text = (prompt or "").lower()
    return (
        "bilingual" in text
        or "chinese + english" in text
        or "chinese and english" in text
        or re.search(r'"[^"]*[A-Za-z][^"]*/[^"]*[\u4e00-\u9fff][^"]*"', prompt or "")
    )

def image_prompt_has_english_only_conflict(prompt):
    text = (prompt or "").lower()
    conflict_patterns = [
        "english text only",
        "english only in speech bubbles",
        "all text in english only",
        "all visible text in english only",
        "visible text must be in english",
        "all readable text in english",
        "english-only",
        "no chinese",
    ]
    return any(pattern in text for pattern in conflict_patterns) or bool(
        re.search(r"speech bubble[s]?\s+'[^']+'\s+in english", prompt or "", re.IGNORECASE)
    )

def image_prompt_mentions_speech(prompt):
    text = (prompt or "").lower()
    return any(token in text for token in ["speech bubble", "speech bubbles", "caption", "comic dialogue", "dialogue bubble"])

def add_issue(issues, severity, code, location, message, suggestion=""):
    issues.append({
        "severity": severity,
        "code": code,
        "location": location,
        "message": message,
        "suggestion": suggestion,
    })

def load_story():
    if os.path.exists(final_file):
        data = load_json(final_file)
        if "story" in data:
            story = data["story"]
            if not story.get("characters") and os.path.exists(outline_file):
                outline = load_json(outline_file)
                outline_story = outline.get("story", outline)
                if outline_story.get("characters"):
                    story["characters"] = outline_story["characters"]
            return story, "output/final_output.json"

    if os.path.exists(outline_file):
        outline = load_json(outline_file)
        story = outline.get("story", outline)
    else:
        story = {}

    chapters = []
    if os.path.isdir(scripts_dir):
        for filename in sorted(os.listdir(scripts_dir)):
            if filename.startswith("chapter") and filename.endswith(".json"):
                chapters.append(load_json(os.path.join(scripts_dir, filename)))
    story["chapters"] = chapters
    return story, "data/story_outline.json + scripts/chapter*.json"

def md_escape(text):
    return str(text or "").replace("|", "\\|")

story, source = load_story()
issues = []
stats = {
    "source": source,
    "checked_at": now_iso(),
    "title": story.get("title") or story.get("title_en") or "",
    "language_level": (story.get("language_level") or story.get("level") or "").upper(),
    "chapters": 0,
    "pages": 0,
    "dialogues": 0,
    "errors": 0,
    "warnings": 0,
    "infos": 0,
}

characters = story.get("characters") or []
stage_speakers = {
    "phone", "notification", "system", "narrator", "sound", "sfx",
    "电话", "旁白", "提示音", "音效",
}

if not characters:
    add_issue(
        issues,
        "warning",
        "missing_characters",
        "story.characters",
        "故事缺少角色列表，模型可以继续审稿，但角色一致性依据会变弱。",
        "在 story_outline.json 中补充 characters，并写清 name/name_en。"
    )

client = OpenAICompatibleJSONClient()
page_summaries = []
page_audits = []
speaker_counter = Counter()
severe_semantic_codes = {
    "MISSING_ENGLISH",
    "MISSING_CHINESE",
    "WRONG_LANGUAGE",
    "SEVERE_TRANSLATION_MISMATCH",
    "UNUSABLE_DIALOGUE",
    "SEVERE_ROLE_CONTRADICTION",
    "LEVEL_SEVERELY_WRONG",
}

chapters = story.get("chapters") or []
stats["chapters"] = len(chapters)

for chapter in chapters:
    chapter_num = chapter.get("chapter_number", "?")
    pages = chapter.get("pages") or []
    for page in pages:
        page_num = page.get("page_number", "?")
        location = f"chapter{chapter_num}_page{page_num}"
        dialogues = page.get("dialogues") or []
        stats["pages"] += 1
        stats["dialogues"] += len(dialogues)

        if not (12 <= len(dialogues) <= 16):
            add_issue(
                issues,
                "error",
                "dialogue_count_out_of_range",
                location,
                f"本页对话为 {len(dialogues)} 句，不在 12-16 句范围内。",
                "补齐或压缩对话，让每页保持 12-16 句，方便口语练习节奏。"
            )

        for index, dialogue in enumerate(dialogues, start=1):
            line_location = f"{location}.dialogues[{index}]"
            text_en = (dialogue.get("text_en") or "").strip()
            text_zh = (dialogue.get("text_zh") or "").strip()
            speaker = dialogue.get("speaker") or ""
            speaker_en = dialogue.get("speaker_en") or ""
            speaker_key = normalize_name(speaker_en or speaker)
            if speaker_key:
                speaker_counter[speaker_key] += 1
            else:
                add_issue(issues, "warning", "missing_speaker", line_location, "缺少 speaker/speaker_en。", "补充说话人，方便后续角色映射。")
            if not text_en:
                add_issue(issues, "error", "missing_text_en", line_location, "缺少英文对话 text_en。", "补充英文句子。")
            if not text_zh:
                add_issue(issues, "error", "missing_text_zh", line_location, "缺少中文翻译 text_zh。", "补充对应中文翻译。")

        page_payload = {
            "location": location,
            "target_level": stats["language_level"] or "B1",
            "characters": characters,
            "scene_location": page.get("scene_location", ""),
            "dialogues": dialogues,
        }
        audit = client.request_json("audit_content_page", page_payload)
        page_audits.append({"location": location, **audit})
        page_summaries.append({
            "location": location,
            "dialogues": len(dialogues),
            "oral_fit_score": audit.get("oral_fit_score"),
            "translation_fit_score": audit.get("translation_fit_score"),
            "level_fit": audit.get("level_fit"),
            "role_consistency": audit.get("role_consistency"),
        })
        for item in audit.get("issues", []):
            severity = item.get("severity", "warning")
            if severity not in {"error", "warning", "info"}:
                severity = "warning"
            code = str(item.get("code", "llm_content_issue"))
            if severity == "error" and code not in severe_semantic_codes:
                severity = "warning"
            add_issue(
                issues,
                severity,
                code,
                location,
                item.get("message", "模型发现内容问题。"),
                item.get("suggestion", "")
            )

if os.path.isdir(storyboards_dir):
    for filename in sorted(os.listdir(storyboards_dir)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(storyboards_dir, filename)
        try:
            storyboard = load_json(path).get("storyboard", {})
        except Exception as exc:
            add_issue(issues, "error", "invalid_storyboard_json", f"storyboards/{filename}", f"分镜 JSON 无法解析：{exc}", "修复 JSON 格式。")
            continue
        if not (storyboard.get("image_prompt") or "").strip():
            add_issue(issues, "error", "missing_image_prompt", f"storyboards/{filename}", "缺少英文 image_prompt。", "补充英文图片提示词，图片生成只使用英文。")
        if not (storyboard.get("image_prompt_zh") or "").strip():
            add_issue(issues, "error", "missing_image_prompt_zh", f"storyboards/{filename}", "缺少中文 image_prompt_zh。", "补充中文图片提示词，HTML 预览直接显示该字段。")
        image_prompt = (storyboard.get("image_prompt") or "").strip()
        if image_prompt:
            if not image_prompt_mentions_16x9(image_prompt):
                add_issue(issues, "warning", "image_prompt_missing_16x9", f"storyboards/{filename}", "英文 image_prompt 未明确要求 16:9 横版构图。", "加入 16:9 landscape / widescreen composition。")
            if not image_prompt_mentions_widescreen_zones(image_prompt):
                add_issue(issues, "warning", "image_prompt_missing_widescreen_zones", f"storyboards/{filename}", "英文 image_prompt 未明确 16:9 横版分区，或仍像竖版 TOP/MIDDLE/BOTTOM 漫画面板。", "使用 left/center/right zones、非均匀横向分区或 diagonal split，并避免 TOP/MIDDLE/BOTTOM 上下分区。")
            if not image_prompt_mentions_bilingual_text(image_prompt):
                add_issue(issues, "warning", "image_prompt_missing_bilingual_text", f"storyboards/{filename}", "英文 image_prompt 未明确对话气泡/字幕需要中英双语。", "加入 bilingual Chinese + English speech bubbles/captions，例如 \"I must go. / 我必须去。\"。")
            if image_prompt_has_english_only_conflict(image_prompt):
                add_issue(issues, "error", "image_prompt_english_only_conflict", f"storyboards/{filename}", "英文 image_prompt 仍包含 English only / no Chinese 等旧规则，会和中英双语气泡要求冲突。", "运行 ensure_bilingual_bubbles.py 清理旧规则，保留 bilingual Chinese + English visible dialogue/caption text。")
            if not image_prompt_mentions_speech(image_prompt):
                add_issue(issues, "warning", "image_prompt_missing_speech_bubbles", f"storyboards/{filename}", "英文 image_prompt 未提到漫画式对话气泡或短 caption。", "根据页面对白加入 1-3 个短中英双语 speech bubbles/captions，避免无对白的空背景。")

if os.path.isdir(missions_dir):
    for filename in sorted(os.listdir(missions_dir)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(missions_dir, filename)
        try:
            mission = load_json(path)
        except Exception as exc:
            add_issue(issues, "error", "invalid_mission_json", f"missions/{filename}", f"mission JSON 无法解析：{exc}", "修复 JSON 格式。")
            continue

        mission_location = f"missions/{filename}"
        user_role = mission.get("user_role") or ""
        ai_role = mission.get("ai_role") or ""
        beats = mission.get("must_hit_beats") or []
        if normalize_name(user_role) in stage_speakers or normalize_name(ai_role) in stage_speakers:
            add_issue(issues, "error", "mission_stage_role", mission_location, f"mission 角色不能是舞台/系统说话人：user_role={user_role}, ai_role={ai_role}", "重新生成 mission。")
        if user_role and ai_role and normalize_name(user_role) == normalize_name(ai_role):
            add_issue(issues, "error", "mission_same_roles", mission_location, f"user_role 和 ai_role 指向同一角色：{user_role}", "为 AI 选择页面中的另一个真实角色。")
        if not isinstance(beats, list) or not beats:
            add_issue(issues, "error", "mission_missing_beats", mission_location, "缺少 must_hit_beats。", "重新生成 mission。")
        for index, beat in enumerate(beats, start=1):
            beat_location = f"{mission_location}.must_hit_beats[{index}]"
            if not isinstance(beat, dict):
                add_issue(issues, "error", "mission_legacy_string_beat", beat_location, "must_hit_beats 应为结构化对象。", "使用新版 generate_conversation_missions.py 重新生成。")
                continue
            if not beat.get("label") or not beat.get("intent") or not beat.get("acceptance_criteria"):
                add_issue(issues, "error", "mission_incomplete_semantic_beat", beat_location, "beat 缺少 label、intent 或 acceptance_criteria。", "重新生成 mission，让模型补齐语义验收标准。")
else:
    add_issue(issues, "info", "missions_not_generated", "missions/", "未发现 conversation missions；如果要做 Story-Guided Free Talk，需要先生成 missions。", "运行 scripts/generate_conversation_missions.py <task_dir>。")

severity_order = {"error": 0, "warning": 1, "info": 2}
issues.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["location"], item["code"]))
stats["errors"] = sum(1 for item in issues if item["severity"] == "error")
stats["warnings"] = sum(1 for item in issues if item["severity"] == "warning")
stats["infos"] = sum(1 for item in issues if item["severity"] == "info")

report = {
    "summary": stats,
    "characters": {
        "declared": characters,
        "speakers_seen": speaker_counter,
    },
    "page_summaries": page_summaries,
    "page_audits": page_audits,
    "issues": issues,
}

with open(json_report, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
    f.write("\n")

status = "通过" if stats["errors"] == 0 else "未通过"
with open(md_report, "w", encoding="utf-8") as f:
    f.write("# 内容质检报告\n\n")
    f.write(f"- 状态：{status}\n")
    f.write(f"- 检查时间：{stats['checked_at']}\n")
    f.write(f"- 数据来源：`{source}`\n")
    f.write(f"- 故事：{stats['title']}\n")
    f.write(f"- 目标难度：{stats['language_level'] or '未填写'}\n")
    f.write(f"- 审稿方式：大模型语义审稿 + 本地结构检查\n")
    f.write(f"- 章节/页/对话：{stats['chapters']} / {stats['pages']} / {stats['dialogues']}\n")
    f.write(f"- 问题统计：error {stats['errors']}，warning {stats['warnings']}，info {stats['infos']}\n\n")

    f.write("## 页面指标\n\n")
    f.write("| 页面 | 对话数 | 口语分 | 翻译分 | 难度 | 角色一致性 |\n")
    f.write("| --- | ---: | ---: | ---: | --- | --- |\n")
    for page in page_summaries:
        oral = page.get("oral_fit_score")
        trans = page.get("translation_fit_score")
        f.write(
            f"| {page['location']} | {page['dialogues']} | "
            f"{'' if oral is None else oral} | {'' if trans is None else trans} | "
            f"{page.get('level_fit', '')} | {page.get('role_consistency', '')} |\n"
        )
    f.write("\n")

    f.write("## 问题列表\n\n")
    if not issues:
        f.write("未发现问题。\n")
    else:
        f.write("| 级别 | 代码 | 位置 | 问题 | 建议 |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for item in issues:
            f.write(
                f"| {item['severity']} | `{item['code']}` | `{md_escape(item['location'])}` | "
                f"{md_escape(item['message'])} | {md_escape(item.get('suggestion', ''))} |\n"
            )

progress_file = os.path.join(task_dir, "data", "progress.json")
if os.path.exists(progress_file):
    try:
        progress = load_json(progress_file)
        progress.setdefault("status", {})
        progress["status"]["content_quality"] = "completed" if stats["errors"] == 0 else "failed"
        progress["content_quality_summary"] = {
            "errors": stats["errors"],
            "warnings": stats["warnings"],
            "infos": stats["infos"],
            "report": "quality/content_quality_report.md",
            "checked_at": stats["checked_at"],
            "auditor": "llm_semantic_v1",
        }
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as exc:
        print(f"质检完成，但 progress.json 更新失败：{exc}")

print(f"内容质检完成：error {stats['errors']}，warning {stats['warnings']}，info {stats['infos']}")
print(f"Markdown: {md_report}")
print(f"JSON: {json_report}")

if stats["errors"] > 0:
    sys.exit(1)
PYEOF
