#!/usr/bin/env python3
"""
YouMind Image Generator Client
Direct API calls to YouMind for ChatGPT Image 2 generation.
Replaces the browser-based opencli approach.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple


def load_youmind_config():
    """Load YouMind API configuration from config file."""
    skill_dir = Path(__file__).resolve().parent.parent
    config_path = skill_dir / "config" / "youmind.env"

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

    # Also check environment variables
    return {
        "api_key": os.getenv("YKM_API_KEY") or os.getenv("YOUMAIND_API_KEY"),
        "base_url": (os.getenv("YKM_BASE_URL") or "https://api.youmind.ai/v1").rstrip("/"),
        "model": os.getenv("YKM_IMAGE_MODEL") or "gpt-image-1",
        "timeout": int(os.getenv("YKM_TIMEOUT") or "300"),
    }


class YouMindImageClient:
    """Client for YouMind Image Generation API (OpenAI-compatible)."""

    def __init__(self):
        self.config = load_youmind_config()
        if not self.config["api_key"]:
            raise RuntimeError(
                "YouMind API Key not found. Please set YKM_API_KEY in config/youmind.env"
            )

    def generate_image(
        self,
        prompt: str,
        size: str = "1024x1536",  # Vertical manga format
        quality: str = "high",
        n: int = 1,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Generate image using YouMind API.

        Args:
            prompt: Image generation prompt
            size: Image size (default 1024x1536 for vertical manga)
            quality: Image quality (low/medium/high)
            n: Number of images to generate

        Returns:
            Tuple of (success, image_url_or_path, error_message)
        """
        url = f"{self.config['base_url']}/images/generations"

        payload = {
            "model": self.config["model"],
            "prompt": prompt,
            "n": n,
            "size": size,
            "quality": quality,
        }

        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        try:
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(
                request, timeout=self.config["timeout"]
            ) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)

                if "data" in data and len(data["data"]) > 0:
                    image_url = data["data"][0].get("url")
                    if image_url:
                        return True, image_url, None

                return False, None, f"Unexpected response format: {raw}"

        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                error_data = json.loads(detail)
                error_msg = error_data.get("error", {}).get("message", detail)
            except:
                error_msg = detail
            return False, None, f"HTTP {exc.code}: {error_msg}"

        except urllib.error.URLError as exc:
            return False, None, f"Connection error: {exc}"

        except Exception as exc:
            return False, None, f"Unexpected error: {exc}"

    def download_image(self, image_url: str, output_path: str) -> Tuple[bool, Optional[str]]:
        """
        Download image from URL to local file.

        Args:
            image_url: URL of the image
            output_path: Local path to save the image

        Returns:
            Tuple of (success, error_message)
        """
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }

            request = urllib.request.Request(image_url, headers=headers, method="GET")

            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
                with open(output_path, "wb") as f:
                    f.write(data)

            return True, None

        except Exception as exc:
            return False, str(exc)


def main():
    """CLI entry point for image generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate image using YouMind API")
    parser.add_argument("prompt", help="Image generation prompt")
    parser.add_argument("--output", "-o", help="Output file path", required=True)
    parser.add_argument("--size", default="1024x1536", help="Image size")
    parser.add_argument("--quality", default="high", help="Image quality")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    client = YouMindImageClient()

    if args.verbose:
        print(f"Generating image with prompt: {args.prompt[:80]}...", file=sys.stderr)

    # Generate image
    success, image_url, error = client.generate_image(
        prompt=args.prompt,
        size=args.size,
        quality=args.quality,
    )

    if not success:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Image generated: {image_url}", file=sys.stderr)
        print(f"Downloading to: {args.output}", file=sys.stderr)

    # Download image
    success, error = client.download_image(image_url, args.output)

    if not success:
        print(f"ERROR downloading image: {error}", file=sys.stderr)
        sys.exit(1)

    print(args.output)


if __name__ == "__main__":
    main()
