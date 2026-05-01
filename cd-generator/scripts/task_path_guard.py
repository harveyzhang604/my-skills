#!/usr/bin/env python3
"""Keep cd-generator task data inside the skill output directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILL_OUTPUT_ROOT = SKILL_ROOT / "output"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def normalize_task_dir(value: str | Path) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("task_dir is required")

    path = Path(raw).expanduser()
    output_root = SKILL_OUTPUT_ROOT.resolve()

    if not path.is_absolute():
        parts = path.parts
        if parts and parts[0] in {"cd_generator_output", "output"}:
            parts = parts[1:]
        if not parts:
            raise ValueError("task_dir must include a task folder name")
        return output_root.joinpath(*parts)

    resolved = path.resolve(strict=False)
    if resolved == output_root or _is_relative_to(resolved, output_root):
        return resolved

    raise ValueError(
        "cd-generator task_dir must be inside "
        f"{output_root}. Refusing project/worktree path: {resolved}"
    )


def require_task_dir(value: str | Path, *, must_exist: bool = True) -> Path:
    task_dir = normalize_task_dir(value)
    if must_exist and not task_dir.is_dir():
        raise ValueError(f"task_dir does not exist: {task_dir}")
    return task_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize a cd-generator task path.")
    parser.add_argument("task_dir")
    parser.add_argument("--no-must-exist", action="store_true")
    args = parser.parse_args()

    try:
        print(require_task_dir(args.task_dir, must_exist=not args.no_must_exist))
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
