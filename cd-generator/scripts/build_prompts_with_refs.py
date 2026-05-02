#!/usr/bin/env python3
"""Build image prompts with compact character and scene continuity references."""

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


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    return re.sub(r"_+", "_", value).strip("_") or "visual_ref"


def plain_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(plain_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(plain_text(item) for item in value.values())
    return ""


def english_aliases(name: str, card_type: str = "character") -> list[str]:
    aliases = []
    normalized = (name or "").strip()
    if not normalized:
        return aliases
    aliases.append(normalized)
    tokens = re.findall(r"[A-Za-z][A-Za-z']*", normalized)
    if card_type == "character" and len(tokens) >= 2:
        for index in range(len(tokens) - 1):
            pair = " ".join(tokens[index : index + 2])
            if pair.lower() not in {"jin's brother"}:
                aliases.append(pair)
    if "Heart of the Forest" in normalized:
        aliases.extend(["Forest Heart", "Heart of the Forest"])
    if "Dawn Civilization" in normalized:
        aliases.extend(["Dawn Civilization", "Dawn ruins"])
    return aliases


def build_card_refs(task_dir: Path) -> list[dict]:
    cards_data = load_json(task_dir / "data" / "character_cards.json", default={}) or {}
    cards = cards_data.get("character_cards", [])
    refs = []
    for index, card in enumerate(cards, start=1):
        name = card.get("name") or ""
        name_en = card.get("name_en") or name
        card_type = card.get("card_type") or "character"
        aliases = []
        aliases.extend(english_aliases(name_en, card_type))
        if name:
            aliases.append(name)
        image_name = f"{index:02d}_{slugify(name_en)}.png"
        refs.append(
            {
                "name": name,
                "name_en": name_en,
                "card_type": card_type,
                "importance": card.get("importance") or "",
                "visual_description_en": card.get("visual_description_en") or card.get("description_en") or "",
                "personality_or_function_en": card.get("personality_or_function_en") or "",
                "continuity_tags": card.get("continuity_tags") or [],
                "aliases": sorted(set(alias for alias in aliases if alias)),
                "image_file": str(task_dir / "character_images" / image_name),
            }
        )
    return refs


def english_match(text: str, alias: str) -> bool:
    if not alias or re.search(r"[\u4e00-\u9fff]", alias):
        return alias in text
    pattern = r"(?<![A-Za-z0-9])" + re.escape(alias.lower()) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text.lower()) is not None


def find_matching_refs(text: str, refs: list[dict]) -> list[dict]:
    matched = []
    for ref in refs:
        if any(english_match(text, alias) for alias in ref["aliases"]):
            matched.append(ref)
    matched.sort(key=lambda item: (0 if item["importance"] == "primary" else 1, item["name_en"]))
    return matched[:8]


def build_scene_refs(task_dir: Path, text: str) -> list[dict]:
    cards_data = load_json(task_dir / "data" / "character_cards.json", default={}) or {}
    scene_cards = cards_data.get("scene_tone_cards", []) or []
    selected = []
    lower = text.lower()
    for card in scene_cards:
        haystacks = " ".join(
            [
                card.get("id", ""),
                card.get("title", ""),
                card.get("title_en", ""),
                " ".join(card.get("key_locations", []) or []),
            ]
        )
        if any(token and token.lower() in lower for token in re.findall(r"[A-Za-z][A-Za-z ]{3,}", haystacks)):
            selected.append(card)
            continue
        if card.get("id") == "natural_mystical_forest" and any(
            token in lower for token in ["forest", "tree", "moss", "archway", "mist", "memory"]
        ):
            selected.append(card)
        if card.get("id") == "ancient_digital_civilization" and any(
            token in lower for token in ["civilization", "holographic", "ai core", "digital", "ruins", "crystal plaza"]
        ):
            selected.append(card)
    unique = []
    seen = set()
    for card in selected:
        card_id = card.get("id")
        if card_id and card_id not in seen:
            seen.add(card_id)
            unique.append(card)
    return unique[:2]


def compact_character_block(refs: list[dict]) -> str:
    if not refs:
        return ""
    lines = [
        "Character continuity references (follow these identities; do not redesign the characters):"
    ]
    for ref in refs:
        tags = ", ".join(ref.get("continuity_tags") or [])
        parts = [f"{ref['name_en']}: {ref['visual_description_en']}"]
        if tags:
            parts.append(f"fixed tags: {tags}")
        lines.append("- " + "; ".join(part for part in parts if part.strip()))
    return "\n".join(lines)


def compact_scene_block(scene_refs: list[dict]) -> str:
    if not scene_refs:
        return ""
    lines = ["Scene visual bible references (keep world style consistent):"]
    for ref in scene_refs:
        rules = ", ".join((ref.get("continuity_rules") or [])[:5])
        palette = ref.get("color_palette") or ""
        mood = ref.get("visual_mood") or ""
        lines.append(f"- {ref.get('title_en') or ref.get('id')}: mood {mood}; palette {palette}; rules {rules}")
    return "\n".join(lines)


def page_context(task_dir: Path, chapter: int, page: int, prompt: str, storyboard: dict) -> str:
    chapter_data = load_json(task_dir / "scripts" / f"chapter{chapter}.json", default={}) or {}
    page_data = {}
    for candidate in chapter_data.get("pages", []) or []:
        if int(candidate.get("page_number", 0)) == page:
            page_data = candidate
            break
    return "\n".join([prompt, plain_text(storyboard), plain_text(page_data)])


def build_prompt(task_dir: Path, prompt_path: Path, refs: list[dict]) -> tuple[str, dict]:
    match = re.search(r"chapter(\d+)_page(\d+)\.txt$", prompt_path.name)
    if not match:
        raise ValueError(f"无法从文件名解析章节页码: {prompt_path}")
    chapter = int(match.group(1))
    page = int(match.group(2))
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    storyboard = load_json(task_dir / "storyboards" / f"chapter{chapter}_page{page}.json", default={}) or {}
    context = page_context(task_dir, chapter, page, prompt, storyboard)
    matching_refs = find_matching_refs(context, refs)
    scene_refs = build_scene_refs(task_dir, context)

    blocks = [prompt]
    character_block = compact_character_block(matching_refs)
    scene_block = compact_scene_block(scene_refs)
    if character_block:
        blocks.append(character_block)
    if scene_block:
        blocks.append(scene_block)
    blocks.append(
        "Reference handling note: the current OpenCLI text image command cannot attach local image files, so these written references are the authoritative visual identity constraints for this request."
    )

    meta = {
        "chapter": chapter,
        "page": page,
        "source_prompt": str(prompt_path),
        "generated_at": now_iso(),
        "matched_character_refs": [
            {
                "name": ref["name"],
                "name_en": ref["name_en"],
                "card_type": ref["card_type"],
                "image_file": ref["image_file"],
                "aliases": ref["aliases"],
            }
            for ref in matching_refs
        ],
        "matched_scene_refs": [
            {
                "id": ref.get("id"),
                "title_en": ref.get("title_en"),
            }
            for ref in scene_refs
        ],
        "opencli_reference_mode": "text_only_character_and_scene_continuity",
    }
    return "\n\n".join(blocks).strip() + "\n", meta


def parse_args():
    parser = argparse.ArgumentParser(description="Build cd-generator image prompts with character/scene references.")
    parser.add_argument("task_dir")
    parser.add_argument("--chapter", type=int)
    parser.add_argument("--page", type=int)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    task_dir = require_task_dir(args.task_dir)
    prompt_dir = task_dir / "prompts"
    output_dir = task_dir / "prompts_with_refs"
    refs = build_card_refs(task_dir)

    prompt_files = sorted(prompt_dir.glob("chapter*_page*.txt"))
    if args.chapter:
        prompt_files = [p for p in prompt_files if re.search(fr"chapter{args.chapter}_page\d+\.txt$", p.name)]
    if args.page:
        prompt_files = [p for p in prompt_files if re.search(fr"page{args.page}\.txt$", p.name)]

    if not prompt_files:
        raise SystemExit(f"没有找到可处理的提示词: {prompt_dir}")

    built = 0
    for prompt_path in prompt_files:
        target = output_dir / prompt_path.name
        meta_target = output_dir / f"{prompt_path.stem}.refs.json"
        if target.exists() and not args.force:
            continue
        enhanced, meta = build_prompt(task_dir, prompt_path, refs)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(enhanced, encoding="utf-8")
        save_json(meta_target, meta)
        built += 1
        print(
            f"✅ 已生成增强提示词 {target.name}: "
            f"{len(meta['matched_character_refs'])} 个角色/实体参照, "
            f"{len(meta['matched_scene_refs'])} 个场景参照",
            flush=True,
        )

    print(f"完成：生成/更新 {built} 个 prompts_with_refs 文件，目录：{output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
