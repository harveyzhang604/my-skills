#!/usr/bin/env python3
"""
Reusable OpenCLI image service for ChatGPT Image generation.

This module is intentionally task-agnostic. It knows how to submit one prompt,
inspect a ChatGPT conversation link, and download the generated PNG. Callers
such as cd-generator own batching, prompt QA, task paths, image_links.json, and
progress reporting.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ATTACH_ERROR_PATTERNS = (
    "cannot access a chrome-extension:// url of different extension",
    "detached while handling command",
    "attach failed",
)

STATUS_JS = r"""
(() => {
  const bodyText = document.body.innerText || '';
  if (bodyText.includes('I was unable to generate') ||
      bodyText.includes('encountered an error') ||
      bodyText.includes('抱歉')) {
    return 'ERROR';
  }

  let img = document.querySelector('img[src*="chatgpt.com/backend-api/"]');
  if (!img) img = document.querySelector('img[alt="Generated image"]');
  if (!img) img = document.querySelector('img[alt="generated image"]');
  if (!img) img = document.querySelector('img[src*="estuary/content"]');

  if (img && img.complete && img.naturalWidth > 0) {
    return 'READY:' + img.naturalWidth + 'x' + img.naturalHeight;
  }
  if (img) return 'LOADING';
  return 'PENDING';
})()
"""

DOWNLOAD_JS = r"""
(async () => {
  let img = document.querySelector('img[src*="chatgpt.com/backend-api/"]');
  if (!img) img = document.querySelector('img[alt="Generated image"]');
  if (!img) img = document.querySelector('img[alt="generated image"]');
  if (!img) img = document.querySelector('img[src*="estuary/content"]');
  if (!img) return 'NO_IMAGE';

  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  const dataUrl = canvas.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = 'chatgpt_image.png';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  return 'DOWNLOADED';
})()
"""


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_command(args, timeout=None):
    proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def parse_link(output):
    output = re.sub(r"\x1b\[[0-9;]*m", "", output or "")
    patterns = [
        r"link:\s*🔗?\s*(https://chatgpt\.com/[^\s<>'\"]+)",
        r"(https://chatgpt\.com/[^\s<>'\"]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            return match.group(1).strip().rstrip(").,;]}>\"'")
    return ""


def is_attach_error(output):
    lowered = (output or "").lower()
    return any(pattern in lowered for pattern in ATTACH_ERROR_PATTERNS)


def repair_browser():
    run_command(["opencli", "browser", "close"])
    run_command(["opencli", "doctor"])
    time.sleep(5)


def submit_prompt(prompt, repair_retries=2):
    attempts = []
    repaired = False
    max_attempts = max(1, repair_retries + 1)
    for index in range(max_attempts):
        code, output = run_command(["opencli", "chatgpt", "image", prompt, "--verbose"])
        attempts.append({"attempt": index + 1, "exit_code": code, "output_tail": output[-2000:]})
        link = parse_link(output)
        if link:
            warning = ""
            if code != 0 or is_attach_error(output):
                warning = "OpenCLI returned a warning/non-zero exit after creating a ChatGPT link"
            return {
                "ok": True,
                "status": "pending",
                "link": link,
                "warning": warning,
                "submit_exit_code": code,
                "submit_attempts": index + 1,
                "opencli_repaired": repaired,
                "attempts": attempts,
                "submitted_at": now_iso(),
            }
        if code != 0 and is_attach_error(output) and index < max_attempts - 1:
            repaired = True
            repair_browser()
            continue
        return {
            "ok": False,
            "status": "submit_failed",
            "link": "",
            "error": "OpenCLI did not return a ChatGPT link",
            "submit_exit_code": code,
            "submit_attempts": index + 1,
            "opencli_repaired": repaired,
            "attempts": attempts,
            "output_tail": output[-2000:],
            "submitted_at": now_iso(),
        }
    return {"ok": False, "status": "submit_failed", "error": "unreachable"}


def open_link(link, repair_retries=1, settle_seconds=5):
    for index in range(repair_retries + 1):
        code, output = run_command(["opencli", "browser", "open", link], timeout=30)
        if code == 0:
            time.sleep(settle_seconds)
            return True, output
        if is_attach_error(output) and index < repair_retries:
            repair_browser()
            continue
        return False, output
    return False, ""


def check_status(link, repair_retries=1):
    opened, output = open_link(link, repair_retries=repair_retries, settle_seconds=5)
    if not opened:
        return {"ok": False, "status": "PENDING", "error": output[-1000:]}
    for index in range(repair_retries + 1):
        code, result = run_command(["opencli", "browser", "eval", STATUS_JS], timeout=30)
        if code == 0:
            status = parse_status_eval_result(result)
            return {"ok": True, "status": status, "checked_at": now_iso()}
        if is_attach_error(result) and index < repair_retries:
            repair_browser()
            open_link(link, repair_retries=0, settle_seconds=5)
            continue
        return {"ok": False, "status": "PENDING", "error": result[-1000:], "checked_at": now_iso()}
    return {"ok": False, "status": "PENDING", "checked_at": now_iso()}


def parse_status_eval_result(result):
    text = (result or "").strip()
    for line in text.splitlines():
        candidate = line.strip().strip("\"'")
        if candidate.startswith("READY:") or candidate in {"ERROR", "LOADING", "PENDING"}:
            return candidate
    return "PENDING"


def latest_download_since(started_at):
    downloads = Path.home() / "Downloads"
    candidates = []
    for path in downloads.glob("*.png"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime >= started_at - 1:
            candidates.append((stat.st_mtime, path))
    return max(candidates)[1] if candidates else None


def download_image(link, output_path, repair_retries=1):
    output_path = Path(output_path).expanduser().resolve(strict=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    opened, output = open_link(link, repair_retries=repair_retries, settle_seconds=3)
    if not opened:
        return {"ok": False, "status": "download_failed", "error": output[-1000:]}

    started_at = time.time()
    for index in range(repair_retries + 1):
        code, result = run_command(["opencli", "browser", "eval", DOWNLOAD_JS], timeout=40)
        if code == 0 and "DOWNLOADED" in result:
            time.sleep(3)
            latest = latest_download_since(started_at)
            if not latest:
                return {"ok": False, "status": "download_failed", "error": "download command succeeded but no new PNG was found"}
            shutil.move(str(latest), str(output_path))
            return {
                "ok": True,
                "status": "completed",
                "output_path": str(output_path),
                "file_size": output_path.stat().st_size,
                "completed_at": now_iso(),
            }
        if is_attach_error(result) and index < repair_retries:
            repair_browser()
            open_link(link, repair_retries=0, settle_seconds=3)
            continue
        return {"ok": False, "status": "download_failed", "error": result[-1000:]}
    return {"ok": False, "status": "download_failed"}


def generate_and_wait(prompt, output_path, wait_schedule, repair_retries=2):
    submit = submit_prompt(prompt, repair_retries=repair_retries)
    if not submit.get("ok"):
        return submit
    link = submit["link"]
    last_status = None
    for wait_seconds in wait_schedule:
        time.sleep(wait_seconds)
        status = check_status(link, repair_retries=1)
        last_status = status
        if status.get("status", "").startswith("READY:"):
            downloaded = download_image(link, output_path, repair_retries=1)
            downloaded["link"] = link
            downloaded["submit"] = submit
            downloaded["last_status"] = status
            return downloaded
        if status.get("status") == "ERROR":
            return {"ok": False, "status": "failed", "link": link, "submit": submit, "last_status": status}
    return {"ok": False, "status": "timeout", "link": link, "submit": submit, "last_status": last_status}


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def parse_wait_schedule(value):
    if not value:
        return [60, 60, 60, 60, 60, 120, 180]
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def main():
    parser = argparse.ArgumentParser(description="Reusable ChatGPT Image OpenCLI service.")
    sub = parser.add_subparsers(dest="command", required=True)

    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("--prompt", required=True)
    submit_parser.add_argument("--repair-retries", type=int, default=2)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--link", required=True)
    status_parser.add_argument("--repair-retries", type=int, default=1)

    download_parser = sub.add_parser("download")
    download_parser.add_argument("--link", required=True)
    download_parser.add_argument("--output", required=True)
    download_parser.add_argument("--repair-retries", type=int, default=1)

    generate_parser = sub.add_parser("generate")
    generate_parser.add_argument("--prompt", required=True)
    generate_parser.add_argument("--output", required=True)
    generate_parser.add_argument("--wait-schedule", default="")
    generate_parser.add_argument("--repair-retries", type=int, default=2)

    args = parser.parse_args()
    if args.command == "submit":
        print_json(submit_prompt(args.prompt, repair_retries=args.repair_retries))
    elif args.command == "status":
        print_json(check_status(args.link, repair_retries=args.repair_retries))
    elif args.command == "download":
        print_json(download_image(args.link, args.output, repair_retries=args.repair_retries))
    elif args.command == "generate":
        print_json(generate_and_wait(
            args.prompt,
            args.output,
            parse_wait_schedule(args.wait_schedule),
            repair_retries=args.repair_retries,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
