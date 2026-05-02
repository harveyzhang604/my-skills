#!/usr/bin/env python3
"""Generate visual reference images and crop character cards.

Stage 2 visual assets:
- One or more 16:9 character/entity sheets: fixed 8-cell 2x4 grid.
- Cropped per-card PNGs from the sheet.
- Two scene tone reference images.

Image generation is delegated to chatgpt-image's reusable OpenCLI service.
"""

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from task_path_guard import require_task_dir


SERVICE = Path("/Users/zhanghua/.claude/skills/chatgpt-image/scripts/opencli_image_service.py")


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


def safe_filename(value):
    out = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_") or "visual_card"


def grid_for_count(count):
    if count <= 0:
        raise ValueError("empty character card list")
    if count > 8:
        raise ValueError("single character sheet supports at most 8 cards")
    return 2, 4


def chunk_cards(cards, sheet_size=8):
    chunks = []
    remaining = list(cards)
    while remaining:
        chunks.append(remaining[:sheet_size])
        remaining = remaining[sheet_size:]
    return chunks


def build_character_sheet_prompt(cards, rows, cols):
    ordered = []
    for idx, card in enumerate(cards, start=1):
        ordered.append(
            f"{idx}. {card.get('name_en')} ({card.get('name')}): "
            f"{card.get('visual_description_en')}. "
            f"Continuity tags: {', '.join(card.get('continuity_tags') or [])}."
        )
    empty_cells = rows * cols - len(cards)
    empty_rule = ""
    if empty_cells:
        empty_rule = f" Leave the final {empty_cells} unused cell(s) as a simple neutral parchment placeholder with no character."

    return (
        "Create one 16:9 widescreen manga character reference sheet, exact full-canvas grid, "
        f"{rows} rows x {cols} columns, equal-size cells, no header, no title, no speech bubbles, "
        "no captions, no readable labels, no random text. Put exactly one character/entity reference in each cell, "
        "centered with generous padding, full-body or clear bust view as appropriate, consistent clean manga adventure style, "
        "same lighting direction and linework across all cells, subtle thin cell dividers only. "
        "Order cells left-to-right on the top row, then left-to-right on the bottom row. "
        f"{empty_rule}\n\n"
        "Cell order and visual requirements:\n" + "\n".join(ordered)
    )


def build_scene_tone_prompt(tone):
    prompt = tone.get("image_prompt", "").strip()
    return (
        f"{prompt}\n\n"
        "This is a world visual bible image for later Scene2Talk comic backgrounds, not a pure mood board and not a precise map. "
        "It must show core location appearance, reusable visual motifs, material and color rules, and rough spatial anchors. "
        "No speech bubbles, no captions, no readable text, no UI, no watermark. "
        "Keep it 16:9 landscape and visually inspectable."
    )


def call_service(command, **kwargs):
    args = [sys.executable, str(SERVICE), command]
    for key, value in kwargs.items():
        args.extend([f"--{key.replace('_', '-')}", str(value)])
    proc = subprocess.run(args, text=True, capture_output=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {"ok": False, "status": "service_error", "error": output[-1000:]}
    data["_returncode"] = proc.returncode
    data["_output_tail"] = output[-1000:]
    return data


def generate_image(prompt, output_path, wait_schedule, repair_retries):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = call_service(
        "generate",
        prompt=prompt,
        output=output_path,
        wait_schedule=wait_schedule,
        repair_retries=repair_retries,
    )
    return result


def crop_sheet(sheet_path, cards, rows, cols, output_dir, start_index=1):
    output_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(sheet_path).convert("RGBA")
    width, height = image.size
    cell_w = width / cols
    cell_h = height / rows
    outputs = []

    for idx, card in enumerate(cards):
        global_index = start_index + idx
        row = idx // cols
        col = idx % cols
        left = round(col * cell_w)
        upper = round(row * cell_h)
        right = round((col + 1) * cell_w)
        lower = round((row + 1) * cell_h)
        crop = image.crop((left, upper, right, lower))
        filename = f"{global_index:02d}_{safe_filename(card.get('name_en') or card.get('name'))}.png"
        out = output_dir / filename
        crop.save(out)
        outputs.append({
            "index": global_index,
            "name": card.get("name"),
            "name_en": card.get("name_en"),
            "filename": filename,
            "crop_box": [left, upper, right, lower],
            "size": list(crop.size),
        })
    return outputs


def main():
    parser = argparse.ArgumentParser(description="Generate and crop cd-generator visual reference images.")
    parser.add_argument("task_dir")
    parser.add_argument("--wait-schedule", default="60,60,60,120,180,240")
    parser.add_argument("--repair-retries", type=int, default=2)
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--crop-only", action="store_true")
    parser.add_argument("--scene-tones-only", action="store_true")
    args = parser.parse_args()

    task_dir = require_task_dir(args.task_dir)
    cards_path = task_dir / "data" / "character_cards.json"
    assets = load_json(cards_path)
    cards = assets.get("character_cards", [])
    scene_tones = assets.get("scene_tone_cards", [])
    card_chunks = chunk_cards(cards, sheet_size=8)

    sheet_dir = task_dir / "character_sheets"
    prompt_dir = task_dir / "character_sheet_prompts"
    character_images_dir = task_dir / "character_images"
    scene_tone_images_dir = task_dir / "scene_tone_images"
    scene_tone_prompt_dir = task_dir / "scene_tone_prompts"
    manifest_path = task_dir / "data" / "visual_reference_manifest.json"
    for directory in [sheet_dir, prompt_dir, character_images_dir, scene_tone_images_dir, scene_tone_prompt_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    if args.scene_tones_only and manifest_path.exists():
        manifest = load_json(manifest_path)
        manifest["updated_at"] = now_iso()
        manifest["scene_tone_images"] = []
    else:
        manifest = {
            "generated_at": now_iso(),
            "character_sheet_rule": {
                "grid": "2x4",
                "cells_per_sheet": 8,
                "split_when_more_than": 8,
                "empty_cells": "leave unused cells blank/neutral when the last sheet has fewer than 8 assets",
            },
            "character_sheets": [],
            "scene_tone_images": [],
            "cropped_character_cards": [],
        }

    global_card_index = 1
    if not args.scene_tones_only:
        for sheet_index, sheet_cards in enumerate(card_chunks, start=1):
            rows, cols = grid_for_count(len(sheet_cards))
            sheet_prompt = build_character_sheet_prompt(sheet_cards, rows, cols)
            sheet_prompt_path = prompt_dir / f"character_sheet_{sheet_index:02d}.txt"
            sheet_prompt_path.write_text(sheet_prompt + "\n", encoding="utf-8")
            sheet_path = sheet_dir / f"character_sheet_{sheet_index:02d}.png"
            sheet_manifest = {
                "index": sheet_index,
                "prompt_file": str(sheet_prompt_path),
                "image_file": str(sheet_path),
                "rows": rows,
                "cols": cols,
                "card_count": len(sheet_cards),
                "card_names": [card.get("name_en") or card.get("name") for card in sheet_cards],
            }

            if not args.skip_generate and not args.crop_only:
                print(f"🎭 生成角色总览 sheet {sheet_index}/{len(card_chunks)}：{rows}x{cols} / {len(sheet_cards)} 张卡", flush=True)
                sheet_result = generate_image(sheet_prompt, sheet_path, args.wait_schedule, args.repair_retries)
                sheet_manifest["generation_result"] = sheet_result
                if not (sheet_result.get("ok") and sheet_path.exists() and sheet_path.stat().st_size > 0):
                    manifest["character_sheets"].append(sheet_manifest)
                    save_json(manifest_path, manifest)
                    raise RuntimeError(f"角色总览 sheet {sheet_index} 生成失败: {sheet_result}")

            if sheet_path.exists() and sheet_path.stat().st_size > 0:
                print(f"✂️  裁切角色卡 sheet {sheet_index}...", flush=True)
                cropped = crop_sheet(sheet_path, sheet_cards, rows, cols, character_images_dir, start_index=global_card_index)
                for item in cropped:
                    item["sheet_index"] = sheet_index
                manifest["cropped_character_cards"].extend(cropped)
                global_card_index += len(sheet_cards)
            else:
                print(f"⚠️  未找到角色总览 sheet {sheet_index}，跳过裁切。", flush=True)

            manifest["character_sheets"].append(sheet_manifest)

    if not args.skip_generate and not args.crop_only:
        for idx, tone in enumerate(scene_tones, start=1):
            tone_id = tone.get("id") or f"scene_tone_{idx:02d}"
            prompt = build_scene_tone_prompt(tone)
            prompt_path = scene_tone_prompt_dir / f"{safe_filename(tone_id)}.txt"
            output_path = scene_tone_images_dir / f"{idx:02d}_{safe_filename(tone_id)}.png"
            prompt_path.write_text(prompt + "\n", encoding="utf-8")
            print(f"🌄 生成场景基调图 {idx}/{len(scene_tones)}：{tone_id}", flush=True)
            result = generate_image(prompt, output_path, args.wait_schedule, args.repair_retries)
            manifest["scene_tone_images"].append({
                "id": tone_id,
                "prompt_file": str(prompt_path),
                "image_file": str(output_path),
                "generation_result": result,
            })
            if not (result.get("ok") and output_path.exists() and output_path.stat().st_size > 0):
                print(f"   ⚠️  场景基调图生成未完成：{tone_id} / {result.get('status')}", flush=True)
            time.sleep(2)

    save_json(manifest_path, manifest)
    print("\n✅ 视觉参考图处理完成")
    print(f"   - 角色总览图：{sheet_dir}")
    print(f"   - 裁切角色卡：{character_images_dir}")
    print(f"   - 场景基调图：{scene_tone_images_dir}")
    print(f"   - 清单：{manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
