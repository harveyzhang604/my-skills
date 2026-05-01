#!/usr/bin/env python3
"""
Conversation Director - 隐藏导演系统
使用大模型语义判断剧情节点完成度，不做关键词匹配。
"""

import json
import logging
from typing import Dict, Optional

try:
    from llm_json_client import OpenAICompatibleJSONClient
except ImportError:
    from .llm_json_client import OpenAICompatibleJSONClient

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ConversationDirector:
    """对话导演 - 追踪剧情进度并生成引导策略"""

    def __init__(self, mission: Dict, llm_client=None):
        self.mission = mission
        self.llm_client = llm_client
        self.completed_beats = []
        self.current_beat_index = 0
        self.conversation_history = []

    def analyze_user_input(self, user_text: str, user_text_zh: Optional[str] = None) -> Dict:
        beats = self.mission.get("must_hit_beats", [])

        if self.current_beat_index >= len(beats):
            return {
                "current_beat": "Mission completed",
                "user_intent": "Conversation complete",
                "beat_completed": True,
                "next_beat": None,
                "needs_hint": False,
                "off_track": False,
                "guidance": "continue",
                "confidence": 1.0,
                "reason": "任务已完成。",
            }

        current_beat = beats[self.current_beat_index]
        current_label = self._beat_label(current_beat)
        model_result = self._analyze_with_llm(user_text, user_text_zh, current_beat)

        beat_completed = bool(model_result.get("beat_completed"))
        if beat_completed:
            self.completed_beats.append(current_beat)
            self.current_beat_index += 1

        self.conversation_history.append({
            "role": "learner",
            "user_text": user_text,
            "user_text_zh": user_text_zh,
            "beat": current_label,
            "completed": beat_completed,
            "model_reason": model_result.get("reason", ""),
        })

        next_beat = beats[self.current_beat_index] if self.current_beat_index < len(beats) else None
        guidance = self._normalize_guidance(model_result.get("guidance"), beat_completed)

        return {
            "current_beat": current_label,
            "user_intent": str(model_result.get("user_intent") or "semantic_response"),
            "beat_completed": beat_completed,
            "next_beat": self._beat_label(next_beat) if next_beat else None,
            "needs_hint": bool(model_result.get("needs_hint")),
            "off_track": False if beat_completed else bool(model_result.get("off_track")),
            "guidance": guidance,
            "progress": f"{len(self.completed_beats)}/{len(beats)}",
            "confidence": float(model_result.get("confidence") or 0),
            "reason": str(model_result.get("reason") or ""),
            "llm_error": str(model_result.get("llm_error") or ""),
        }

    def _client(self):
        if self.llm_client:
            return self.llm_client
        self.llm_client = OpenAICompatibleJSONClient()
        return self.llm_client

    def _analyze_with_llm(self, user_text: str, user_text_zh: Optional[str], current_beat) -> Dict:
        payload = {
            "mission": {
                "scene": self.mission.get("scene", ""),
                "user_role": self.mission.get("user_role", ""),
                "ai_role": self.mission.get("ai_role", ""),
                "mission_summary": self.mission.get("mission_summary", ""),
                "language_level": self.mission.get("language_level", ""),
                "success_rule": self.mission.get("success_rule", ""),
            },
            "all_beats": self.mission.get("must_hit_beats", []),
            "current_beat_index": self.current_beat_index,
            "current_beat": current_beat,
            "completed_beats": [self._beat_label(beat) for beat in self.completed_beats],
            "recent_history": self.conversation_history[-6:],
            "same_beat_attempts": self._same_beat_attempts(),
            "learner_utterance": user_text,
            "learner_utterance_zh": user_text_zh or "",
        }
        try:
            result = self._client().request_json("analyze_story_guided_turn", payload)
            if not isinstance(result, dict):
                raise RuntimeError("模型返回的 director 分析结果不是 JSON object。")
            return result
        except Exception as exc:
            logger.warning("LLM director analysis failed: %s", exc)
            return self._safe_non_completion_analysis(exc)

    def _safe_non_completion_analysis(self, exc: Exception) -> Dict:
        attempts = self._same_beat_attempts()
        return {
            "user_intent": "llm_unavailable",
            "beat_completed": False,
            "off_track": False,
            "needs_hint": attempts >= 2,
            "guidance": "hint" if attempts >= 2 else "encourage",
            "confidence": 0,
            "reason": f"模型判断暂时失败，未自动判定完成：{exc}",
            "llm_error": str(exc),
        }

    def _same_beat_attempts(self) -> int:
        count = 0
        for item in reversed(self.conversation_history):
            if item.get("completed"):
                break
            count += 1
        return count

    def _beat_label(self, beat) -> str:
        if isinstance(beat, dict):
            return beat.get("label") or beat.get("id") or "Continue the scene"
        return str(beat or "Continue the scene")

    def _normalize_guidance(self, guidance, beat_completed: bool) -> str:
        allowed = {"continue", "redirect", "hint", "encourage"}
        if beat_completed:
            return "continue"
        if guidance in allowed:
            return guidance
        return "encourage"

    def get_ai_prompt_guidance(self, analysis: Dict) -> str:
        guidance = analysis["guidance"]
        current_beat = analysis["current_beat"]
        next_beat = analysis.get("next_beat")
        reason = analysis.get("reason", "")

        prompts = {
            "continue": (
                f"The learner completed '{current_beat}'. "
                + (
                    f"Now naturally transition to '{next_beat}'. Keep your response under 20 words and end with a question."
                    if next_beat
                    else "Briefly celebrate and close this scene naturally. Keep your response under 20 words."
                )
            ),
            "redirect": f"The learner is off track for '{current_beat}'. Briefly acknowledge them, then guide back. Director reason: {reason}",
            "hint": f"The learner seems stuck on '{current_beat}'. Give a gentle hint without revealing the exact answer. Director reason: {reason}",
            "encourage": f"The learner is working on '{current_beat}'. Respond naturally and encourage them to continue. Keep it conversational.",
        }
        return prompts.get(guidance, prompts["encourage"])

    def get_progress_summary(self) -> Dict:
        beats = self.mission.get("must_hit_beats", [])
        return {
            "total_beats": len(beats),
            "completed_beats": len(self.completed_beats),
            "current_beat": self._beat_label(beats[self.current_beat_index]) if self.current_beat_index < len(beats) else None,
            "progress_percentage": int(len(self.completed_beats) / len(beats) * 100) if beats else 100,
            "completed": self.current_beat_index >= len(beats),
        }


if __name__ == "__main__":
    mission = {
        "page": 1,
        "scene": "第一天到设计公司报到",
        "must_hit_beats": [
            {
                "label": "Greet and introduce",
                "intent": "greet_introduce",
                "acceptance_criteria": "Learner greets the mentor and introduces themself.",
            },
            {
                "label": "Explain arriving early",
                "intent": "explain_arrival",
                "acceptance_criteria": "Learner explains they arrived early or cared about not being late.",
            },
        ],
    }

    director = ConversationDirector(mission)
    for user_input in [
        "Hi Alex, I'm Lin Xiao. Nice to meet you!",
        "I came ahead of time because I wanted to be prepared.",
    ]:
        analysis = director.analyze_user_input(user_input)
        print(f"\n用户: {user_input}")
        print(f"分析: {json.dumps(analysis, indent=2, ensure_ascii=False)}")
        print(f"AI 引导: {director.get_ai_prompt_guidance(analysis)}")
