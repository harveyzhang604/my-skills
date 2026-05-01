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
- Each variant must have different story angles, character setups, or conflict designs
- Example: for "designer growth", variant 1 could be "newbie meets strict mentor", variant 2 could be "team collaboration challenge", variant 3 could be "client demand conflict"
- Ensure the story is suitable for speaking practice with realistic dialogue scenarios

#### Scenario 2: Full Script Generation (for final production)

**Story Outline Input**:
- story theme, genre, language level, total chapters, pages per chapter, and art style
- Scene2Talk speaking-practice goal and target learner context
- required output file type: `story_outline.json`
- production constraints: natural spoken English, short turns, page-level speaking goals, and JSON-only output

**Chapter Script Input**:
- complete `story_outline.json`
- current `chapter_number` and corresponding `chapter_outlines[]`
- previous chapter ending state (if any) and next chapter connection goal (if any)
- each page serves speaking practice: 12-16 short English dialogues with natural reactions, clarifications, follow-ups, corrections, commitments, etc.
- required output file type: `scripts/chapter{N}.json`
- output constraints: JSON only, no Markdown explanation, no pause for confirmation

Expected input from `cd-generator`:

- story theme, genre, language level, total chapters, pages per chapter, and art style
- Scene2Talk speaking-practice goal and target learner context
- required output file type: `story_outline.json` or `scripts/chapter{N}.json`
- any continuity constraints from previous chapters/pages
- production constraints: natural spoken English, short turns, page-level speaking goals, and JSON-only output

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

## Writing Rules

- English dialogue must match the requested A2/B1/B2 level and sound natural for speaking practice.
- Each page needs a clear speaking purpose: greet, clarify, ask for help, explain a reason, respond to feedback, negotiate time, summarize a promise, etc.
- Keep dialogue short enough for learners to repeat aloud.
- Use micro-tension: misunderstanding, time pressure, feedback, hesitation, repair, choice, or small emotional turn.
- Avoid stage/system speakers unless the line is truly a sound cue; never make those the learner role.
- Use visible actions and subtext; avoid abstract psychology and explanatory monologues.
- Output valid JSON only when the caller requests a file artifact.
