#!/usr/bin/env python3
"""Submit cd-generator prompts to chatgpt-image service at a fixed interval."""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from task_path_guard import require_task_dir

CHATGPT_IMAGE_SERVICE = Path("/Users/zhanghua/.claude/skills/chatgpt-image/scripts/opencli_image_service.py")


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def output_tail(output, limit=2000):
    return (output or "")[-limit:]


def call_chatgpt_image_submit(prompt, repair_retries=2):
    if not CHATGPT_IMAGE_SERVICE.exists():
        raise RuntimeError(f"missing chatgpt-image service: {CHATGPT_IMAGE_SERVICE}")
    proc = subprocess.run(
        [
            sys.executable,
            str(CHATGPT_IMAGE_SERVICE),
            "submit",
            "--prompt",
            prompt,
            "--repair-retries",
            str(repair_retries),
        ],
        text=True,
        capture_output=True,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {
            "ok": False,
            "status": "submit_failed",
            "link": "",
            "error": "chatgpt-image service returned non-JSON output",
            "submit_exit_code": proc.returncode,
            "submit_attempts": 1,
            "opencli_repaired": False,
        }
    payload.setdefault("submit_exit_code", proc.returncode)
    payload.setdefault("submit_attempts", 1)
    payload.setdefault("opencli_repaired", False)
    payload["_service_output"] = output
    payload["_service_returncode"] = proc.returncode
    return payload


def existing_record(data, chapter, page):
    for item in data.get("images", []):
        if int(item.get("chapter", 0) or 0) == chapter and int(item.get("page", 0) or 0) == page:
            return item
    return None


def upsert_record(data, record):
    images = [
        item for item in data.get("images", [])
        if not (
            int(item.get("chapter", 0) or 0) == record["chapter"]
            and int(item.get("page", 0) or 0) == record["page"]
        )
    ]
    images.append(record)
    images.sort(key=lambda item: (int(item.get("chapter", 0) or 0), int(item.get("page", 0) or 0)))
    data["images"] = images


def submit_prompt(task_dir, page, force=False, repair_retries=2):
    chapter = 1
    prompt_path = task_dir / "prompts" / f"chapter{chapter}_page{page}.txt"
    if not prompt_path.exists():
        raise RuntimeError(f"missing prompt: {prompt_path}")
    prompt = prompt_path.read_text(encoding="utf-8").strip()

    links_path = task_dir / "image_links.json"
    data = load_json(links_path, {"images": []})
    existing = existing_record(data, chapter, page)
    image_path = task_dir / "images" / f"chapter{chapter}_page{page}.png"
    if image_path.exists() and image_path.stat().st_size > 0 and not force:
        if existing:
            existing["status"] = "completed"
            existing["updated_at"] = now_iso()
        else:
            upsert_record(data, {
                "chapter": chapter,
                "page": page,
                "filename": image_path.name,
                "link": "",
                "prompt": prompt,
                "status": "completed",
                "retry_count": 0,
                "generation_mode": "local_image_existing",
                "updated_at": now_iso(),
            })
        save_json(links_path, data)
        return {
            "page": page,
            "status": "skipped",
            "link": existing.get("link", "") if existing else "",
            "message": "local image already exists",
        }

    if existing and existing.get("link") and existing.get("status") in {"pending", "completed"} and not force:
        return {
            "page": page,
            "status": "skipped",
            "link": existing.get("link", ""),
            "message": "existing pending/completed link",
        }

    log_path = task_dir / f"image_generation_page{page}_submit.log"
    started_at = now_iso()
    service_result = call_chatgpt_image_submit(prompt, repair_retries=repair_retries)
    output = service_result.get("_service_output", "")
    log_path.write_text(output, encoding="utf-8", errors="replace")
    link = service_result.get("link", "")
    status = service_result.get("status") or ("pending" if link else "submit_failed")
    record = {
        "chapter": chapter,
        "page": page,
        "filename": f"chapter{chapter}_page{page}.png",
        "link": link,
        "prompt": prompt,
        "status": status,
        "retry_count": 0,
        "submitted_at": started_at,
        "generation_mode": "chatgpt_image_service_opencli_rate_limited",
        "submit_exit_code": int(service_result.get("submit_exit_code") or service_result.get("_service_returncode") or 0),
        "submit_attempts": int(service_result.get("submit_attempts") or 1),
        "submit_log": log_path.name,
        "submit_warning": service_result.get("warning", ""),
        "opencli_repaired": bool(service_result.get("opencli_repaired")),
        "last_submit_error": service_result.get("error", ""),
        "submit_output_tail": output_tail(output),
        "updated_at": now_iso(),
    }
    if not link:
        record["error"] = output_tail(output)
    upsert_record(data, record)
    save_json(links_path, data)
    return {
        "page": page,
        "status": status,
        "link": link,
        "exit_code": record["submit_exit_code"],
        "attempts": record["submit_attempts"],
        "warning": record["submit_warning"],
        "opencli_repaired": record["opencli_repaired"],
        "error": record["last_submit_error"],
    }


def update_progress(task_dir, submitted, total, status):
    progress_path = task_dir / "data" / "progress.json"
    if not progress_path.exists():
        return
    progress = load_json(progress_path, {})
    progress.setdefault("status", {})
    progress["status"]["images"] = status
    progress["image_submission_summary"] = {
        "submitted_or_existing": submitted,
        "total": total,
        "interval_seconds": 120,
        "mode": "chatgpt_image_service_opencli_rate_limited",
        "updated_at": now_iso(),
    }
    save_json(progress_path, progress)


def main():
    parser = argparse.ArgumentParser(description="Submit OpenCLI image prompts one by one.")
    parser.add_argument("task_dir")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=24)
    parser.add_argument("--interval", type=int, default=120)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--repair-retries", type=int, default=2)
    parser.add_argument("--max-submit-failures", type=int, default=3)
    parser.add_argument("--stop-on-first-failure", action="store_true")
    args = parser.parse_args()

    task_dir = require_task_dir(args.task_dir)
    pages = list(range(args.start, args.end + 1))
    submitted = 0
    consecutive_failures = 0
    stopped = False
    for index, page in enumerate(pages, start=1):
        print(f"[{now_iso()}] submitting page {page}/{args.end}", flush=True)
        try:
            result = submit_prompt(
                task_dir,
                page,
                force=args.force,
                repair_retries=args.repair_retries,
            )
            if result["status"] in {"pending", "skipped"}:
                submitted += 1
                consecutive_failures = 0
            else:
                consecutive_failures += 1
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as exc:
            consecutive_failures += 1
            print(json.dumps({"page": page, "status": "error", "error": str(exc)}, ensure_ascii=False), flush=True)
        update_progress(task_dir, submitted, len(pages), "submitting")
        if consecutive_failures:
            should_stop = args.stop_on_first_failure or consecutive_failures >= args.max_submit_failures
            if should_stop:
                print(
                    json.dumps(
                        {
                            "status": "stopped",
                            "reason": "too many consecutive submit failures",
                            "consecutive_failures": consecutive_failures,
                            "max_submit_failures": args.max_submit_failures,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                update_progress(task_dir, submitted, len(pages), "submit_stopped")
                stopped = True
                break
        if index < len(pages):
            print(f"[{now_iso()}] waiting {args.interval} seconds before next image", flush=True)
            time.sleep(args.interval)
    if not stopped:
        update_progress(task_dir, submitted, len(pages), "submitted")
    print(f"[{now_iso()}] done submitted_or_existing={submitted}/{len(pages)} stopped={stopped}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
