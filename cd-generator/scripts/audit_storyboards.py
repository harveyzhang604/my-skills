#!/usr/bin/env python3
"""
Lightweight storyboard and image-prompt audit for cd-generator.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


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


def has_16x9(prompt):
    lower = prompt.lower()
    return any(token in lower for token in ["16:9", "16x9", "widescreen", "landscape"])


def has_zones(prompt):
    lower = prompt.lower()
    return all(token in lower for token in ["left", "center", "right"]) or "diagonal" in lower


def has_bilingual_text_rule(prompt):
    lower = prompt.lower()
    return (
        "bilingual" in lower
        or "chinese + english" in lower
        or "chinese and english" in lower
        or re.search(r'"[^"]*[A-Za-z][^"]*/[^"]*[\u4e00-\u9fff][^"]*"', prompt)
    )


def has_bubble_budget_rule(prompt):
    lower = prompt.lower()
    return (
        "max 2" in lower
        or "maximum 2" in lower
        or "max two" in lower
        or "最多 2" in prompt
        or "最多2" in prompt
        or "default 1-3" in lower
        or "1-3" in lower
    ) and (
        "max 6" in lower
        or "maximum 6" in lower
        or "max six" in lower
        or "最多 6" in prompt
        or "最多6" in prompt
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


def count_declared_bubbles(storyboard, prompt):
    text = json.dumps(storyboard.get("visual_elements", {}), ensure_ascii=False) + " " + prompt
    return len(re.findall(r"\b(?:bilingual\s+)?speech bubble[s]?\b|caption[s]?", text, re.IGNORECASE))


def has_english_only_conflict(prompt):
    lower = prompt.lower()
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
    return any(pattern in lower for pattern in conflict_patterns) or bool(
        re.search(r"speech bubble[s]?\s+'[^']+'\s+in english", prompt, re.IGNORECASE)
        or re.search(r"(?<!bilingual chinese \+ )(?<!bilingual )\b(?:one short |three short |three )?english speech bubbles?\b", prompt, re.IGNORECASE)
    )


def audit_storyboard(path):
    data = load_json(path)
    storyboard = data.get("storyboard") or {}
    prompt = storyboard.get("image_prompt") or ""
    prompt_zh = storyboard.get("image_prompt_zh") or ""
    storyboard_text = json.dumps(storyboard, ensure_ascii=False)
    issues = []

    for key in ["composition", "left_zone", "center_zone", "right_zone", "image_prompt", "image_prompt_zh"]:
        if not str(storyboard.get(key) or "").strip():
            issues.append({
                "severity": "error",
                "code": f"missing_{key}",
                "message": f"storyboard.{key} 为空",
                "suggestion": f"补充 storyboard.{key}",
            })

    if prompt and not has_16x9(prompt):
        issues.append({
            "severity": "warning",
            "code": "image_prompt_missing_16x9",
            "message": "英文 image_prompt 未明确 16:9 / landscape / widescreen。",
            "suggestion": "加入 16:9 widescreen landscape composition。",
        })
    if prompt and not has_zones(prompt):
        issues.append({
            "severity": "warning",
            "code": "image_prompt_missing_zones",
            "message": "英文 image_prompt 未明确 left/center/right 或 diagonal 构图。",
            "suggestion": "加入 LEFT/CENTER/RIGHT zones 或 diagonal split。",
        })
    if prompt and not has_bilingual_text_rule(prompt):
        issues.append({
            "severity": "warning",
            "code": "image_prompt_missing_bilingual_text",
            "message": "image_prompt 未明确对话气泡/字幕需要中英双语。",
            "suggestion": "加入 bilingual Chinese + English speech bubbles，例如 \"I must go. / 我必须去。\"。",
        })
    if prompt and not has_bubble_budget_rule(prompt):
        issues.append({
            "severity": "warning",
            "code": "image_prompt_missing_bubble_budget",
            "message": "image_prompt 未明确气泡数量预算：每个场景最多 2 个、整图最多 6 个、默认 1-3 个。",
            "suggestion": "加入 bubble budget 规则，避免图片模型把对白塞满画面。",
        })
    if prompt and not has_ui_safety_rule(prompt):
        issues.append({
            "severity": "warning",
            "code": "image_prompt_missing_ui_safety_margin",
            "message": "image_prompt 未明确 UI 安全区：顶部 12% 避开气泡/脸/关键文字，左右 6% 留边距。",
            "suggestion": "加入 UI safety margins: avoid the top 12%... keep a 6% left/right edge margin。",
        })
    bubble_mentions = count_declared_bubbles(storyboard, prompt)
    if bubble_mentions > 10:
        issues.append({
            "severity": "warning",
            "code": "image_prompt_too_many_bubble_mentions",
            "message": f"提示词中 speech bubble/caption 提及过多：{bubble_mentions} 次，可能导致画面塞满文字。",
            "suggestion": "减少气泡描述，保留默认 1-3 个，复杂多场景页也不要超过整图 6 个。",
        })
    if prompt and has_english_only_conflict(prompt):
        issues.append({
            "severity": "error",
            "code": "image_prompt_english_only_conflict",
            "message": "image_prompt 仍包含 English only / no Chinese 等旧规则，会和中英双语气泡要求冲突。",
            "suggestion": "运行 ensure_bilingual_bubbles.py 清理旧规则，保留 bilingual Chinese + English visible dialogue/caption text。",
        })
    if storyboard_text and has_english_only_conflict(storyboard_text):
        issues.append({
            "severity": "error",
            "code": "storyboard_english_only_conflict",
            "message": "storyboard 其他字段仍包含 English speech bubbles / English only 等旧规则。",
            "suggestion": "运行 ensure_bilingual_bubbles.py 清理整个 storyboard，而不只是 image_prompt。",
        })
    if len(prompt) > 1800:
        issues.append({
            "severity": "warning",
            "code": "image_prompt_too_long",
            "message": f"英文 image_prompt 过长：{len(prompt)} chars。",
            "suggestion": "压缩为单一可渲染场景，减少同时发生的事件。",
        })
    if len(prompt) < 250:
        issues.append({
            "severity": "warning",
            "code": "image_prompt_too_short",
            "message": f"英文 image_prompt 过短：{len(prompt)} chars。",
            "suggestion": "补充角色、动作、构图、光线、文字规则和风格。",
        })
    if prompt and not any(token in prompt.lower() for token in ["speech bubble", "caption"]):
        issues.append({
            "severity": "warning",
            "code": "image_prompt_missing_speech_or_caption",
            "message": "image_prompt 未包含 speech bubble 或 caption。",
            "suggestion": "加入 1-3 个短中英双语 speech bubbles/captions。",
        })
    if prompt_zh and len(prompt_zh) < 80:
        issues.append({
            "severity": "info",
            "code": "image_prompt_zh_short",
            "message": "中文提示词偏短，人工审稿信息可能不足。",
            "suggestion": "补充中文场景、人物动作、构图和气氛说明。",
        })

    return {
        "file": str(path),
        "chapter": data.get("chapter"),
        "page": data.get("page"),
        "prompt_length": len(prompt),
        "prompt_zh_length": len(prompt_zh),
        "issues": issues,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Audit storyboard JSON and image prompts.")
    parser.add_argument("task_dir")
    parser.add_argument("--chapter", type=int)
    parser.add_argument("--output")
    return parser.parse_args()


def main():
    args = parse_args()
    task_dir = Path(args.task_dir)
    storyboards_dir = task_dir / "storyboards"
    files = sorted(storyboards_dir.glob("chapter*_page*.json"))
    if args.chapter is not None:
        files = [path for path in files if path.name.startswith(f"chapter{args.chapter}_page")]

    report = {
        "checked_at": now_iso(),
        "task_dir": str(task_dir),
        "storyboards": [],
        "summary": {
            "storyboard_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
        },
    }

    for path in files:
        item = audit_storyboard(path)
        report["storyboards"].append(item)
        report["summary"]["storyboard_count"] += 1
        for issue in item["issues"]:
            report["summary"][f"{issue['severity']}_count"] += 1

    output = Path(args.output) if args.output else task_dir / "quality" / "storyboard_audit.json"
    save_json(output, report)

    print("🎬 分镜与图片提示词审查")
    print(f"   - 分镜：{report['summary']['storyboard_count']}")
    print(f"   - 错误：{report['summary']['error_count']}")
    print(f"   - 警告：{report['summary']['warning_count']}")
    print(f"   - 信息：{report['summary']['info_count']}")
    for item in report["storyboards"]:
        if not item["issues"]:
            continue
        print(f"⚠️ chapter{item['chapter']}_page{item['page']}: {len(item['issues'])} 个问题")
        for issue in item["issues"][:8]:
            print(f"   - [{issue['code']}] {issue['message']}")
    print(f"📄 报告已保存：{output}")
    return 1 if report["summary"]["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
