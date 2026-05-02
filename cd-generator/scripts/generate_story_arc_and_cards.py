#!/usr/bin/env python3
"""
Generate story arc, full visual character cards, and scene tone prompts.

This stage runs after selecting a story outline and before detailed chapter
scripts. The character cards are visual-continuity assets for later image
prompts, so they must cover all important characters/entities from the full
outline, not only the protagonist list.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from llm_json_client import OpenAICompatibleJSONClient
from task_path_guard import require_task_dir


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def story_from_outline(outline):
    return outline.get("story", outline)


def safe_filename(value):
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", value.strip(), flags=re.UNICODE)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "visual_asset"


def generate_story_arc(task_dir):
    outline = load_json(task_dir / "data" / "story_outline.json")
    story = story_from_outline(outline)

    payload = {
        "story": {
            "title": story.get("title"),
            "title_en": story.get("title_en"),
            "genre": story.get("genre"),
            "language_level": story.get("language_level"),
            "total_chapters": story.get("total_chapters"),
            "summary": story.get("summary"),
            "chapter_outlines": story.get("chapter_outlines", []),
        }
    }
    prompt = {
        "instruction": "Generate story_arc for each chapter with chapter, title, title_en, core_events, key_turning_point, emotional_tone.",
        **payload,
    }
    client = OpenAICompatibleJSONClient()
    result = client.request_json("generate_story_arc", prompt)
    if not isinstance(result.get("story_arc"), list):
        raise RuntimeError("模型未返回 story_arc 数组")
    return result


def generate_visual_assets(task_dir):
    outline = load_json(task_dir / "data" / "story_outline.json")
    story = story_from_outline(outline)
    extracted_assets = extract_visual_assets_from_outline(story)

    payload = {
        "story": {
            "title": story.get("title"),
            "title_en": story.get("title_en"),
            "genre": story.get("genre"),
            "language_level": story.get("language_level"),
            "summary": story.get("summary"),
            "characters": story.get("characters", []),
            "chapter_outlines": story.get("chapter_outlines", []),
        },
        "deterministic_extracted_assets": extracted_assets,
        "coverage_requirements": [
            "Include all explicit characters in story.characters.",
            "Extract named characters from chapter summaries and page_beats.",
            "Include opposing leaders and recurring groups/entities that influence visual continuity.",
            "Include exactly two scene tone cards for world style reference images.",
        ],
    }
    try:
        client = OpenAICompatibleJSONClient(timeout=180)
        result = client.request_json("generate_story_visual_assets", payload)
    except Exception as exc:
        print(f"   ⚠️  模型生成视觉资产失败，使用本地兜底生成：{exc}", flush=True)
        result = build_fallback_visual_assets(story, extracted_assets)
    validate_visual_assets(result, story)
    result["generated_at"] = now_iso()
    result["source"] = "story_outline_full_scan"
    return result


def extract_visual_assets_from_outline(story):
    assets = []
    seen = set()

    def add(name, name_en, card_type, importance, faction, role, visual_description_zh="", source=""):
        key = (name or name_en).strip()
        if not key or key in seen:
            return
        seen.add(key)
        assets.append({
            "name": name,
            "name_en": name_en,
            "card_type": card_type,
            "importance": importance,
            "faction": faction,
            "role": role,
            "visual_description_zh": visual_description_zh,
            "source": source,
        })

    for char in story.get("characters", []):
        add(
            char.get("name", ""),
            char.get("name_en", ""),
            "character",
            "primary",
            "heroes",
            char.get("role", ""),
            char.get("visual_description", ""),
            "story.characters",
        )

    full_text = json.dumps({
        "summary": story.get("summary"),
        "chapter_outlines": story.get("chapter_outlines", []),
    }, ensure_ascii=False)
    patterns = [
        ("狼王格雷", "Wolf King Grey", "character", "secondary", "opposition", "流亡族群领袖/前世牺牲者", "chapter_outlines"),
        ("格雷", "Grey", "character", "secondary", "opposition", "流亡族群领袖", "chapter_outlines"),
        ("卡尔", "Karl", "past_identity", "secondary", "opposition", "格雷的前世身份/被牺牲的队友", "chapter_outlines"),
        ("小金的弟弟", "Xiao Jin's Brother", "character", "secondary", "support", "小金寻找的失踪弟弟/森林之心中的意识", "story_outline"),
        ("流亡族群", "Exiled Clan", "group", "visual_anchor", "opposition", "北方森林幸存族群", "story_outline"),
        ("森林之心", "Heart of the Forest", "entity", "visual_anchor", "neutral_or_testers", "晨曦文明集体意识/AI考验者", "story_outline"),
        ("晨曦文明", "Dawn Civilization", "entity", "visual_anchor", "neutral_or_testers", "古代数字文明与遗迹风格", "story_outline"),
        ("记忆森林", "Memory Forest", "entity", "visual_anchor", "neutral_or_testers", "储存记忆的水晶森林空间", "story_outline"),
        ("晨曦之城", "Dawn City", "entity", "visual_anchor", "neutral_or_testers", "古代文明数字遗迹城市", "chapter_outlines"),
        ("古代AI", "Ancient AI", "entity", "visual_anchor", "neutral_or_testers", "森林之心的测试意识", "story_outline"),
    ]
    for token, name_en, card_type, importance, faction, role, source in patterns:
        if token in full_text:
            add(token, name_en, card_type, importance, faction, role, "", source)
    return assets


def build_fallback_visual_assets(story, extracted_assets):
    cards = []
    for asset in extracted_assets:
        visual_zh = asset.get("visual_description_zh") or asset.get("role", "")
        visual_en = fallback_visual_en(asset)
        name_en = asset.get("name_en") or romanize_like_name(asset.get("name", ""))
        cards.append({
            "name": asset.get("name"),
            "name_en": name_en,
            "card_type": asset.get("card_type"),
            "importance": asset.get("importance"),
            "faction": asset.get("faction"),
            "role": asset.get("role"),
            "description_zh": f"{asset.get('name')}：{asset.get('role')}。用于后续分镜保持视觉和身份一致。",
            "description_en": f"{name_en}: {asset.get('role')}. Used as a visual continuity anchor for later storyboards.",
            "personality_or_function_zh": asset.get("role"),
            "personality_or_function_en": asset.get("role"),
            "visual_description_zh": visual_zh,
            "visual_description_en": visual_en,
            "continuity_tags": fallback_tags_en(asset, visual_en),
            "continuity_tags_zh": fallback_tags_zh(asset, visual_zh),
            "source_mentions": [asset.get("source", "story_outline")],
            "image_prompt": (
                f"Character reference sheet, {name_en}, {visual_en}, full body and portrait views, "
                "consistent manga adventure style, clean linework, neutral background, no speech bubbles, no text."
            ),
        })

    return {
        "character_cards": cards,
        "factions": build_factions(cards),
        "scene_tone_cards": fallback_scene_tones(story),
    }


def romanize_like_name(name):
    return re.sub(r"\s+", " ", name or "Visual Asset").strip() or "Visual Asset"


def fallback_visual_en(asset):
    name_en = asset.get("name_en", "")
    role = asset.get("role", "")
    zh = asset.get("visual_description_zh", "")
    known = {
        "Rhino Bart": "strong rhinoceros warrior, worn leather armor, mysterious glowing cracks on the left horn, calm but burdened eyes",
        "Monkey Ah Ling": "agile monkey warrior, slightly fluffy squirrel-like tail, heterochromia eyes, athletic stance, alert expression",
        "Leopard Xiao Jin": "golden-patterned leopard scout, necklace from her missing brother, sharp observing eyes, cautious posture",
        "Bear Da Da": "large gentle brown bear, deep wise eyes, ancient rune birthmark on the chest, calm spiritual presence",
        "Mole Duo Duo": "small mole engineer with goggles, shy posture, tiny crystal fragments on fingers, tool pouch and nervous expression",
        "Wolf King Grey": "grey wolf leader, weathered cloak, tired noble eyes, scars from exile, protective stance",
        "Grey": "grey wolf leader, weathered cloak, tired noble eyes, scars from exile, protective stance",
        "Karl": "past-life guardian identity, spectral grey wolf aura, memory-fragment glow, wounded but resolute expression",
        "Xiao Jin's Brother": "young leopard spirit, soft golden markings, gentle eyes, faint memory-light aura, small necklace motif",
        "Exiled Clan": "weary northern forest refugees, wolves and mixed animals in patched cloaks, survival gear, hopeful but exhausted",
        "Heart of the Forest": "ancient living AI core, mossy stone rings, luminous roots, floating runes, warm green-gold energy",
        "Dawn Civilization": "ancient animal civilization, luminous crystal technology, elegant stone-and-light architecture, warm digital glyphs",
        "Memory Forest": "crystal forest space, glowing plants, floating memory shards, misty blue-green light",
        "Dawn City": "ancient digital city ruins, holographic animal silhouettes, crystal towers, golden-blue light",
        "Ancient AI": "abstract guardian intelligence, floating glyph halo, soft geometric light, calm testing presence",
    }
    if name_en in known:
        return known[name_en]
    if zh:
        return f"visually based on: {zh}"
    return f"visual anchor for {role}"


def fallback_tags_en(asset, visual_en):
    tags = [asset.get("name_en") or asset.get("name"), asset.get("card_type"), asset.get("faction")]
    for token in re.split(r"[,，]", visual_en):
        token = token.strip()
        if token:
            tags.append(token)
        if len(tags) >= 8:
            break
    return [tag for tag in tags if tag]


def fallback_tags_zh(asset, visual_zh):
    tags = [asset.get("name"), asset.get("card_type"), asset.get("faction")]
    if visual_zh:
        tags.extend([item.strip() for item in re.split(r"[，,]", visual_zh) if item.strip()][:5])
    return [tag for tag in tags if tag]


def build_factions(cards):
    factions = {
        "heroes": [],
        "villains_or_opposition": [],
        "neutral_or_testers": [],
        "support": [],
        "groups_or_entities": [],
    }
    for card in cards:
        name = card.get("name")
        faction = card.get("faction", "")
        card_type = card.get("card_type", "")
        if card_type in {"group", "entity"}:
            factions["groups_or_entities"].append(name)
        if faction == "heroes":
            factions["heroes"].append(name)
        elif faction in {"opposition", "villains"}:
            factions["villains_or_opposition"].append(name)
        elif faction in {"neutral_or_testers", "neutral"}:
            factions["neutral_or_testers"].append(name)
        elif faction == "support":
            factions["support"].append(name)
    return factions


def fallback_scene_tones(story):
    return [
        {
            "id": "mystical_forest_world",
            "title": "神秘森林世界基调",
            "title_en": "Mystical Forest World Tone",
            "purpose": "锁定森林之心入口、记忆森林、南方森林的核心场景样貌、风格情绪和可复用视觉元素。",
            "visual_mood": "mysterious, hopeful, misty, emotionally warm",
            "color_palette": "deep forest green, moss, dawn gold, soft cyan crystal glow",
            "key_locations": ["森林之心入口", "记忆森林", "南方森林"],
            "continuity_rules": ["16:9 landscape", "central moss-covered ancient arch", "luminous roots spreading left and right", "memory crystals and glowing plants", "foreground/midground/background layers", "not a precise map"],
            "image_prompt": "16:9 widescreen world visual bible image for the mystical forest side of the story. Show the Forest Heart entrance as a moss-covered ancient stone arch near the center, luminous roots spreading left and right, memory crystals and glowing plants in the foreground, layered giant trees and soft mist in the background, green-gold-cyan palette, natural materials mixed with subtle ancient technology. This is not a precise map, but it should show reusable spatial anchors, core location appearance, visual motifs, and atmosphere for later Scene2Talk backgrounds. Clean manga adventure style, no characters as the main subject, no speech bubbles, no readable text.",
        },
        {
            "id": "ancient_digital_civilization",
            "title": "晨曦数字文明基调",
            "title_en": "Ancient Digital Civilization Tone",
            "purpose": "锁定晨曦之城、森林之心核心、古代 AI 系统的核心场景样貌、风格情绪和可复用视觉元素。",
            "visual_mood": "ancient, sacred, technological, bittersweet",
            "color_palette": "warm gold, blue holographic light, pale stone, translucent crystal",
            "key_locations": ["晨曦之城", "森林之心核心", "古代数字遗迹"],
            "continuity_rules": ["16:9 landscape", "central ancient AI core or circular crystal plaza", "soft ring layout", "blue-gold holographic pathways", "pale stone and translucent crystal materials", "not a precise map"],
            "image_prompt": "16:9 widescreen world visual bible image for the Dawn digital civilization side of the story. Show a central ancient AI core or circular crystal plaza, pale stone ruins arranged in soft rings, holographic blue-gold light pathways, translucent crystal towers in the background, animal-scale architecture with sacred but melancholic atmosphere. This is not a precise map, but it should establish reusable location shapes, material rules, color rules, rough spatial anchors, and motifs for later Scene2Talk backgrounds. Clean manga fantasy sci-fi style, no characters, no speech bubbles, no readable text.",
        },
    ]


def validate_visual_assets(data, story):
    cards = data.get("character_cards")
    tones = data.get("scene_tone_cards")
    if not isinstance(cards, list) or not cards:
        raise RuntimeError("模型未返回 character_cards 数组")
    if not isinstance(tones, list) or len(tones) != 2:
        raise RuntimeError("模型必须返回 exactly 2 scene_tone_cards")

    names = {
        (card.get("name") or "").strip()
        for card in cards
    } | {
        (card.get("name_en") or "").strip()
        for card in cards
    }
    missing = []
    for source in story.get("characters", []):
        if source.get("name") not in names and source.get("name_en") not in names:
            missing.append(source.get("name") or source.get("name_en"))
    if missing:
        raise RuntimeError(f"角色卡缺少 story.characters 中的角色: {', '.join(missing)}")

    for card in cards:
        for key in [
            "name",
            "name_en",
            "card_type",
            "importance",
            "faction",
            "role",
            "description_zh",
            "description_en",
            "visual_description_zh",
            "visual_description_en",
            "image_prompt",
        ]:
            if not str(card.get(key) or "").strip():
                raise RuntimeError(f"角色卡字段为空: {card.get('name') or card.get('name_en')} / {key}")
        if "speech bubble" in card.get("image_prompt", "").lower():
            raise RuntimeError(f"角色参考图 prompt 不应包含 speech bubble: {card.get('name')}")

    for tone in tones:
        for key in ["id", "title", "title_en", "purpose", "visual_mood", "color_palette", "image_prompt"]:
            if not str(tone.get(key) or "").strip():
                raise RuntimeError(f"场景基调卡字段为空: {tone.get('id')} / {key}")
        prompt = tone.get("image_prompt", "").lower()
        if "16:9" not in prompt and "widescreen" not in prompt and "landscape" not in prompt:
            raise RuntimeError(f"场景基调图 prompt 未明确 16:9/landscape: {tone.get('id')}")


def write_asset_prompts(task_dir, visual_assets):
    character_dir = task_dir / "character_prompts"
    scene_tone_dir = task_dir / "scene_tone_prompts"
    character_dir.mkdir(parents=True, exist_ok=True)
    scene_tone_dir.mkdir(parents=True, exist_ok=True)

    for card in visual_assets.get("character_cards", []):
        name = card.get("name_en") or card.get("name")
        path = character_dir / f"{safe_filename(name)}.txt"
        path.write_text(card.get("image_prompt", "").strip() + "\n", encoding="utf-8")

    for tone in visual_assets.get("scene_tone_cards", []):
        name = tone.get("id") or tone.get("title_en") or tone.get("title")
        path = scene_tone_dir / f"{safe_filename(name)}.txt"
        path.write_text(tone.get("image_prompt", "").strip() + "\n", encoding="utf-8")

    return character_dir, scene_tone_dir


def update_progress(task_dir, summary):
    progress_path = task_dir / "data" / "progress.json"
    if not progress_path.exists():
        return
    progress = load_json(progress_path)
    progress.setdefault("status", {})
    progress["status"]["story_visual_assets"] = "completed"
    progress["story_visual_assets_summary"] = summary
    progress["updated_at"] = now_iso()
    save_json(progress_path, progress)


def save_story_arc_and_cards(task_dir):
    print("📖 生成故事脉络...", flush=True)
    story_arc = generate_story_arc(task_dir)
    arc_path = task_dir / "data" / "story_arc.json"
    save_json(arc_path, story_arc)
    print(f"   ✓ 故事脉络已保存：{arc_path}", flush=True)

    print("\n🎭 抽取全量角色/实体并生成视觉角色卡...", flush=True)
    visual_assets = generate_visual_assets(task_dir)
    cards_path = task_dir / "data" / "character_cards.json"
    save_json(cards_path, visual_assets)
    print(f"   ✓ 角色卡与场景基调已保存：{cards_path}", flush=True)

    character_dir, scene_tone_dir = write_asset_prompts(task_dir, visual_assets)
    print(f"   ✓ 角色头像提示词已保存：{character_dir}", flush=True)
    print(f"   ✓ 场景基调图提示词已保存：{scene_tone_dir}", flush=True)

    cards = visual_assets.get("character_cards", [])
    tones = visual_assets.get("scene_tone_cards", [])
    summary = {
        "character_cards": len(cards),
        "scene_tone_cards": len(tones),
        "character_prompts_dir": str(character_dir),
        "scene_tone_prompts_dir": str(scene_tone_dir),
    }
    update_progress(task_dir, summary)

    print("\n" + "=" * 60)
    print("📊 故事视觉资产生成完成")
    print("=" * 60)
    print(f"📖 故事脉络：{len(story_arc.get('story_arc', []))} 个章节")
    print(f"🎭 角色/实体卡：{len(cards)} 张")
    print(f"🌄 场景基调图：{len(tones)} 张")

    factions = visual_assets.get("factions", {})
    for key, value in factions.items():
        if isinstance(value, list):
            print(f"   - {key}: {len(value)}")

    print("\n📁 输出文件：")
    print(f"   - {arc_path}")
    print(f"   - {cards_path}")
    print(f"   - {character_dir}/")
    print(f"   - {scene_tone_dir}/")


def main():
    parser = argparse.ArgumentParser(description="Generate story arc, full character cards, and scene tone prompts.")
    parser.add_argument("task_dir")
    args = parser.parse_args()
    task_dir = require_task_dir(args.task_dir)
    save_story_arc_and_cards(task_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
