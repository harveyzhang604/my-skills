#!/usr/bin/env python3
"""
统一图片生成服务：支持 ChatGPT Image 和 Gemini Image 两种方式。
当 ChatGPT 遇到限额时自动切换到 Gemini。

使用方式：
  python3 unified_image_service.py generate --prompt "..." --output "path.png"
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ChatGPT 限额错误模式
LIMIT_ERROR_PATTERNS = [
    "image generation limit reached",
    "you've reached your limit",
    "limit has been reached",
    "达到限制",
    "已达到限额",
]


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_command(args, timeout=None):
    """运行命令并返回退出码和输出"""
    proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def is_limit_error(output):
    """检查输出是否包含限额错误"""
    lowered = (output or "").lower()
    return any(pattern in lowered for pattern in LIMIT_ERROR_PATTERNS)


def generate_with_chatgpt(prompt, output_path, wait_schedule=None, repair_retries=2):
    """
    使用 ChatGPT Image 生成图片

    Args:
        prompt: 图片提示词
        output_path: 输出路径
        wait_schedule: 等待时间表，例如 [60, 60, 120]
        repair_retries: 修复重试次数

    Returns:
        dict: 包含 ok, status, error 等字段的结果
    """
    chatgpt_service = Path(__file__).parent.parent.parent / "chatgpt-image" / "scripts" / "opencli_image_service.py"

    if not chatgpt_service.exists():
        return {
            "ok": False,
            "status": "service_not_found",
            "error": f"ChatGPT image service not found at {chatgpt_service}",
            "provider": "chatgpt"
        }

    # 构建命令
    cmd = [
        "python3",
        str(chatgpt_service),
        "generate",
        "--prompt", prompt,
        "--output", output_path,
        "--repair-retries", str(repair_retries)
    ]

    if wait_schedule:
        cmd.extend(["--wait-schedule", ",".join(map(str, wait_schedule))])

    # 执行命令
    code, output = run_command(cmd, timeout=1200)  # 20分钟超时

    # 解析 JSON 输出
    try:
        result = json.loads(output)
        result["provider"] = "chatgpt"

        # 检查是否是限额错误
        if not result.get("ok"):
            error_text = result.get("error", "")
            if is_limit_error(error_text) or is_limit_error(output):
                result["is_limit_error"] = True

        return result
    except json.JSONDecodeError:
        # 检查原始输出是否包含限额错误
        is_limit = is_limit_error(output)
        return {
            "ok": False,
            "status": "parse_error",
            "error": "Failed to parse ChatGPT service output",
            "output_tail": output[-2000:],
            "provider": "chatgpt",
            "is_limit_error": is_limit
        }


def generate_with_gemini(prompt, output_path, timeout=300):
    """
    使用 Gemini Image 生成图片

    Args:
        prompt: 图片提示词
        output_path: 输出路径
        timeout: 超时时间（秒）

    Returns:
        dict: 包含 ok, status, error 等字段的结果
    """
    output_path = Path(output_path).expanduser().resolve(strict=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 使用 opencli gemini image 命令
    cmd = [
        "opencli",
        "gemini",
        "image",
        prompt,
        "--op", str(output_path.parent)
    ]

    started_at = time.time()
    code, output = run_command(cmd, timeout=timeout)
    elapsed = time.time() - started_at

    if code == 0:
        # Gemini 默认保存到 ~/Pictures/gemini/，需要找到最新的图片
        gemini_dir = Path.home() / "Pictures" / "gemini"

        if gemini_dir.exists():
            # 找到最新生成的图片
            candidates = []
            for path in gemini_dir.glob("*.png"):
                try:
                    stat = path.stat()
                    if stat.st_mtime >= started_at - 1:
                        candidates.append((stat.st_mtime, path))
                except OSError:
                    continue

            if candidates:
                latest = max(candidates)[1]
                # 移动到目标位置
                import shutil
                shutil.move(str(latest), str(output_path))

                return {
                    "ok": True,
                    "status": "completed",
                    "output_path": str(output_path),
                    "file_size": output_path.stat().st_size,
                    "completed_at": now_iso(),
                    "elapsed_seconds": round(elapsed, 1),
                    "provider": "gemini"
                }

        # 如果没找到图片，返回错误
        return {
            "ok": False,
            "status": "download_failed",
            "error": "Gemini command succeeded but no image was found",
            "output_tail": output[-1000:],
            "provider": "gemini"
        }

    # 命令失败
    return {
        "ok": False,
        "status": "failed",
        "error": f"Gemini command failed with exit code {code}",
        "output_tail": output[-2000:],
        "provider": "gemini"
    }


def generate_with_fallback(prompt, output_path, prefer_provider="chatgpt", wait_schedule=None, repair_retries=2, gemini_timeout=300):
    """
    使用备选方案生成图片：优先使用 ChatGPT，遇到限额时切换到 Gemini

    Args:
        prompt: 图片提示词
        output_path: 输出路径
        prefer_provider: 优先使用的提供商，"chatgpt" 或 "gemini"
        wait_schedule: ChatGPT 等待时间表
        repair_retries: ChatGPT 修复重试次数
        gemini_timeout: Gemini 超时时间

    Returns:
        dict: 包含 ok, status, provider, fallback_used 等字段的结果
    """
    result = {
        "ok": False,
        "status": "unknown",
        "provider": prefer_provider,
        "fallback_used": False,
        "attempts": []
    }

    # 第一次尝试：使用优先提供商
    if prefer_provider == "chatgpt":
        print(f"🔄 尝试使用 ChatGPT Image 生成图片...", file=sys.stderr)
        chatgpt_result = generate_with_chatgpt(prompt, output_path, wait_schedule, repair_retries)
        result["attempts"].append(chatgpt_result)

        if chatgpt_result.get("ok"):
            # 成功
            result.update(chatgpt_result)
            return result

        # 检查是否是限额错误
        if chatgpt_result.get("is_limit_error"):
            print(f"⚠️  ChatGPT Image 已达到限额，切换到 Gemini Image...", file=sys.stderr)
            result["fallback_used"] = True
            result["fallback_reason"] = "chatgpt_limit_reached"

            # 切换到 Gemini
            gemini_result = generate_with_gemini(prompt, output_path, gemini_timeout)
            result["attempts"].append(gemini_result)

            if gemini_result.get("ok"):
                result.update(gemini_result)
                return result
            else:
                # Gemini 也失败了
                result["status"] = "all_providers_failed"
                result["error"] = f"ChatGPT limit reached, Gemini also failed: {gemini_result.get('error')}"
                return result
        else:
            # 不是限额错误，直接返回 ChatGPT 的错误
            result.update(chatgpt_result)
            return result

    else:  # prefer_provider == "gemini"
        print(f"🔄 尝试使用 Gemini Image 生成图片...", file=sys.stderr)
        gemini_result = generate_with_gemini(prompt, output_path, gemini_timeout)
        result["attempts"].append(gemini_result)

        if gemini_result.get("ok"):
            result.update(gemini_result)
            return result
        else:
            # Gemini 失败，尝试 ChatGPT
            print(f"⚠️  Gemini Image 失败，切换到 ChatGPT Image...", file=sys.stderr)
            result["fallback_used"] = True
            result["fallback_reason"] = "gemini_failed"

            chatgpt_result = generate_with_chatgpt(prompt, output_path, wait_schedule, repair_retries)
            result["attempts"].append(chatgpt_result)

            if chatgpt_result.get("ok"):
                result.update(chatgpt_result)
                return result
            else:
                result["status"] = "all_providers_failed"
                result["error"] = f"Gemini failed, ChatGPT also failed: {chatgpt_result.get('error')}"
                return result


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def parse_wait_schedule(value):
    if not value:
        return [60, 60, 60, 60, 60, 120, 180]
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def main():
    parser = argparse.ArgumentParser(description="统一图片生成服务：ChatGPT + Gemini 备选")
    sub = parser.add_subparsers(dest="command", required=True)

    # generate 命令
    generate_parser = sub.add_parser("generate", help="生成图片（自动备选）")
    generate_parser.add_argument("--prompt", required=True, help="图片提示词")
    generate_parser.add_argument("--output", required=True, help="输出路径")
    generate_parser.add_argument("--provider", default="chatgpt", choices=["chatgpt", "gemini"], help="优先使用的提供商")
    generate_parser.add_argument("--wait-schedule", default="", help="ChatGPT 等待时间表，逗号分隔")
    generate_parser.add_argument("--repair-retries", type=int, default=2, help="ChatGPT 修复重试次数")
    generate_parser.add_argument("--gemini-timeout", type=int, default=300, help="Gemini 超时时间（秒）")

    # chatgpt 命令（直接使用 ChatGPT）
    chatgpt_parser = sub.add_parser("chatgpt", help="仅使用 ChatGPT Image")
    chatgpt_parser.add_argument("--prompt", required=True)
    chatgpt_parser.add_argument("--output", required=True)
    chatgpt_parser.add_argument("--wait-schedule", default="")
    chatgpt_parser.add_argument("--repair-retries", type=int, default=2)

    # gemini 命令（直接使用 Gemini）
    gemini_parser = sub.add_parser("gemini", help="仅使用 Gemini Image")
    gemini_parser.add_argument("--prompt", required=True)
    gemini_parser.add_argument("--output", required=True)
    gemini_parser.add_argument("--timeout", type=int, default=300)

    args = parser.parse_args()

    if args.command == "generate":
        result = generate_with_fallback(
            args.prompt,
            args.output,
            prefer_provider=args.provider,
            wait_schedule=parse_wait_schedule(args.wait_schedule),
            repair_retries=args.repair_retries,
            gemini_timeout=args.gemini_timeout
        )
        print_json(result)
        return 0 if result.get("ok") else 1

    elif args.command == "chatgpt":
        result = generate_with_chatgpt(
            args.prompt,
            args.output,
            wait_schedule=parse_wait_schedule(args.wait_schedule),
            repair_retries=args.repair_retries
        )
        print_json(result)
        return 0 if result.get("ok") else 1

    elif args.command == "gemini":
        result = generate_with_gemini(
            args.prompt,
            args.output,
            timeout=args.timeout
        )
        print_json(result)
        return 0 if result.get("ok") else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
