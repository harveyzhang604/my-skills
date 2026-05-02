---
name: shanyin-write
description: Use when generating story outlines, chapter scripts, character arcs, beat sheets, or dialogue scripts for comic drama, short film, film, or series writing; especially when cd-generator needs structured story JSON.
---

# Shanyin Write

This skill adapts the Shanyin screenwriting methodology for Scene2Talk and `cd-generator`.
Use the bundled references for the full screenwriting process, format-specific rules, and dialogue/story structure.

## Source References

Read only what the task needs:

- `references/screenwriting-master.md`: original Shanyin screenwriting skill instructions
- `references/core-methodology.md`: shared story, character, structure, scene, and dialogue principles
- `references/format-series.md`: multi-episode and chapter-based story planning
- `references/format-short.md`: compact story structure
- `references/format-ultrashort.md`: concept ultrashort structure
- `references/format-feature.md`: feature-length structure

## cd-generator Mode

When called by `cd-generator`, do not follow the original interactive pause-after-each-step workflow. Produce the requested JSON artifact directly because `cd-generator` owns the outer progress gates.

Still provide short progress feedback while working. Progress feedback must be separate from the JSON artifact: do not put progress text inside `story_outline.json` or `scripts/chapter{N}.json`, and do not wrap the final JSON file content in Markdown if the caller is saving it directly.

### Execution Boundary

This skill is a writing contract for AI conversation mode. Shell scripts cannot directly execute a skill document.

For `cd-generator` script mode, use the concrete executors:

- `cd-generator/scripts/generate_outline_with_llm.py` for `data/story_outline.json`
- `cd-generator/scripts/generate_chapter_with_llm.py` for `scripts/chapter{N}.json`

Do not rely on a bash script saying "call shanyin-write" unless it invokes one of these executors. The executors must print progress, call the configured LLM, validate JSON, and write files.

**No Silent Work Rule**: when invoked by `cd-generator`, send a progress message before doing long reasoning or reading heavy references. Do not wait until the full JSON is complete before responding. If generation will take more than about 30 seconds, emit another progress update before continuing.

**JSON-only boundary**: `JSON only` applies only to the final artifact content that will be written to a file. It does not suppress conversational progress updates. If the caller asks for both JSON-only output and progress feedback, keep progress in the conversation and keep the saved artifact pure JSON.

### Progress Feedback Protocol

Use brief Chinese status messages before and during long generation steps so the caller is not left waiting.

**First response after invocation**:
```
⏳ shanyin-write：已收到 cd-generator 调用，正在进入 {story_outline|chapter_script|batch_outline} 模式
   - 目标文件：{target_file}
   - 范围：{chapters/pages/variant_count}
```

**General format**:
```
⏳ shanyin-write：{current_step}
   - {useful_metric_or_context}
```

**Do not ask for confirmation** in `cd-generator Mode`. These messages are status updates only.

**Story outline milestones**:

1. Input received and generation scope locked
2. Characters, core conflict, and speaking-practice goal drafted
3. Chapter arc and page beats drafted
4. JSON structure checked and ready to write

Example:
```
⏳ shanyin-write：正在规划故事大纲
   - 章节数：8
   - 每章页数：6
   - 语言等级：B1
```

**Chapter script milestones**:

1. Chapter context and continuity constraints loaded
2. Page beats mapped to speaking goals
3. Dialogue generation progress reported every 2 pages, or at 25% / 50% / 75% / 100% for longer chapters
4. JSON structure, page count, and dialogue count checked

Example:
```
⏳ shanyin-write：正在生成第3章剧本
   - 已完成：4/8 页
   - 当前重点：澄清需求 + 协商下一步
```

**Batch outline milestones**:

When producing multiple variants, report after every 2 variants and at completion.

Example:
```
⏳ shanyin-write：批量大纲生成中
   - 已完成：6/10 个变体
   - 正在增加差异化冲突
```

If the caller explicitly says `quiet JSON mode`, suppress progress messages and return only the JSON artifact.

### Two Calling Scenarios

#### Scenario 1: Batch Outline Generation (for quick screening)

**Input**:
- `story_theme`: story theme or direction
- `genre`: genre type
- `language_level`: language difficulty
- `total_chapters`: number of chapters
- `pages_per_chapter`: pages per chapter
- `art_style`: art style
- `variant`: variant number (1-10), each variant should differ significantly in plot, characters, or conflict

**Output**: `story_outline.json` (outline only, no detailed scripts)

**Requirements**:
- First emit the `First response after invocation` progress message before drafting the outline.
- For long batch or high-page-count requests, emit milestone progress before continuing instead of staying silent.
- Each variant must have different story angles, character setups, or conflict designs
- Example: for "designer growth", variant 1 could be "newbie meets strict mentor", variant 2 could be "team collaboration challenge", variant 3 could be "client demand conflict"
- Ensure the story is suitable for speaking practice with realistic dialogue scenarios

#### Scenario 2: Full Script Generation (for final production)

**Story Outline Input**:
- story theme, genre, language level, total chapters, pages per chapter, and art style
- Scene2Talk speaking-practice goal and target learner context
- required output file type: `story_outline.json`
- production constraints: natural spoken English, short turns, page-level speaking goals, and pure JSON artifact output
- progress constraints: send progress before planning, after character/conflict design, after chapter arc drafting, and before final JSON handoff

**Chapter Script Input**:
- complete `story_outline.json`
- current `chapter_number` and corresponding `chapter_outlines[]`
- previous chapter ending state (if any) and next chapter connection goal (if any)
- each page serves speaking practice: 12-16 short English dialogues with natural reactions, clarifications, follow-ups, corrections, commitments, etc.
- required output file type: `scripts/chapter{N}.json`
- output constraints: pure JSON artifact output, no Markdown explanation inside the artifact, no pause for confirmation
- progress constraints: send progress before writing, after page-beat mapping, every 2 pages or 25% / 50% / 75% / 100%, and before final JSON handoff

Expected input from `cd-generator`:

- story theme, genre, language level, total chapters, pages per chapter, and art style
- Scene2Talk speaking-practice goal and target learner context
- required output file type: `story_outline.json` or `scripts/chapter{N}.json`
- any continuity constraints from previous chapters/pages
- production constraints: natural spoken English, short turns, page-level speaking goals, and pure JSON artifact output
- progress constraints: conversational progress is required unless the caller explicitly says `quiet JSON mode`

For `story_outline.json`, return a single JSON object with:

- `story.title`, `story.title_en`, `story.genre`, `story.language_level`
- `story.logline`, `story.summary`
- `story.characters[]` with `name`, `name_en`, `role`, `personality`, `visual_description`
- `story.total_chapters`, `story.total_pages`, `story.estimated_practice_time`
- `story.chapter_outlines[]` with `chapter_number`, `title`, `title_en`, `summary`, `page_beats[]`

For `scripts/chapter{N}.json`, return a single JSON object with:

- `chapter_number`, `title`, `title_en`, `summary`
- `pages[]`, one object per page
- each page has `page_number`, `page_title`, `scene_location`, `time`, `weather`, `emotional_arc`, `vocabulary_focus`
- each page has `dialogues[]` with 12-16 short lines by default, each line containing `speaker`, `speaker_en`, `text_zh`, `text_en`, and optional `emotion`

## Required Post-Generation Audit

After generating chapter scripts for `cd-generator`, run or request the oral-practice audit before moving to storyboard generation:

```bash
python3 cd-generator/scripts/audit_oral_practice_fit.py <task_dir> --chapters <N>
```

If the audit reports oral-practice issues, repair before storyboard generation:

```bash
python3 cd-generator/scripts/repair_oral_practice_issues.py <task_dir> --chapters <N>
```

The audit is part of the writing workflow. A chapter is not considered ready for `shanyin-direct` until:

- every page has a concrete `speaking_goal`
- dialogue is short, speakable, and natural for the target level
- each page has enough conversational moves for practice
- narrator/system/lore lines do not replace learner-facing dialogue
- warnings such as `few_conversation_moves` and `english_line_too_long` have been reviewed or fixed

## Writing Rules

- English dialogue must match the requested A2/B1/B2 level and sound natural for speaking practice.
- Oral-practice fit is a hard requirement, not a polish pass. Every page must be something a learner can speak aloud, shadow, repeat, or use in a free-talk exchange.
- Prefer short spoken turns over literary prose. Most learner-facing English lines should be 4-14 words for A2/B1 and 6-18 words for B2.
- Each page must include practical conversational moves such as greeting, asking for help, clarifying, checking understanding, expressing worry, giving a reason, disagreeing gently, apologizing, suggesting, negotiating, summarizing, or committing.
- Avoid lines that only describe inner thoughts, lore, exposition, prophecy, or narrator information. If lore is needed, turn it into dialogue with a clear speaking purpose.
- Avoid stiff textbook English. Use natural spoken phrases such as "Wait, what do you mean?", "Can you say that again?", "I think I understand", "Let's try one step first", or "I'm not ready, but I'll help."
- Keep each page usable for practice even without seeing the full chapter: the learner should know what communicative task they are practicing.
- Each page needs a clear speaking purpose: greet, clarify, ask for help, explain a reason, respond to feedback, negotiate time, summarize a promise, etc.
- Keep dialogue short enough for learners to repeat aloud.
- Use micro-tension: misunderstanding, time pressure, feedback, hesitation, repair, choice, or small emotional turn.
- Avoid stage/system speakers unless the line is truly a sound cue; never make those the learner role.
- Use visible actions and subtext; avoid abstract psychology and explanatory monologues.
- Output valid JSON only inside the file artifact when the caller requests one. Conversational progress updates are still required in `cd-generator Mode` unless the caller explicitly says `quiet JSON mode`.
