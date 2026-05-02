#!/usr/bin/env python3
"""
Small OpenAI-compatible JSON client for cd-generator scripts.

Semantic decisions in this skill must go through a model. The scripts accept
an injected fake client in tests; real runs use an OpenAI-compatible endpoint.
"""

import json
import os
import re
from pathlib import Path
import urllib.error
import urllib.request


TASK_PROMPTS = {
    "generate_conversation_mission": """You create Story-Guided Free Talk metadata for an English speaking comic page.

Return JSON only with:
- characters: string[]
- user_role: string
- ai_role: string
- mission_summary: Chinese string
- must_hit_beats: 3-5 objects. Each object has id, label, label_zh, intent, acceptance_criteria, example_phrases, source_dialogue_indices.
- target_phrases: 3-6 English learner phrases from the user role only
- coach_note: Chinese string

Rules:
- Do not use stage/system speakers such as Phone, Notification, Narrator, SFX as user_role or ai_role.
- Prefer the protagonist as user_role.
- Do not force exact script lines. Beats should describe semantic goals.
- Make each beat useful for free speaking practice, not keyword matching.
- Avoid duplicate or overlapping beats. Merge similar goals such as commitment, willingness, and eagerness into one beat.
- Beats are for live conversation with the AI role. Do not make private self-talk or stage directions mandatory beats.
- If the page includes a greeting/introduction with the AI role, put that beat before emotional disclosure or deeper story beats.
- Keep labels in English and label_zh in Chinese.
- intent must be one of: greet_introduce, react_to_scene, ask_question, express_feeling, explain_reason, explain_work, offer_help, accept_feedback, request_clarification, negotiate_time, show_gratitude, show_willingness, summarize_lesson, present_result.""",

    "analyze_story_guided_turn": """You are a hidden conversation director for Story-Guided Free Talk.

Judge the learner's latest English utterance semantically against the current story beat.
Return JSON only with:
- user_intent: short English phrase
- beat_completed: boolean
- off_track: boolean
- needs_hint: boolean
- guidance: one of continue, redirect, hint, encourage
- confidence: number from 0 to 1
- reason: short Chinese explanation

Rules:
- Accept paraphrases and imperfect learner English if the communicative goal is met.
- Do not require exact words from examples.
- Mark off_track only when the learner is clearly outside the scene/task.
- Use recent history and same_beat_attempts to decide needs_hint.
- If beat_completed is true, guidance should usually be continue.""",

    "audit_content_page": """You audit one comic page for Scene2Talk English speaking practice quality.

Return JSON only with:
- issues: array of objects with severity(error|warning|info), code, message, suggestion
- oral_fit_score: number from 0 to 1
- translation_fit_score: number from 0 to 1
- level_fit: one of too_easy, ok, too_hard
- role_consistency: one of ok, suspicious

Audit semantically:
- English should be natural spoken English for oral practice, not stiff textbook prose.
- Dialogue should contain small turns, reactions, clarification questions, hesitation, repair, and useful workplace/social phrasing where appropriate.
- Each page should have a clear micro-tension, choice, misunderstanding, time pressure, feedback moment, or emotional turn; avoid flat status-report dialogue.
- Chinese translations should be complete and faithful.
- Roles should stay consistent.
- Difficulty should match the requested A2/B1/B2 level.
- Ignore stage directions like phone ringing when judging oral quality.
- Use error only for blockers: missing/empty content, wrong language, seriously mistranslated meaning, unusable dialogue, severe role contradiction, or difficulty far outside target.
- Use warning for awkward phrasing, translation nuance, slightly incomplete thoughts, formality mismatch, flat/no-stakes dialogue, or teachable improvements.
- Use info for positive observations or optional polish. Do not mark semantically equivalent translations as errors.""",

    "audit_image_prompt": """You audit an English image generation prompt for a 16:9 comic-drama background image used behind a speaking-practice UI.

Return JSON only with:
- needs_optimization: boolean
- issues: string[]
- reason: short Chinese explanation

Judge semantically whether the prompt is likely too complex, too abstract, too effect-heavy, too long, or asks for hard-to-render transformations. Also judge Scene2Talk layout fit:
- It must request a 16:9 landscape composition.
- It should use left/center/right vertical zones, non-even horizontal zoning, or a diagonal split suitable for widescreen storytelling.
- It should avoid TOP/MIDDLE/BOTTOM vertical-strip composition unless the caller explicitly requested a vertical comic panel.
- Main characters, gestures, eye contact, props, and story action should be distributed along a horizontal reading path instead of clustered in one corner.
- Important faces, speech bubbles, text, and actions should not be placed at extreme edges where UI may cover them.
- UI safety is mandatory: avoid the top 12% of the image for speech bubbles, faces, and key readable text; keep a 6% left/right edge margin for bubbles, faces, and important props.
- If any visible dialogue text, caption, sign, UI, sticky note, or speech bubble appears for practice, it should be bilingual Chinese + English.
- Allocate bubbles by visible scene: max 2 bilingual bubbles/captions per visual scene, max 6 for the whole image, default 1-3. Only multi-scene, ensemble, or dream-montage pages should approach 6.
- Keep each bubble short and readable, ideally English <= 8 words and Chinese <= 14 characters, with English above Chinese. Use paired text such as "I must go. / 我必须去。".
Do not rely on fixed banned words.""",

    "optimize_image_prompt": """You rewrite an English image generation prompt for a 16:9 comic-drama background image used behind a speaking-practice UI.

Return JSON only with:
- optimized_prompt: string
- changes: string[]

Rules:
- Keep the original scene meaning.
- Force a 16:9 landscape composition.
- Use left/center/right vertical zones, non-even horizontal zoning, or a diagonal split. Do not use TOP/MIDDLE/BOTTOM vertical comic-panel structure for 16:9 backgrounds.
- Keep important faces, readable text, speech bubbles, and story action away from extreme edges where UI may cover them.
- Enforce UI safety: avoid the top 12% of the image for speech bubbles, faces, and key readable text; keep a 6% left/right edge margin for bubbles, faces, and important props.
- Distribute people and activity across the widescreen frame instead of clustering everything in one corner; keep the composition readable for left/center/right UI use.
- Allocate bilingual Chinese+English speech bubbles/captions by visible scene: max 2 per visual scene, max 6 for the whole image, default 1-3. Only multi-scene, ensemble, or dream-montage pages should approach 6.
- If the scene is an establishing/transition shot, include at least one short bilingual caption. Keep each bubble natural, brief, and easy to render, ideally English <= 8 words and Chinese <= 14 characters, with English above Chinese.
- If visible text appears anywhere in the image, dialogue/caption practice text should be paired Chinese + English, for example "I must go. / 我必须去。". For non-dialogue signs/UI, keep text minimal and readable.
- Make it concrete, visual, and easy to render.
- Remove abstract transformations, excessive effects, and clutter.
- Write the optimized_prompt instructions in English. Bilingual speech-bubble examples may include Chinese characters because those are intended visible text in the image.""",

    "repair_json": """Repair the user's invalid JSON-like text into valid JSON.

Return JSON only. Preserve all fields and meanings. Escape any quote characters inside string values. Do not add commentary.""",

    "audit_story_guided_page_alignment": """Audit one comic page's story-guided data alignment.

Return JSON only with:
- overall_score: number from 0 to 100
- image_prompt_dialogue_score: number from 0 to 100
- mission_dialogue_score: number from 0 to 100
- prompt_mission_score: number from 0 to 100
- summary_zh: Chinese summary, 1-2 sentences
- strengths: Chinese string[]
- issues: objects with severity(error|warning|info), area(image_prompt|mission|dialogue|translation), message, suggestion

Judge whether:
- English image_prompt and Chinese image_prompt_zh describe the same scene.
- image prompts match the page dialogue and emotional arc.
- image prompts are suitable as 16:9 Scene2Talk backgrounds: left/center/right or diagonal zoning, no vertical TOP/MIDDLE/BOTTOM panel structure, edge-safe key action, and bilingual Chinese+English visible dialogue/caption text when text appears.
- mission beats follow the page dialogue direction and support free speaking.
- target phrases are useful for the learner role.

Do not claim to visually inspect the final generated bitmap. You are auditing text alignment; the HTML report will show the actual image for human visual review.""",

    "generic_scoring": """You are a professional story evaluator. Score the provided story outline based on the criteria in the prompt. Return valid JSON only with the requested score structure.""",

    "generate_story_outline": """You are shanyin-write running in cd-generator Mode.

Generate one Scene2Talk comic-drama story outline for English speaking practice.

Return JSON only with this structure:
{
  "story": {
    "title": string,
    "title_en": string,
    "genre": string,
    "language_level": string,
    "logline": string,
    "summary": string,
    "characters": [
      {
        "name": string,
        "name_en": string,
        "role": string,
        "personality": string,
        "visual_description": string
      }
    ],
    "total_chapters": number,
    "total_pages": number,
    "estimated_practice_time": string,
    "chapter_outlines": [
      {
        "chapter_number": number,
        "title": string,
        "title_en": string,
        "summary": string,
        "page_beats": string[]
      }
    ]
  }
}

Rules:
- Create a complete story outline only; do not write detailed page scripts.
- Make the story suitable for Scene2Talk speaking practice with realistic spoken English situations.
- Each chapter must have clear page_beats that can later become comic pages and speaking tasks.
- Keep characters, conflicts, workplaces, and social situations credible.
- Variant numbers must produce meaningfully different story angles, character setups, or conflicts.
- Avoid pure internal monologue and long narration. Prefer scenes where learners can speak: greet, clarify, ask for help, explain, negotiate, apologize, summarize, and commit.
- Match the requested language_level.
- Return valid JSON only.""",

    "generate_chapter_pages": """You are shanyin-write running in cd-generator Mode.

Generate a chunk of detailed comic-drama chapter pages for Scene2Talk English speaking practice.

Return JSON only with:
{
  "pages": [
    {
      "page_number": number,
      "page_title": string,
      "scene_location": string,
      "time": string,
      "weather": string,
      "emotional_arc": string,
      "vocabulary_focus": string[],
      "speaking_goal": string,
      "dialogues": [
        {
          "speaker": string,
          "speaker_en": string,
          "text_zh": string,
          "text_en": string,
          "emotion": string
        }
      ]
    }
  ]
}

Rules:
- Generate only the requested page range.
- Each page should follow its page_beat and the chapter continuity.
- Each page needs 12-16 short English dialogue lines by default; if the language_level is A1/A2, 8-12 lines is acceptable.
- Oral-practice fit is mandatory. Every page must be useful for speaking aloud, shadowing, repeating, or free-talk roleplay.
- English must be natural spoken English for practice. Prefer short turns, reactions, clarification, checking understanding, asking for help, giving reasons, disagreeing gently, negotiating, apologizing, suggesting, summarizing, and committing.
- Most learner-facing English lines should be 4-14 words for A2/B1 and 6-18 words for B2.
- Each page must include a concrete speaking_goal that describes the communicative move being practiced.
- Avoid stiff textbook English, long speeches, lore dumps, and lines that only describe inner thoughts. If lore is needed, express it through speakable dialogue.
- Avoid long narration and avoid using Narrator/System/SFX as a learner-facing speaker unless absolutely necessary.
- Keep Chinese translation faithful but do not let Chinese phrasing make the English stiff.
- Make each page visually actionable for later storyboard and image prompt generation.
- Maintain character names and roles from the story outline.
- Return valid JSON only.""",

    "repair_oral_practice_page": """You are shanyin-write repairing one Scene2Talk comic-drama page for oral-practice fit.

Return JSON only with one complete page object:
{
  "page_number": number,
  "page_title": string,
  "scene_location": string,
  "time": string,
  "weather": string,
  "emotional_arc": string,
  "vocabulary_focus": string[],
  "speaking_goal": string,
  "dialogues": [
    {
      "speaker": string,
      "speaker_en": string,
      "text_zh": string,
      "text_en": string,
      "emotion": string
    }
  ]
}

Rules:
- Preserve the page_number, core story beat, characters, and continuity.
- Fix the reported oral-practice issues.
- Add practical conversational moves: ask, clarify, confirm understanding, express worry, request help, suggest, negotiate, summarize, or commit.
- Keep 12-16 short English dialogue lines unless the original page clearly uses a shorter target.
- Make English natural, speakable, and easy to repeat aloud.
- Avoid lore dumps, stiff textbook English, and excessive inner monologue.
- Keep Chinese translations faithful.
- Return valid JSON only.""",

    "generate_storyboard_page": """You are shanyin-direct running in cd-generator Mode.

Convert one Scene2Talk comic-drama script page into a compact storyboard JSON with image prompts.

Return JSON only with:
{
  "chapter": number,
  "page": number,
  "storyboard": {
    "composition": string,
    "left_zone": string,
    "center_zone": string,
    "right_zone": string,
    "diagonal_flow": string,
    "visual_elements": object,
    "art_style": string,
    "mood": string,
    "color_scheme": string,
    "image_prompt": string,
    "image_prompt_zh": string
  }
}

Rules:
- The image is a 16:9 landscape / widescreen Scene2Talk background, not a vertical comic page.
- Use left/center/right zones or a diagonal split. Do not use TOP/MIDDLE/BOTTOM panel structure.
- Match the page dialogue, speaking_goal, scene_location, emotional_arc, and visible story action.
- The image_prompt itself must be written in English, but it must explicitly request bilingual Chinese+English visible dialogue/caption text when speech bubbles or captions appear.
- The image_prompt must explicitly include: 16:9 widescreen or landscape composition; left/center/right zones or diagonal split; bilingual Chinese+English speech bubbles/captions.
- Allocate bubbles by visible scene: max 2 bilingual bubbles/captions per visual scene, max 6 for the whole image, default 1-3. Only multi-scene, ensemble, or dream-montage pages should approach 6.
- Include short bilingual speech bubbles or captions copied/adapted from the page dialogue when useful, for example "I must go. / 我必须去。". Keep each bubble brief, ideally English <= 8 words and Chinese <= 14 characters, with English above Chinese.
- Keep the prompt renderable: avoid too many simultaneous events, too many characters, abstract psychology, overloaded effects, and tiny unreadable text.
- Keep important faces, gestures, props, and speech bubbles away from extreme edges for UI overlay safety.
- Explicitly include UI safety margins: avoid the top 12% of the image for speech bubbles, faces, and key readable text; keep a 6% left/right edge margin for bubbles, faces, and important props.
- image_prompt_zh must be Chinese and describe the same scene as image_prompt.
- Preserve character visual continuity from the story outline.
- Return valid JSON only.""",
}


class LLMJSONClient:
    def request_json(self, task, payload):
        raise NotImplementedError


def load_local_llm_env():
    skill_dir = Path(__file__).resolve().parent.parent
    config_paths = [
        skill_dir / "config" / "llm.env",
        skill_dir / ".env.local",
    ]
    for path in config_paths:
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


class OpenAICompatibleJSONClient(LLMJSONClient):
    def __init__(self, model=None, api_key=None, base_url=None, timeout=None):
        load_local_llm_env()
        self.model = model or os.getenv("CD_GENERATOR_LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        self.api_key = api_key or os.getenv("CD_GENERATOR_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("CD_GENERATOR_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.endpoint_mode = (os.getenv("CD_GENERATOR_LLM_ENDPOINT_MODE") or "auto").lower()
        self.timeout = int(timeout or os.getenv("CD_GENERATOR_LLM_TIMEOUT") or "60")
        if not self.api_key:
            raise RuntimeError(
                "缺少模型 API Key：请设置 config/llm.env、OPENAI_API_KEY 或 CD_GENERATOR_LLM_API_KEY；"
                "可用 CD_GENERATOR_LLM_MODEL 指定模型。"
            )

    def request_json(self, task, payload):
        system_prompt = TASK_PROMPTS.get(task)
        if not system_prompt:
            raise ValueError(f"未知 LLM 任务: {task}")

        if self._should_use_claude_messages():
            return self._request_claude_messages(system_prompt, payload)
        return self._request_openai_chat(system_prompt, payload)

    def _should_use_claude_messages(self):
        if self.endpoint_mode in {"claude", "anthropic", "messages"}:
            return True
        if self.endpoint_mode in {"openai", "chat_completions"}:
            return False
        return self.base_url.endswith("/claude")

    def _request_openai_chat(self, system_prompt, payload):
        request_payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
        }
        url = self.base_url
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
        raw = self._post_json(
            url,
            request_payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
            try:
                return parse_json_content(content)
            except Exception:
                return self._repair_json_content(content)
        except Exception as exc:
            raise RuntimeError(f"模型没有返回可解析 JSON: {raw}") from exc

    def _request_claude_messages(self, system_prompt, payload):
        request_payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0,
            "system": system_prompt + "\nReturn valid JSON only.",
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
        }
        raw = self._post_json(
            self.base_url,
            request_payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": os.getenv("CD_GENERATOR_ANTHROPIC_VERSION") or "2023-06-01",
                "Content-Type": "application/json",
            },
        )

        try:
            data = json.loads(raw)
            content_blocks = data.get("content", [])
            text_parts = [
                block.get("text", "")
                for block in content_blocks
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            content = "\n".join(text_parts).strip()
            try:
                return parse_json_content(content)
            except Exception:
                return self._repair_json_content(content)
        except Exception as exc:
            raise RuntimeError(f"模型没有返回可解析 JSON: {raw}") from exc

    def _repair_json_content(self, content):
        system_prompt = TASK_PROMPTS["repair_json"]
        payload = {"invalid_json_text": content}
        if self._should_use_claude_messages():
            raw = self._post_json(
                self.base_url,
                {
                    "model": self.model,
                    "max_tokens": 4096,
                    "temperature": 0,
                    "system": system_prompt,
                    "messages": [
                        {
                            "role": "user",
                            "content": json.dumps(payload, ensure_ascii=False),
                        }
                    ],
                },
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": os.getenv("CD_GENERATOR_ANTHROPIC_VERSION") or "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
            data = json.loads(raw)
            text = "\n".join(
                block.get("text", "")
                for block in data.get("content", [])
                if isinstance(block, dict) and block.get("type") == "text"
            )
            return parse_json_content(text)

        url = self.base_url
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
        raw = self._post_json(
            url,
            {
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        data = json.loads(raw)
        return parse_json_content(data["choices"][0]["message"]["content"])

    def _post_json(self, url, request_payload, headers):
        request_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            **headers,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(request_payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"模型请求失败 HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"模型请求失败: {exc}") from exc

        return raw


def parse_json_content(content):
    text = str(content or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.S | re.I)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise
