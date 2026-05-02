#!/usr/bin/env python3
"""
Layered quality gate for cd-generator.

Default mode is lightweight and local:
- oral-practice fit audit for scripts
- storyboard/image-prompt audit
- optional generated-image file audit when images exist or --images is passed

Deep LLM semantic validation remains available through validate_content.sh but is
not the default for iterative work.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from audit_oral_practice_fit import audit_task
from audit_generated_images import audit_image, expected_pages, link_records
from audit_storyboards import audit_storyboard, save_json


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_deep_validation(task_dir):
    script = Path(__file__).resolve().parent / "validate_content.sh"
    result = subprocess.run(
        ["bash", str(script), str(task_dir)],
        text=True,
        capture_output=True,
        timeout=900,
    )
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def audit_storyboards_for_task(task_dir, chapter=None):
    storyboards_dir = Path(task_dir) / "storyboards"
    files = sorted(storyboards_dir.glob("chapter*_page*.json"))
    if chapter is not None:
        files = [path for path in files if path.name.startswith(f"chapter{chapter}_page")]
    items = [audit_storyboard(path) for path in files]
    summary = {
        "storyboard_count": len(items),
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
    }
    for item in items:
        for issue in item["issues"]:
            summary[f"{issue['severity']}_count"] += 1
    return {"summary": summary, "storyboards": items}


def audit_images_for_task(task_dir, chapter=None, pages=None):
    task_path = Path(task_dir)
    image_pages = expected_pages(task_path, chapter)
    if pages:
        wanted = set(pages)
        image_pages = [(ch, page) for ch, page in image_pages if page in wanted]
    records = link_records(task_path)
    items = [audit_image(task_path, ch, page, records) for ch, page in image_pages]
    summary = {
        "expected_count": len(items),
        "existing_count": sum(1 for item in items if item["exists"]),
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
    }
    for item in items:
        for issue in item["issues"]:
            summary[f"{issue['severity']}_count"] += 1
    return {"summary": summary, "images": items}


def has_any_images(task_dir):
    images_dir = Path(task_dir) / "images"
    return any(images_dir.glob("chapter*_page*.png")) if images_dir.exists() else False


def should_run_deep(oral_report, storyboard_report):
    oral_summary = oral_report["summary"]
    storyboard_summary = storyboard_report["summary"]
    return (
        oral_summary["error_count"] > 0
        or storyboard_summary["error_count"] > 0
        or oral_summary["warning_count"] > 5
        or storyboard_summary["warning_count"] > 5
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Run layered cd-generator quality checks.")
    parser.add_argument("task_dir")
    parser.add_argument("--chapters", nargs="*", type=int)
    parser.add_argument("--chapter", type=int, help="Shortcut for a single chapter.")
    parser.add_argument("--images", action="store_true", help="Run generated-image file audit even if images are incomplete.")
    parser.add_argument("--deep", action="store_true", help="Also run full LLM semantic validation.")
    parser.add_argument("--auto-deep", action="store_true", help="Run deep validation only when lightweight checks show risk.")
    return parser.parse_args()


def main():
    args = parse_args()
    task_dir = Path(args.task_dir)
    chapters = args.chapters
    if args.chapter is not None:
        chapters = [args.chapter]

    oral_report = audit_task(task_dir, chapters)
    storyboard_chapter = chapters[0] if chapters and len(chapters) == 1 else None
    storyboard_report = audit_storyboards_for_task(task_dir, storyboard_chapter)
    image_report = None
    if args.images or has_any_images(task_dir):
        image_report = audit_images_for_task(task_dir, storyboard_chapter)

    report = {
        "checked_at": now_iso(),
        "task_dir": str(task_dir),
        "scope": {"chapters": chapters},
        "layers": {
            "oral_practice": oral_report,
            "storyboards": storyboard_report,
            "images": image_report,
        },
        "deep_validation": None,
        "summary": {
            "error_count": oral_report["summary"]["error_count"] + storyboard_report["summary"]["error_count"],
            "warning_count": oral_report["summary"]["warning_count"] + storyboard_report["summary"]["warning_count"],
            "info_count": oral_report["summary"].get("info_count", 0) + storyboard_report["summary"]["info_count"],
        },
    }

    run_deep = args.deep or (args.auto_deep and should_run_deep(oral_report, storyboard_report))
    if run_deep:
        report["deep_validation"] = run_deep_validation(task_dir)
        if report["deep_validation"]["exit_code"] != 0:
            report["summary"]["warning_count"] += 1

    output = task_dir / "quality" / "quality_gate_report.json"
    save_json(output, report)

    print("🧪 分层质检")
    print(f"   - 口语审查：error {oral_report['summary']['error_count']} / warning {oral_report['summary']['warning_count']}")
    print(f"   - 分镜审查：error {storyboard_report['summary']['error_count']} / warning {storyboard_report['summary']['warning_count']}")
    if report["deep_validation"]:
        print(f"   - 深审：exit {report['deep_validation']['exit_code']}")
    else:
        print("   - 深审：跳过")
    if image_report:
        print(
            "   - 图片审查："
            f"existing {image_report['summary']['existing_count']}/{image_report['summary']['expected_count']} / "
            f"error {image_report['summary']['error_count']} / "
            f"warning {image_report['summary']['warning_count']}"
        )
    print(f"   - 报告：{output}")

    return 1 if report["summary"]["error_count"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
