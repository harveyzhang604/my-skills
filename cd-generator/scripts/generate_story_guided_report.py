#!/usr/bin/env python3
"""
Generate a detailed HTML report for Story-Guided Free Talk output.

The report is written to <task_dir>/output/story_guided_report.html and includes
images, prompts, dialogues, missions, quality results, and model-based text
alignment scores.
"""

import base64
import html
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from llm_json_client import OpenAICompatibleJSONClient
    from task_path_guard import require_task_dir
except ImportError:
    from .llm_json_client import OpenAICompatibleJSONClient
    from .task_path_guard import require_task_dir


def esc(value):
    return html.escape(str(value or ""), quote=True)


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path):
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def image_data_uri(path):
    path = Path(path)
    if not path.exists():
        return ""
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    return f"data:image/{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def page_key(chapter, page):
    return f"chapter{chapter}_page{page}"


def score_class(score):
    try:
        score = float(score)
    except Exception:
        return "score-mid"
    if score >= 85:
        return "score-good"
    if score >= 70:
        return "score-mid"
    return "score-low"


def issue_badge(severity):
    if severity == "error":
        return "badge-error"
    if severity == "warning":
        return "badge-warning"
    return "badge-info"


def build_alignment(task_dir, story, force=False):
    quality_dir = task_dir / "quality"
    quality_dir.mkdir(exist_ok=True)
    cache_file = quality_dir / "story_guided_alignment_report.json"
    if cache_file.exists() and not force:
        return load_json(cache_file, {})

    client = OpenAICompatibleJSONClient()
    alignments = {}
    for chapter in story.get("chapters", []):
        chapter_num = chapter.get("chapter_number")
        for page in chapter.get("pages", []):
            page_num = page.get("page_number")
            key = page_key(chapter_num, page_num)
            payload = {
                "page_key": key,
                "scene_location": page.get("scene_location", ""),
                "dialogues": page.get("dialogues", []),
                "vocabulary_focus": page.get("vocabulary_focus", []),
                "image_prompt": load_text(task_dir / "prompts" / f"{key}.txt"),
                "image_prompt_zh": load_text(task_dir / "prompts_zh" / f"{key}.txt"),
                "storyboard": load_json(task_dir / "storyboards" / f"{key}.json", {}),
                "mission": load_json(task_dir / "missions" / f"{key}.json", {}),
            }
            result = client.request_json("audit_story_guided_page_alignment", payload)
            alignments[key] = result
            print(f"✅ 页面匹配审稿完成: {key}")

    report = {
        "checked_at": now_iso(),
        "auditor": "llm_semantic_alignment_v1",
        "pages": alignments,
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return report


def render_dialogues(dialogues):
    parts = []
    for index, item in enumerate(dialogues or [], start=1):
        speaker = item.get("speaker_en") or item.get("speaker") or "?"
        text_en = item.get("text_en", "")
        text_zh = item.get("text_zh", "")
        emotion = item.get("emotion", "")
        parts.append(
            f"""
            <div class="dialogue">
              <div class="dialogue-index">{index}</div>
              <div class="dialogue-body">
                <div class="dialogue-head"><span>{esc(speaker)}</span><em>{esc(emotion)}</em></div>
                <div class="dialogue-en">{esc(text_en)}</div>
                <div class="dialogue-zh">{esc(text_zh)}</div>
              </div>
            </div>
            """
        )
    return "\n".join(parts)


def render_beats(beats):
    parts = []
    for index, beat in enumerate(beats or [], start=1):
        examples = beat.get("example_phrases", []) or []
        sources = beat.get("source_dialogue_indices", []) or []
        parts.append(
            f"""
            <div class="beat">
              <div class="beat-num">{index}</div>
              <div class="beat-main">
                <div class="beat-title">{esc(beat.get('label'))}<span>{esc(beat.get('intent'))}</span></div>
                <div class="beat-zh">{esc(beat.get('label_zh'))}</div>
                <div class="beat-criteria">{esc(beat.get('acceptance_criteria'))}</div>
                <div class="beat-meta">source: {esc(', '.join(map(str, sources)))} · examples: {esc(' / '.join(examples))}</div>
              </div>
            </div>
            """
        )
    return "\n".join(parts)


def render_issues(issues):
    if not issues:
        return '<div class="empty">未发现明显问题。</div>'
    rows = []
    for issue in issues:
        severity = issue.get("severity", "info")
        rows.append(
            f"""
            <div class="issue">
              <span class="badge {issue_badge(severity)}">{esc(severity)}</span>
              <strong>{esc(issue.get('area') or issue.get('code') or 'issue')}</strong>
              <p>{esc(issue.get('message'))}</p>
              <small>{esc(issue.get('suggestion'))}</small>
            </div>
            """
        )
    return "\n".join(rows)


def render_raw_json(title, data):
    return f"""
    <details class="raw">
      <summary>{esc(title)}</summary>
      <pre>{esc(json.dumps(data or {}, indent=2, ensure_ascii=False))}</pre>
    </details>
    """


def render_report(task_dir, final, quality, alignment):
    story = final.get("story", {})
    pages_alignment = alignment.get("pages", {})
    quality_issues = quality.get("issues", []) if quality else []
    quality_by_location = {}
    for issue in quality_issues:
        quality_by_location.setdefault(issue.get("location", ""), []).append(issue)

    html_parts = []
    w = html_parts.append
    w(f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(story.get('title'))} - Story Guided Report</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#0b0c10;color:#e8e8ea;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.5}}
.hero{{padding:28px 36px;background:#171923;border-bottom:1px solid #2d3142;position:sticky;top:0;z-index:3}}
.hero h1{{margin:0;font-size:26px}} .hero p{{margin:6px 0 0;color:#a9adbb}}
.meta{{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}} .pill{{padding:5px 10px;border:1px solid #38405a;background:#202436;border-radius:999px;color:#c9d1e6;font-size:12px}}
.wrap{{max-width:1320px;margin:0 auto;padding:24px}}
.summary-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
.metric{{background:#151824;border:1px solid #2b3147;border-radius:8px;padding:14px}} .metric span{{display:block;color:#9098ad;font-size:12px}} .metric strong{{font-size:24px}}
.section-title{{font-size:20px;margin:24px 0 12px;color:#fff}}
.page{{background:#141722;border:1px solid #2b3147;border-radius:10px;margin-bottom:28px;overflow:hidden}}
.page-head{{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 20px;border-bottom:1px solid #2b3147;background:#191d2b}}
.page-head h2{{font-size:18px;margin:0}} .scene{{color:#9ea6bb;font-size:13px;margin-top:4px}}
.scores{{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}} .score{{padding:6px 10px;border-radius:7px;font-size:12px;border:1px solid #3b4158}} .score b{{font-size:15px}}
.score-good{{background:#123326;color:#82f0b4}} .score-mid{{background:#352d13;color:#ffd36e}} .score-low{{background:#3b181b;color:#ff9ca5}}
.page-body{{display:grid;grid-template-columns:280px minmax(0,1fr);gap:18px;padding:18px}}
.image-panel img{{width:100%;border-radius:8px;border:1px solid #333a52;background:#0e1018}} .image-note{{font-size:12px;color:#8f96a8;margin-top:8px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} .panel{{background:#0f121b;border:1px solid #282e42;border-radius:8px;padding:14px;min-width:0}}
.panel h3{{font-size:14px;margin:0 0 10px;color:#dce5ff}} .text-block{{white-space:pre-wrap;font-size:12px;color:#c5cad8;overflow-wrap:anywhere}}
.dialogue{{display:flex;gap:10px;border-bottom:1px solid #22283a;padding:8px 0}} .dialogue-index{{width:24px;height:24px;border-radius:50%;background:#26304d;color:#dce5ff;text-align:center;font-size:12px;line-height:24px;flex:0 0 auto}}
.dialogue-head{{display:flex;gap:8px;align-items:center}} .dialogue-head span{{color:#8fb3ff;font-weight:700;font-size:12px}} .dialogue-head em{{color:#7d8496;font-size:11px}}
.dialogue-en{{font-size:13px;color:#f0f2f8}} .dialogue-zh{{font-size:12px;color:#abb2c5}}
.beat{{display:flex;gap:10px;border-bottom:1px solid #22283a;padding:9px 0}} .beat-num{{width:24px;height:24px;border-radius:6px;background:#332642;color:#f0c8ff;text-align:center;line-height:24px;font-size:12px;flex:0 0 auto}}
.beat-title{{font-weight:700;color:#fff}} .beat-title span{{margin-left:8px;color:#b58cff;font-size:11px;font-weight:500}} .beat-zh{{color:#c4bdd0;font-size:12px}} .beat-criteria{{color:#d6d9e5;font-size:12px;margin-top:4px}} .beat-meta{{color:#7f879a;font-size:11px;margin-top:4px}}
.badge{{display:inline-block;padding:2px 7px;border-radius:999px;font-size:11px;margin-right:6px}} .badge-error{{background:#5a1d24;color:#ffb3bd}} .badge-warning{{background:#4b3914;color:#ffd883}} .badge-info{{background:#1e3558;color:#9cc8ff}}
.issue{{border-bottom:1px solid #22283a;padding:8px 0}} .issue p{{margin:5px 0;color:#d8dbe5;font-size:12px}} .issue small{{color:#8f96a8}}
.empty{{color:#8f96a8;font-size:12px}} details.raw{{margin-top:10px;background:#0b0d14;border:1px solid #242a3d;border-radius:8px;padding:10px}} details.raw summary{{cursor:pointer;color:#9cc8ff;font-size:12px}} pre{{white-space:pre-wrap;overflow:auto;font-size:11px;color:#bec6d8}}
@media(max-width:900px){{.summary-grid,.page-body,.grid2{{grid-template-columns:1fr}} .hero{{position:static}}}}
</style>
</head>
<body>
<div class="hero">
  <h1>{esc(story.get('title'))} · Story-Guided 数据报告</h1>
  <p>{esc(story.get('title_en'))} · 生成时间 {esc(now_iso())}</p>
  <div class="meta">
    <span class="pill">任务目录：{esc(task_dir.name)}</span>
    <span class="pill">难度：{esc(story.get('language_level') or story.get('level'))}</span>
    <span class="pill">类型：{esc(story.get('genre'))}</span>
    <span class="pill">审稿：模型文本匹配 + 实图展示</span>
  </div>
</div>
<main class="wrap">
""")
    summary = quality.get("summary", {}) if quality else {}
    w(f"""
<div class="summary-grid">
  <div class="metric"><span>页面数</span><strong>{esc(summary.get('pages'))}</strong></div>
  <div class="metric"><span>对话句数</span><strong>{esc(summary.get('dialogues'))}</strong></div>
  <div class="metric"><span>质检 Error</span><strong>{esc(summary.get('errors'))}</strong></div>
  <div class="metric"><span>质检 Warning</span><strong>{esc(summary.get('warnings'))}</strong></div>
</div>
<div class="panel">
  <h3>说明</h3>
  <div class="text-block">本报告展示实际生成图片，并用模型对 image_prompt / image_prompt_zh / 对话 / mission 做文本一致性审稿。当前模型不直接视觉识别本地图片，图片与对话的最终视觉匹配可在每页左侧直接人工对照。</div>
</div>
""")

    for chapter in story.get("chapters", []):
        w(f'<h2 class="section-title">Chapter {esc(chapter.get("chapter_number"))} · {esc(chapter.get("chapter_title") or chapter.get("title"))}</h2>')
        for page in chapter.get("pages", []):
            chapter_num = chapter.get("chapter_number")
            page_num = page.get("page_number")
            key = page_key(chapter_num, page_num)
            mission = load_json(task_dir / "missions" / f"{key}.json", {})
            storyboard = load_json(task_dir / "storyboards" / f"{key}.json", {})
            prompt_en = load_text(task_dir / "prompts" / f"{key}.txt")
            prompt_zh = load_text(task_dir / "prompts_zh" / f"{key}.txt")
            image_uri = image_data_uri(task_dir / "images" / f"{key}.png")
            align = pages_alignment.get(key, {})
            q_issues = quality_by_location.get(key, [])
            a_issues = align.get("issues", [])
            w(f"""
<section class="page">
  <div class="page-head">
    <div>
      <h2>{esc(key)} · {esc(page.get('page_title') or page.get('title') or '')}</h2>
      <div class="scene">{esc(page.get('scene_location'))}</div>
    </div>
    <div class="scores">
      <span class="score {score_class(align.get('overall_score'))}">整体 <b>{esc(align.get('overall_score'))}</b></span>
      <span class="score {score_class(align.get('image_prompt_dialogue_score'))}">图文提示 <b>{esc(align.get('image_prompt_dialogue_score'))}</b></span>
      <span class="score {score_class(align.get('mission_dialogue_score'))}">任务对话 <b>{esc(align.get('mission_dialogue_score'))}</b></span>
      <span class="score {score_class(align.get('prompt_mission_score'))}">提示任务 <b>{esc(align.get('prompt_mission_score'))}</b></span>
    </div>
  </div>
  <div class="page-body">
    <aside class="image-panel">
      {'<img src="' + image_uri + '" alt="' + esc(key) + '">' if image_uri else '<div class="empty">未找到图片</div>'}
      <div class="image-note">实际图片：images/{esc(key)}.png</div>
    </aside>
    <div class="content">
      <div class="grid2">
        <div class="panel">
          <h3>匹配总结</h3>
          <div class="text-block">{esc(align.get('summary_zh'))}</div>
          <h3 style="margin-top:14px">匹配问题</h3>
          {render_issues(a_issues)}
        </div>
        <div class="panel">
          <h3>内容质检问题</h3>
          {render_issues(q_issues)}
        </div>
      </div>
      <div class="grid2" style="margin-top:14px">
        <div class="panel">
          <h3>英文图片提示词 image_prompt</h3>
          <div class="text-block">{esc(prompt_en)}</div>
        </div>
        <div class="panel">
          <h3>中文图片提示词 image_prompt_zh</h3>
          <div class="text-block">{esc(prompt_zh)}</div>
        </div>
      </div>
      <div class="grid2" style="margin-top:14px">
        <div class="panel">
          <h3>Story-Guided Mission</h3>
          <div class="text-block">用户角色：{esc(mission.get('user_role'))} → AI角色：{esc(mission.get('ai_role'))}<br>摘要：{esc(mission.get('mission_summary'))}</div>
          {render_beats(mission.get('must_hit_beats', []))}
          <h3 style="margin-top:12px">Target Phrases</h3>
          <div class="text-block">{esc(' / '.join(mission.get('target_phrases', [])))}</div>
        </div>
        <div class="panel">
          <h3>对话 Dialogues</h3>
          {render_dialogues(page.get('dialogues', []))}
        </div>
      </div>
      {render_raw_json('原始 mission JSON', mission)}
      {render_raw_json('原始 storyboard JSON', storyboard)}
      {render_raw_json('页面匹配审稿 JSON', align)}
    </div>
  </div>
</section>
""")

    w(render_raw_json("完整质量报告 JSON", quality))
    w("</main></body></html>")
    return "\n".join(html_parts)


def main():
    if len(sys.argv) < 2:
        print("用法: generate_story_guided_report.py <task_dir> [--force]")
        return 1
    task_dir = require_task_dir(sys.argv[1])
    force = "--force" in sys.argv[2:]
    should_open = "--no-open" not in sys.argv[2:]
    final = load_json(task_dir / "output" / "final_output.json")
    if not final:
        print(f"错误：找不到 final_output.json: {task_dir / 'output' / 'final_output.json'}")
        return 1
    story = final.get("story", {})
    quality = load_json(task_dir / "quality" / "content_quality_report.json", {})
    alignment = build_alignment(task_dir, story, force=force)
    html_text = render_report(task_dir, final, quality, alignment)
    output_file = task_dir / "output" / "story_guided_report.html"
    output_file.parent.mkdir(exist_ok=True)
    output_file.write_text(html_text, encoding="utf-8")
    print(f"✅ Story-Guided HTML 报告已生成: {output_file}")
    print(f"📊 页面匹配数据: {task_dir / 'quality' / 'story_guided_alignment_report.json'}")
    if should_open:
        open_in_default_browser(output_file)
    return 0


def open_in_default_browser(path):
    path = Path(path).resolve()
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
        print(f"🌐 已用默认浏览器打开: {path}")
    except Exception as exc:
        print(f"⚠️ 报告已生成，但自动打开失败: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
