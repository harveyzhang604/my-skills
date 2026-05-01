#!/usr/bin/env python3

import unittest
from pathlib import Path

from task_path_guard import SKILL_OUTPUT_ROOT, normalize_task_dir


class TaskPathGuardTest(unittest.TestCase):
    def test_relative_cd_generator_output_is_mapped_to_skill_output(self):
        task_dir = normalize_task_dir(
            "cd_generator_output/20260429_235435_bakery_adventure"
        )

        self.assertEqual(
            task_dir,
            SKILL_OUTPUT_ROOT / "20260429_235435_bakery_adventure",
        )

    def test_rejects_absolute_project_worktree_output(self):
        with self.assertRaises(ValueError):
            normalize_task_dir(
                "/Users/zhanghua/Documents/GitHub/ai-scene2talk/.claude/"
                "worktrees/distracted-cori-c45173/cd_generator_output/"
                "20260429_235435_bakery_adventure"
            )

    def test_accepts_skill_output_task_dir(self):
        task_dir = normalize_task_dir(
            "/Users/zhanghua/.claude/skills/cd-generator/output/"
            "20260429_235435_bakery_adventure"
        )

        self.assertEqual(
            task_dir,
            SKILL_OUTPUT_ROOT / "20260429_235435_bakery_adventure",
        )


if __name__ == "__main__":
    unittest.main()
