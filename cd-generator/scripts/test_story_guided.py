#!/usr/bin/env python3

import json
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from conversation_director import ConversationDirector
from generate_conversation_missions import generate_mission_for_page
from llm_json_client import parse_json_content


class FakeLLMClient:
    def __init__(self):
        self.requests = []

    def request_json(self, task, payload):
        self.requests.append((task, payload))
        if task == "generate_conversation_mission":
            return {
                "characters": ["Lin Xiao", "Alex Chen"],
                "user_role": "Lin Xiao",
                "ai_role": "Alex Chen",
                "mission_summary": "在设计部场景中练习自由对话。",
                "must_hit_beats": [
                    {
                        "id": "beat_1_react_to_scene",
                        "label": "React to the current situation",
                        "label_zh": "回应当前场景",
                        "intent": "react_to_scene",
                        "acceptance_criteria": "Learner comments naturally on the office size or first impression.",
                        "example_phrases": ["Wow, this is much bigger than I imagined!"],
                        "source_dialogue_indices": [1],
                    }
                ],
                "target_phrases": ["Wow, this is much bigger than I imagined!"],
                "coach_note": "Accept natural paraphrases, not exact lines.",
            }
        if task == "analyze_story_guided_turn":
            current_label = payload["current_beat"]["label"]
            completed = (
                "arriving early" in current_label.lower()
                or "nervous" in current_label.lower()
                or "feeling" in current_label.lower()
            )
            return {
                "user_intent": "semantic_completion",
                "beat_completed": completed,
                "off_track": False,
                "needs_hint": False,
                "guidance": "continue" if completed else "encourage",
                "confidence": 0.92,
                "reason": "The learner completed the beat semantically.",
            }
        raise AssertionError(f"unexpected task: {task}")


class FailingLLMClient:
    def request_json(self, task, payload):
        raise RuntimeError("simulated model outage")


class StoryGuidedMissionTest(unittest.TestCase):
    def test_mission_uses_declared_character_roles_and_ignores_stage_speakers(self):
        page = {
            "scene_location": "Design Department",
            "dialogues": [
                {
                    "speaker": "林晓",
                    "speaker_en": "Lin Xiao",
                    "text_en": "Wow, this is much bigger than I imagined!",
                    "text_zh": "哇，这里比我想象的大多了！",
                },
                {
                    "speaker": "Phone",
                    "speaker_en": "Phone",
                    "text_en": "(Phone ringing)",
                    "text_zh": "（电话响起）",
                },
                {
                    "speaker": "Alex",
                    "speaker_en": "Alex Chen",
                    "text_en": "This is the design department.",
                    "text_zh": "这里是设计部。",
                },
            ],
        }
        story_characters = [
            {"name": "林晓", "name_en": "Lin Xiao", "role": "protagonist"},
            {"name": "Alex Chen", "name_en": "Alex Chen", "role": "supporting"},
        ]

        mission = generate_mission_for_page(
            page,
            chapter_num=1,
            page_num=2,
            story_characters=story_characters,
            language_level="B2",
            llm_client=FakeLLMClient(),
        )

        self.assertEqual(mission["user_role"], "Lin Xiao")
        self.assertEqual(mission["ai_role"], "Alex Chen")
        self.assertNotIn("Phone", mission["characters"])
        self.assertEqual(mission["language_level"], "B2")
        self.assertTrue(
            all("Phone ringing" not in phrase for phrase in mission["target_phrases"])
        )
        self.assertTrue(all(isinstance(beat, dict) for beat in mission["must_hit_beats"]))
        self.assertEqual(mission["director_mode"], "llm_semantic_v1")
        self.assertEqual(mission["must_hit_beats"][0]["intent"], "react_to_scene")

    def test_director_completes_arriving_early_and_feeling_beats(self):
        mission = {
            "must_hit_beats": [
                {
                    "id": "arrive_early",
                    "label": "Explain arriving early",
                    "intent": "explain_arrival",
                    "acceptance_criteria": "Learner explains they came early or cared about being on time.",
                },
                {
                    "id": "express_feeling",
                    "label": "Express nervousness",
                    "intent": "express_feeling",
                    "acceptance_criteria": "Learner shares honest feelings about the first day.",
                },
            ]
        }
        director = ConversationDirector(mission, llm_client=FakeLLMClient())

        first = director.analyze_user_input(
            "I arrived 15 minutes early because I didn't want to be late."
        )
        second = director.analyze_user_input(
            "To be honest, I'm a bit nervous about my first day."
        )

        self.assertTrue(first["beat_completed"])
        self.assertEqual(first["guidance"], "continue")
        self.assertTrue(second["beat_completed"])
        self.assertEqual(director.get_progress_summary()["progress_percentage"], 100)

    def test_director_uses_llm_instead_of_keyword_fallback(self):
        mission = {
            "must_hit_beats": [
                {
                    "id": "react_scene",
                    "label": "React to the current situation",
                    "intent": "react_to_scene",
                    "acceptance_criteria": "Learner comments naturally on the current scene.",
                }
            ]
        }
        director = ConversationDirector(mission, llm_client=FakeLLMClient())

        analysis = director.analyze_user_input("The space feels different from what I expected.")

        self.assertEqual(analysis["user_intent"], "semantic_completion")
        self.assertFalse(analysis["beat_completed"])

    def test_director_model_failure_uses_safe_non_completion(self):
        mission = {
            "must_hit_beats": [
                {
                    "id": "ask_question",
                    "label": "Ask a relevant question",
                    "intent": "ask_question",
                    "acceptance_criteria": "Learner asks a relevant question.",
                }
            ]
        }
        director = ConversationDirector(mission, llm_client=FailingLLMClient())

        analysis = director.analyze_user_input("Could you show me where to start?")

        self.assertFalse(analysis["beat_completed"])
        self.assertEqual(analysis["guidance"], "encourage")
        self.assertTrue(analysis["llm_error"])

    def test_parse_json_content_handles_claude_code_fence(self):
        parsed = parse_json_content('```json\n{"ok": true}\n```')

        self.assertEqual(parsed, {"ok": True})

    def test_parse_json_content_extracts_json_from_text(self):
        parsed = parse_json_content('Here is the JSON:\\n{"ok": true}\\nDone.')

        self.assertEqual(parsed, {"ok": True})

    def test_mission_deduplicates_overlapping_intents(self):
        class DuplicateBeatLLM(FakeLLMClient):
            def request_json(self, task, payload):
                result = super().request_json(task, payload)
                if task == "generate_conversation_mission":
                    result["must_hit_beats"].append({
                        "id": "beat_duplicate",
                        "label": "Show excitement to learn",
                        "label_zh": "表达学习热情",
                        "intent": "react_to_scene",
                        "acceptance_criteria": "Learner also says they are eager to keep going.",
                        "example_phrases": ["I want to learn more."],
                        "source_dialogue_indices": [3],
                    })
                return result

        mission = generate_mission_for_page(
            {"scene_location": "Office", "dialogues": []},
            chapter_num=1,
            page_num=1,
            llm_client=DuplicateBeatLLM(),
        )

        intents = [beat["intent"] for beat in mission["must_hit_beats"]]
        self.assertEqual(len(intents), len(set(intents)))

    def test_mission_sorts_beats_by_source_dialogue_order(self):
        class OutOfOrderLLM(FakeLLMClient):
            def request_json(self, task, payload):
                result = super().request_json(task, payload)
                if task == "generate_conversation_mission":
                    result["must_hit_beats"] = [
                        {
                            "id": "later",
                            "label": "Later beat",
                            "label_zh": "后面的节点",
                            "intent": "show_willingness",
                            "acceptance_criteria": "Learner shows willingness later.",
                            "example_phrases": [],
                            "source_dialogue_indices": [8],
                        },
                        {
                            "id": "earlier",
                            "label": "Earlier beat",
                            "label_zh": "前面的节点",
                            "intent": "greet_introduce",
                            "acceptance_criteria": "Learner greets earlier.",
                            "example_phrases": [],
                            "source_dialogue_indices": [2],
                        },
                    ]
                return result

        mission = generate_mission_for_page(
            {"scene_location": "Office", "dialogues": []},
            chapter_num=1,
            page_num=1,
            llm_client=OutOfOrderLLM(),
        )

        self.assertEqual(mission["must_hit_beats"][0]["intent"], "greet_introduce")

    def test_mission_prioritizes_greeting_before_private_feeling(self):
        class GreetingAfterSelfTalkLLM(FakeLLMClient):
            def request_json(self, task, payload):
                result = super().request_json(task, payload)
                if task == "generate_conversation_mission":
                    result["must_hit_beats"] = [
                        {
                            "id": "self_talk",
                            "label": "Share first-day nerves",
                            "label_zh": "表达第一天紧张",
                            "intent": "express_feeling",
                            "acceptance_criteria": "Learner shares nervousness.",
                            "example_phrases": [],
                            "source_dialogue_indices": [1],
                        },
                        {
                            "id": "greeting",
                            "label": "Greet your mentor",
                            "label_zh": "问候导师",
                            "intent": "greet_introduce",
                            "acceptance_criteria": "Learner greets the mentor.",
                            "example_phrases": [],
                            "source_dialogue_indices": [4],
                        },
                    ]
                return result

        mission = generate_mission_for_page(
            {"scene_location": "Office", "dialogues": []},
            chapter_num=1,
            page_num=1,
            llm_client=GreetingAfterSelfTalkLLM(),
        )

        self.assertEqual(mission["must_hit_beats"][0]["intent"], "greet_introduce")

    def test_mission_preserves_raw_intent_when_model_returns_unknown_intent(self):
        class UnknownIntentLLM(FakeLLMClient):
            def request_json(self, task, payload):
                result = super().request_json(task, payload)
                if task == "generate_conversation_mission":
                    result["must_hit_beats"][0]["intent"] = "build rapport by being authentic"
                return result

        mission = generate_mission_for_page(
            {"scene_location": "Office", "dialogues": []},
            chapter_num=1,
            page_num=1,
            llm_client=UnknownIntentLLM(),
        )

        beat = mission["must_hit_beats"][0]
        self.assertEqual(beat["intent"], "other_goal")
        self.assertEqual(beat["model_intent_raw"], "build rapport by being authentic")


if __name__ == "__main__":
    unittest.main()
