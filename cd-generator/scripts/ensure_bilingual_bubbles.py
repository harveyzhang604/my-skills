#!/usr/bin/env python3
"""
Ensure storyboard image prompts request bilingual Chinese+English bubbles.
"""

import argparse
import json
import re
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def has_bilingual_rule(prompt):
    lower = prompt.lower()
    return (
        "bilingual" in lower
        or "chinese + english" in lower
        or "chinese and english" in lower
        or re.search(r'"[^"]*[A-Za-z][^"]*/[^"]*[\u4e00-\u9fff][^"]*"', prompt)
    )


def has_bilingual_addition(prompt):
    return "Use 1-3 short bilingual Chinese + English speech bubbles/captions for dialogue practice" in prompt


def has_bubble_budget_rule(prompt):
    lower = prompt.lower()
    has_scene_budget = (
        "max 2" in lower
        or "maximum 2" in lower
        or "max two" in lower
        or "最多 2" in prompt
        or "最多2" in prompt
    )
    has_total_budget = (
        "max 6" in lower
        or "maximum 6" in lower
        or "max six" in lower
        or "最多 6" in prompt
        or "最多6" in prompt
    )
    has_default = "default 1-3" in lower or "1-3" in lower
    return has_scene_budget and has_total_budget and has_default


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


def has_english_only_conflict(prompt):
    lower = prompt.lower()
    conflict_patterns = [
        "english text only",
        "english only in speech bubbles",
        "all text in english only",
        "all visible text in english only",
        "all visible text, signs, captions, and speech bubbles must be english only",
        "visible text must be in english",
        "all readable text in english",
        "english-only",
        "no chinese",
    ]
    return any(pattern in lower for pattern in conflict_patterns) or bool(
        re.search(r"speech bubble[s]?\s+'[^']+'\s+in english", prompt, re.IGNORECASE)
        or re.search(r"(?<!bilingual chinese \+ )(?<!bilingual )\b(?:one short |three short |three )?english speech bubbles?\b", prompt, re.IGNORECASE)
    )


def pick_bubble_pairs(chapter, page_number):
    page = next((p for p in chapter.get("pages", []) if int(p.get("page_number", 0)) == page_number), None)
    if not page:
        return []
    pairs = []
    for line in page.get("dialogues", []):
        en = str(line.get("text_en") or "").strip()
        zh = str(line.get("text_zh") or "").strip()
        if not en or not zh:
            continue
        pairs.append((en, zh))
    return pairs


def short_pairs(bubble_pairs, limit=2):
    picked = []
    for en, zh in bubble_pairs:
        if len(en.split()) <= 10 and len(zh) <= 18:
            picked.append((en, zh))
        if len(picked) >= limit:
            return picked
    return bubble_pairs[:limit]


def format_examples(bubble_pairs):
    examples = short_pairs(bubble_pairs)
    if not examples:
        return '"I understand. / 我明白了。"'
    return ", ".join(f'"{en} / {zh}"' for en, zh in examples)


def pair_for_english_text(text, bubble_pairs):
    normalized = normalize_dialogue_text(text)
    for en, zh in bubble_pairs:
        normalized_en = normalize_dialogue_text(en)
        if normalized_en == normalized or normalized in normalized_en or normalized_en in normalized:
            return f'bilingual speech bubble "{en} / {zh}"'
    return "bilingual Chinese + English speech bubble"


def normalize_dialogue_text(text):
    text = str(text or "").strip().lower()
    text = re.sub(r"[.。…!！?？'\"’‘`]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def bilingual_for_quoted_text(text, bubble_pairs):
    normalized = normalize_dialogue_text(text)
    if not normalized:
        return text
    for en, zh in bubble_pairs:
        if normalize_dialogue_text(en) == normalized:
            return f"{en} / {zh}"
        normalized_en = normalize_dialogue_text(en)
        if normalized in normalized_en or normalized_en in normalized:
            return f"{en} / {zh}"
    return text


def text_variants(text):
    variants = {str(text or "").strip()}
    compact = str(text or "").strip()
    variants.add(compact.replace("...", "."))
    variants.add(compact.replace("?!", "?"))
    variants.add(compact.replace("?", ""))
    variants.add(compact.replace("!", ""))
    variants.add(compact.replace("...", ".").replace("?!", "?"))
    return {item for item in variants if item}


def replace_known_dialogue(prompt, bubble_pairs):
    result = prompt
    for en, zh in bubble_pairs:
        paired = f"{en} / {zh}"
        for variant in text_variants(en):
            result = result.replace(f"speech bubble '{variant}'", f'bilingual speech bubble "{paired}"')
            result = result.replace(f"speech bubbles '{variant}'", f'bilingual speech bubble "{paired}"')
    return result


def pair_quoted_dialogue(prompt, bubble_pairs):
    def replace_double(match):
        original = match.group(1)
        if "/" in original and re.search(r"[\u4e00-\u9fff]", original):
            return match.group(0)
        paired = bilingual_for_quoted_text(original, bubble_pairs)
        if paired == original:
            return match.group(0)
        return f'"{paired}"'

    prompt = replace_known_dialogue(prompt, bubble_pairs)
    prompt = re.sub(r'"([^"]+)"', replace_double, prompt)
    return prompt


def normalize_bilingual_phrasing(prompt):
    sanitized = prompt
    previous = None
    while previous != sanitized:
        previous = sanitized
        sanitized = re.sub(
            r"bilingual Chinese \+ (?:bilingual Chinese \+ )+English",
            "bilingual Chinese + English",
            sanitized,
            flags=re.IGNORECASE,
        )
    repeated_rule = re.compile(
        r"\s*Use 1-3 short bilingual Chinese \+ English speech bubbles/captions for dialogue practice, "
        r"with paired readable text such as .*?; keep the bilingual text large, clean, and readable\.",
        re.IGNORECASE,
    )
    matches = list(repeated_rule.finditer(sanitized))
    if len(matches) > 1:
        keep = matches[-1].group(0)
        sanitized = repeated_rule.sub("", sanitized).rstrip(". ") + "." + keep
    sanitized = re.sub(r"\s+\.", ".", sanitized)
    return sanitized


def sanitize_prompt(prompt, bubble_pairs):
    sanitized = str(prompt or "")

    def speech_bubble_repl(match):
        return pair_for_english_text(match.group(1), bubble_pairs)

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
    for pattern, replacement in replacements:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    sanitized = re.sub(
        r"speech bubble\s+'([^']+)'\s+in English",
        speech_bubble_repl,
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"speech bubbles?\s+'([^']+)'\s+in English",
        speech_bubble_repl,
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = pair_quoted_dialogue(sanitized, bubble_pairs)
    sanitized = normalize_bilingual_phrasing(sanitized)
    sanitized = re.sub(r"\s{2,}", " ", sanitized).strip()
    return sanitized


def sanitize_storyboard_strings(value, bubble_pairs):
    if isinstance(value, dict):
        return {key: sanitize_storyboard_strings(item, bubble_pairs) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_storyboard_strings(item, bubble_pairs) for item in value]
    if isinstance(value, str) and has_english_only_conflict(value):
        return sanitize_prompt(value, bubble_pairs)
    return value


def ensure_prompt(data, bubble_pairs):
    storyboard = data.get("storyboard", {})
    before = json.dumps(storyboard, ensure_ascii=False, sort_keys=True)
    data["storyboard"] = sanitize_storyboard_strings(storyboard, bubble_pairs)
    storyboard = data["storyboard"]

    prompt = sanitize_prompt(str(storyboard.get("image_prompt") or "").strip(), bubble_pairs)
    if (not has_bilingual_rule(prompt) or has_english_only_conflict(prompt)) and not has_bilingual_addition(prompt):
        examples = format_examples(bubble_pairs)
        addition = (
            " Use 1-3 short bilingual Chinese + English speech bubbles/captions for dialogue practice, "
            f"with paired readable text such as {examples}; keep the bilingual text large, clean, and readable."
        )
        prompt = prompt.rstrip(".") + "." + addition
    if not has_bubble_budget_rule(prompt):
        prompt = (
            prompt.rstrip(".")
            + ". Bubble budget: max 2 bilingual bubbles/captions per visible scene, max 6 in the whole image, default 1-3; only multi-scene, ensemble, or dream-montage pages should approach 6. Keep each bubble brief, with English above Chinese."
        )
    if not has_ui_safety_rule(prompt):
        prompt = (
            prompt.rstrip(".")
            + ". UI safety margins: avoid the top 12% of the image for speech bubbles, faces, and key readable text; keep a 6% left/right edge margin for bubbles, faces, and important props."
        )
    storyboard["image_prompt"] = prompt

    after = json.dumps(storyboard, ensure_ascii=False, sort_keys=True)
    return before != after


def parse_args():
    parser = argparse.ArgumentParser(description="Add bilingual bubble requirements to storyboard prompts.")
    parser.add_argument("task_dir")
    parser.add_argument("--chapter", type=int, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    task_dir = Path(args.task_dir)
    chapter = load_json(task_dir / "scripts" / f"chapter{args.chapter}.json")
    changed = 0
    for path in sorted((task_dir / "storyboards").glob(f"chapter{args.chapter}_page*.json")):
        match = re.search(r"_page(\d+)", path.stem)
        if not match:
            continue
        page_number = int(match.group(1))
        data = load_json(path)
        bubble_pairs = pick_bubble_pairs(chapter, page_number)
        if ensure_prompt(data, bubble_pairs):
            save_json(path, data)
            changed += 1
            print(f"✅ 已清理并补中英双语气泡规则：{path.name}")
    print(f"完成：更新 {changed} 个 storyboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
