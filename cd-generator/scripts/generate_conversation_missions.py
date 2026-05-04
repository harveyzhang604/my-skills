#!/usr/bin/env python3
"""
为每页漫画生成 Conversation Mission 元数据。

语义抽取全部交给大模型：角色、beats、目标表达都由模型根据页面剧本判断。
本脚本只做 JSON 读写、输出规范化和基础结构校验。
"""

import json
import re
import sys
from pathlib import Path

try:
    from integrate_final_output import integrate
    from llm_json_client import OpenAICompatibleJSONClient
    from task_path_guard import require_task_dir
except ImportError:
    from .integrate_final_output import integrate
    from .llm_json_client import OpenAICompatibleJSONClient
    from .task_path_guard import require_task_dir


STAGE_SPEAKERS = {
    "phone", "notification", "system", "narrator", "sound", "sfx",
    "电话", "旁白", "提示音", "音效",
}

ALLOWED_INTENTS = {
    "greet_introduce",
    "react_to_scene",
    "ask_question",
    "express_feeling",
    "explain_reason",
    "explain_work",
    "offer_help",
    "accept_feedback",
    "request_clarification",
    "negotiate_time",
    "show_gratitude",
    "show_willingness",
    "summarize_lesson",
    "present_result",
    "other_goal",
}

MISSION_CANDIDATE_KEYS = ("conversation_mission", "mission")


def normalize_name(value):
    return " ".join(str(value or "").strip().lower().split())


def is_stage_speaker(name):
    return normalize_name(name) in STAGE_SPEAKERS


def is_stage_direction(text):
    stripped = str(text or "").strip()
    return stripped.startswith("(") and stripped.endswith(")")


def unique_preserve_order(values):
    seen = set()
    result = []
    for value in values or []:
        text = str(value or "").strip()
        key = normalize_name(text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def slugify_intent(value, fallback):
    text = str(value or fallback or "semantic_goal").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    if text in ALLOWED_INTENTS:
        return text
    return "other_goal"


def visible_dialogues(dialogues):
    result = []
    for index, dialogue in enumerate(dialogues or [], start=1):
        speaker = dialogue.get("speaker_en") or dialogue.get("speaker", "")
        text_en = dialogue.get("text_en", "")
        if is_stage_speaker(speaker) or is_stage_direction(text_en):
            continue
        result.append({
            "index": index,
            "speaker": dialogue.get("speaker", ""),
            "speaker_en": dialogue.get("speaker_en", ""),
            "text_en": text_en,
            "text_zh": dialogue.get("text_zh", ""),
            "emotion": dialogue.get("emotion", ""),
        })
    return result


def generate_mission_for_page(
    page_data,
    chapter_num,
    page_num,
    story_characters=None,
    language_level=None,
    llm_client=None,
):
    dialogues = page_data.get("dialogues", [])
    scene_location = page_data.get("scene_location", "")
    embedded_mission = embedded_conversation_mission(page_data)
    if embedded_mission:
        return normalize_mission(
            embedded_mission,
            chapter_num=chapter_num,
            page_num=page_num,
            scene_location=scene_location,
            language_level=language_level or page_data.get("language_level") or page_data.get("difficulty_level", "B1"),
            vocabulary_focus=page_data.get("vocabulary_focus", []),
            estimated_turns=len(dialogues),
        )

    client = llm_client or OpenAICompatibleJSONClient()

    payload = {
        "chapter": chapter_num,
        "page": page_num,
        "scene": scene_location,
        "language_level": language_level or page_data.get("language_level") or page_data.get("difficulty_level", "B1"),
        "story_characters": story_characters or [],
        "vocabulary_focus": page_data.get("vocabulary_focus", []),
        "dialogues": visible_dialogues(dialogues),
    }
    model_mission = client.request_json("generate_conversation_mission", payload)
    if not isinstance(model_mission, dict):
        raise RuntimeError("模型返回的 mission 不是 JSON object。")

    return normalize_mission(
        model_mission,
        chapter_num=chapter_num,
        page_num=page_num,
        scene_location=scene_location,
        language_level=payload["language_level"],
        vocabulary_focus=page_data.get("vocabulary_focus", []),
        estimated_turns=len(dialogues),
    )


def normalize_mission(
    model_mission,
    chapter_num,
    page_num,
    scene_location,
    language_level,
    vocabulary_focus,
    estimated_turns,
):
    characters = [
        name for name in unique_preserve_order(model_mission.get("characters", []))
        if not is_stage_speaker(name)
    ]
    user_role = str(model_mission.get("user_role") or (characters[0] if characters else "Learner")).strip()
    ai_role = str(model_mission.get("ai_role") or "AI Partner").strip()
    if is_stage_speaker(user_role):
        user_role = characters[0] if characters else "Learner"
    if is_stage_speaker(ai_role) or normalize_name(ai_role) == normalize_name(user_role):
        ai_role = next(
            (name for name in characters if normalize_name(name) != normalize_name(user_role)),
            "AI Partner",
        )

    beats = normalize_beats(model_mission.get("must_hit_beats", []))
    if not beats:
        raise RuntimeError("模型没有生成 must_hit_beats，无法创建 Story-Guided mission。")

    return {
        "page": page_num,
        "chapter": chapter_num,
        "scene": scene_location,
        "characters": characters,
        "user_role": user_role,
        "ai_role": ai_role,
        "mission_summary": str(model_mission.get("mission_summary") or f"在{scene_location}中完成自由口语练习。"),
        "must_hit_beats": beats,
        "target_phrases": unique_preserve_order(model_mission.get("target_phrases", []))[:6],
        "vocabulary_focus": vocabulary_focus,
        "estimated_turns": estimated_turns,
        "language_level": language_level,
        "director_mode": "llm_semantic_v1",
        "success_rule": "Complete all must_hit_beats semantically in order; exact wording is not required.",
        "coach_note": str(model_mission.get("coach_note") or ""),
    }


def embedded_conversation_mission(page_data):
    for key in MISSION_CANDIDATE_KEYS:
        candidate = page_data.get(key)
        if isinstance(candidate, dict) and candidate.get("must_hit_beats"):
            return candidate
    return None


def normalize_beats(beats):
    result = []
    for index, beat in enumerate(beats or [], start=1):
        if not isinstance(beat, dict):
            continue
        intent = slugify_intent(beat.get("intent"), beat.get("label"))
        label = str(beat.get("label") or f"Story beat {index}").strip()
        raw_intent = str(beat.get("intent") or "").strip()
        result.append({
            "id": str(beat.get("id") or f"beat_{index}_{intent}").strip(),
            "label": label,
            "label_zh": str(beat.get("label_zh") or "").strip(),
            "intent": intent,
            "model_intent_raw": raw_intent,
            "acceptance_criteria": str(beat.get("acceptance_criteria") or label).strip(),
            "example_phrases": unique_preserve_order(beat.get("example_phrases", []))[:3],
            "source_dialogue_indices": [
                int(value) for value in beat.get("source_dialogue_indices", [])
                if str(value).isdigit()
            ],
        })
    result.sort(key=beat_sort_key)
    deduped = []
    by_intent = {}
    for beat in result:
        existing = by_intent.get(beat["intent"])
        if not existing:
            by_intent[beat["intent"]] = beat
            deduped.append(beat)
            continue
        existing["example_phrases"] = unique_preserve_order(
            existing.get("example_phrases", []) + beat.get("example_phrases", [])
        )[:3]
        existing["source_dialogue_indices"] = sorted(set(
            existing.get("source_dialogue_indices", []) + beat.get("source_dialogue_indices", [])
        ))
        if beat.get("acceptance_criteria") and beat["acceptance_criteria"] not in existing["acceptance_criteria"]:
            existing["acceptance_criteria"] = (
                existing["acceptance_criteria"].rstrip(".")
                + "; "
                + beat["acceptance_criteria"].rstrip(".")
                + "."
            )

    deduped = prioritize_opening_greeting(deduped)
    for index, beat in enumerate(deduped[:5], start=1):
        beat["id"] = f"beat_{index}_{beat['intent']}"
    return deduped[:5]


def beat_sort_key(beat):
    indices = beat.get("source_dialogue_indices") or []
    if indices:
        return min(indices)
    return 999


def prioritize_opening_greeting(beats):
    greeting_index = next(
        (index for index, beat in enumerate(beats) if beat.get("intent") == "greet_introduce"),
        None,
    )
    if greeting_index is None:
        return beats
    greeting = beats[greeting_index]
    return [greeting] + beats[:greeting_index] + beats[greeting_index + 1:]


def process_task_directory(task_dir, llm_client=None):
    scripts_dir = Path(task_dir) / "scripts"
    missions_dir = Path(task_dir) / "missions"
    missions_dir.mkdir(exist_ok=True)
    story_characters = []
    language_level = None
    client = llm_client or OpenAICompatibleJSONClient()

    outline_file = Path(task_dir) / "data" / "story_outline.json"
    if outline_file.exists():
        with open(outline_file, 'r', encoding='utf-8') as f:
            outline = json.load(f)
        story = outline.get("story", outline)
        story_characters = story.get("characters", [])
        language_level = story.get("language_level")

    if not scripts_dir.exists():
        print(f"错误：找不到 scripts 目录: {scripts_dir}")
        return

    mission_count = 0

    for script_file in sorted(scripts_dir.glob("chapter*.json")):
        with open(script_file, 'r', encoding='utf-8') as f:
            chapter_data = json.load(f)

        chapter_num = chapter_data.get("chapter_number")
        pages = chapter_data.get("pages", [])

        for page_data in pages:
            page_num = page_data.get("page_number")
            mission = generate_mission_for_page(
                page_data,
                chapter_num,
                page_num,
                story_characters=story_characters,
                language_level=language_level,
                llm_client=client,
            )

            mission_file = missions_dir / f"chapter{chapter_num}_page{page_num}.json"
            with open(mission_file, 'w', encoding='utf-8') as f:
                json.dump(mission, f, indent=2, ensure_ascii=False)
                f.write('\n')

            page_data["conversation_mission"] = mission
            mission_count += 1
            print(f"✅ 生成 mission: chapter{chapter_num}_page{page_num}")

        with open(script_file, 'w', encoding='utf-8') as f:
            json.dump(chapter_data, f, indent=2, ensure_ascii=False)
            f.write('\n')

    progress_file = Path(task_dir) / "data" / "progress.json"
    if progress_file.exists():
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress = json.load(f)
        progress.setdefault("status", {})
        progress["status"]["conversation_missions"] = "completed"
        progress["conversation_missions_summary"] = {
            "mission_count": mission_count,
            "directory": "missions",
            "director_mode": "llm_semantic_v1",
        }
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
            f.write('\n')

    integrate(task_dir)
    print(f"\n✅ 所有 missions 已生成到: {missions_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python generate_conversation_missions.py <task_dir>")
        sys.exit(1)

    process_task_directory(require_task_dir(sys.argv[1]))
