#!/bin/bash
# 生成漫剧HTML预览页面
# 用法: ./generate_preview.sh <task_dir>

TASK_DIR="$1"
GUARD="/Users/zhanghua/.claude/skills/cd-generator/scripts/task_path_guard.py"
if [ -z "$TASK_DIR" ]; then
    echo "用法: $0 <task_dir>"
    exit 1
fi

TASK_DIR="$(python3 "$GUARD" "$TASK_DIR")"

echo "🖥️  生成HTML预览页面..."

export TASK_DIR
python3 << 'PYEOF'
import json, base64, html, os, sys

task_dir = os.environ.get("TASK_DIR", sys.argv[1] if len(sys.argv) > 1 else "")
if not task_dir:
    print("错误：未指定任务目录")
    sys.exit(1)

# 读取final_output
with open(f"{task_dir}/output/final_output.json") as f:
    final = json.load(f)

# 读取提示词
prompts = {}
prompts_zh = {}
for root, dirs, files in os.walk(f"{task_dir}/storyboards"):
    for fn in files:
        if fn.endswith(".json"):
            ch = int(fn.split("chapter")[1].split("_")[0])
            pg = int(fn.split("_page")[1].split(".")[0])
            with open(os.path.join(root, fn)) as f:
                sb = json.load(f)
                storyboard = sb.get("storyboard", {})
                prompts[(ch,pg)] = storyboard.get("image_prompt", "")
                if storyboard.get("image_prompt_zh"):
                    prompts_zh[(ch,pg)] = storyboard["image_prompt_zh"]

# 读取提示词文件（优先）
prompts_dir = f"{task_dir}/prompts"
if os.path.isdir(prompts_dir):
    for fn in os.listdir(prompts_dir):
        if fn.endswith(".txt"):
            ch = int(fn.split("chapter")[1].split("_")[0])
            pg = int(fn.split("_page")[1].split(".")[0])
            with open(os.path.join(prompts_dir, fn)) as f:
                prompts[(ch,pg)] = f.read().strip()

# 读取中文提示词文件（最高优先级）
prompts_zh_dir = f"{task_dir}/prompts_zh"
if os.path.isdir(prompts_zh_dir):
    for fn in os.listdir(prompts_zh_dir):
        if fn.endswith(".txt"):
            ch = int(fn.split("chapter")[1].split("_")[0])
            pg = int(fn.split("_page")[1].split(".")[0])
            with open(os.path.join(prompts_zh_dir, fn)) as f:
                prompts_zh[(ch,pg)] = f.read().strip()

def img_to_base64(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def esc(value):
    return html.escape(str(value or ""), quote=False)

# 情感映射表
EMOTION_VAL = {
    "crushed":10,"dejected":15,"panicking":15,"overwhelmed":15,
    "bitter":20,"frustrated":20,"stressed":20,"deflated":20,
    "anxious":25,"nervous":25,"tense":25,"worried":25,
    "embarrassed":25,"disapproving":25,
    "cautious":30,"concerned":30,"uncertain":30,"defensive":30,
    "shocked":30,"apologetic":30,"stern":35,"serious":40,
    "matter-of-fact":40,"firm":40,
    "professional":50,"businesslike":50,"relenting":50,
    "negotiating":50,"informative":50,"practical":50,
    "surprised":50,"modest":50,"neutral":50,
    "calm":60,"teaching":60,"diplomatic":60,"kind":65,
    "understanding":65,"casual":60,"reassuring":70,
    "encouraging":70,"friendly":70,"impressed":65,
    "hopeful":70,"supportive":70,"wise":70,
    "eager":75,"excited":80,"determined":80,
    "grateful":80,"satisfied":85,"proud":75,
    "confident":85,"triumphant":90,
}

EMOTION_ZH = {
    "nervous":"紧张","anxious":"焦虑","friendly":"友好","relieved":"放松",
    "casual":"随和","encouraging":"受鼓舞","embarrassed":"尴尬",
    "understanding":"理解","surprised":"惊讶","reassuring":"安心",
    "earnest":"认真","modest":"谦虚","eager":"热切","impressed":"赞赏",
    "uncertain":"不确定","worried":"担忧","concerned":"关切","tense":"紧张",
    "serious":"严肃","cautious":"谨慎","stressed":"压力",
    "overwhelmed":"不安","shocked":"震惊","frustrated":"沮丧",
    "determined":"坚定","grateful":"感激","professional":"专业",
    "teaching":"教导","apologetic":"抱歉","defensive":"防御",
    "deflated":"泄气","crushed":"崩溃","dejected":"沮丧",
    "bitter":"苦涩","confused":"困惑","wise":"智慧",
    "supportive":"支持","satisfied":"满意","hopeful":"希望",
    "excited":"兴奋","proud":"自豪","diplomatic":"委婉",
    "firm":"坚决","disapproving":"不满","negotiating":"协商",
    "stern":"严厉","relenting":"让步","kind":"友善",
    "calm":"冷静","panicking":"恐慌",
}

def get_emotion_val(emotion_str):
    if not emotion_str:
        return 50
    e = emotion_str.lower()
    for key, val in sorted(EMOTION_VAL.items(), key=lambda x: -len(x[0])):
        if key in e:
            return val
    return 50

def get_emotion_zh(emotion_str):
    if not emotion_str:
        return ""
    e = emotion_str.lower()
    for key, zh in sorted(EMOTION_ZH.items(), key=lambda x: -len(x[0])):
        if key in e:
            return zh
    return emotion_str[:4]

def generate_arc_svg(chapter_num, pages):
    if not pages:
        return ""
    n = len(pages)
    # 用每页最后一句对话的情感作为该页的情感终点
    page_vals = []
    page_labels = []
    for page in pages:
        dialogues = page.get("dialogues", [])
        # 取最后一句对话的情感
        if dialogues:
            last_emotion = dialogues[-1].get("emotion", "")
            val = get_emotion_val(last_emotion)
            page_labels.append(get_emotion_zh(last_emotion))
        else:
            val = 50
            page_labels.append("")
        page_vals.append(max(10, min(90, val)))

    # SVG坐标
    xs = [100 + i * (360 / max(n - 1, 1)) for i in range(n)]
    ys = [95 - (v / 100 * 80) for v in page_vals]

    # 构建贝塞尔路径
    if n == 1:
        path = f"M {xs[0]},{ys[0]}"
    elif n >= 2:
        segs = [f"M {xs[0]},{ys[0]}"]
        for i in range(n - 1):
            dx = (xs[i+1] - xs[i]) / 3
            segs.append(f"C {xs[i]+dx},{ys[i]} {xs[i+1]-dx},{ys[i+1]} {xs[i+1]},{ys[i+1]}")
        path = " ".join(segs)
    else:
        path = ""

    fill_path = f"{path} L {xs[-1]},95 L {xs[0]},95 Z"
    aid = f"arc{chapter_num}"

    svg_parts = [f'<div class="arc-container">',
        f'<div class="arc-label">情感曲线 EMOTIONAL ARC</div>',
        f'<svg viewBox="0 0 560 130" width="100%" xmlns="http://www.w3.org/2000/svg" style="overflow:visible">',
        f'<defs><linearGradient id="{aid}" x1="0" y1="0" x2="0" y2="1">',
        f'<stop offset="0%" stop-color="#e94560" stop-opacity="0.35"/>',
        f'<stop offset="100%" stop-color="#e94560" stop-opacity="0.03"/>',
        f'</linearGradient></defs>',
        f'<line x1="70" y1="15" x2="500" y2="15" stroke="#222" stroke-dasharray="4,4"/>',
        f'<line x1="70" y1="55" x2="500" y2="55" stroke="#222" stroke-dasharray="4,4"/>',
        f'<line x1="70" y1="95" x2="500" y2="95" stroke="#222" stroke-dasharray="4,4"/>',
        f'<text x="60" y="19" fill="#444" font-size="8" text-anchor="end">积极</text>',
        f'<text x="60" y="59" fill="#444" font-size="8" text-anchor="end">中性</text>',
        f'<text x="60" y="99" fill="#444" font-size="8" text-anchor="end">消极</text>',
        f'<path d="{fill_path}" fill="url(#{aid})"/>',
        f'<path d="{path}" fill="none" stroke="#e94560" stroke-width="2.5" stroke-linecap="round"/>']

    for i in range(n):
        svg_parts.append(f'<circle cx="{xs[i]}" cy="{ys[i]}" r="5" fill="#e94560" stroke="#1a1a2e" stroke-width="2"/>')

    for i in range(n):
        ly = ys[i] - 11
        if ly < 5:
            ly = ys[i] + 18
        svg_parts.append(f'<text x="{xs[i]}" y="{ly}" fill="#fff" font-size="11" text-anchor="middle" font-weight="600">{page_labels[i]}</text>')

    for i in range(n):
        pg = pages[i].get("page_number", i+1)
        svg_parts.append(f'<text x="{xs[i]}" y="115" fill="#666" font-size="10" text-anchor="middle">第{pg}页</text>')

    svg_parts.append('</svg></div>')
    return "\n".join(svg_parts)

story = final["story"]
characters = story.get("characters", [])

# 构建HTML
html_parts = []
def w(s=""): html_parts.append(s)

w(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{story['title']} - 漫剧预览</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'Segoe UI',sans-serif;background:#0f0f0f;color:#e0e0e0}}
.header{{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:40px;text-align:center;border-bottom:2px solid #e94560}}
.header h1{{font-size:32px;color:#fff;margin-bottom:8px}}
.header h2{{font-size:20px;color:#aaa;font-weight:normal;text-align:center}}
.header .meta{{margin-top:16px;display:flex;justify-content:center;gap:20px;flex-wrap:wrap;text-align:left}}
.header .meta span{{background:#e94560;color:#fff;padding:4px 12px;border-radius:12px;font-size:13px}}
.characters{{display:flex;gap:16px;padding:24px 40px;overflow-x:auto;background:#1a1a1a}}
.char-card{{background:#252540;border-radius:12px;padding:16px;min-width:200px;border:1px solid #333}}
.char-card .role{{color:#e94560;font-size:12px;text-transform:uppercase;letter-spacing:1px}}
.char-card .name{{font-size:18px;font-weight:bold;color:#fff;margin:4px 0}}
.char-card .name-en{{color:#888;font-size:13px}}
.char-card .desc{{color:#aaa;font-size:12px;margin-top:8px;line-height:1.5}}
.chapter{{margin:32px auto;max-width:1200px;text-align:center}}
.chapter-title{{font-size:24px;color:#e94560;margin-bottom:4px;text-align:center}}
.chapter-title-en{{font-size:14px;color:#666;margin-bottom:8px;text-align:center}}
.chapter-summary{{color:#aaa;font-size:14px;margin-bottom:24px;line-height:1.6;padding:12px 16px;background:#1a1a2e;border-radius:8px;border-left:3px solid #e94560;text-align:left}}
.chapter-arc{{margin-bottom:16px;text-align:center}}
.arc-container{{background:#111;border-radius:8px;padding:12px 16px;border:1px solid #2a2a4a;text-align:left}}
.arc-label{{color:#888;font-size:11px;margin-bottom:6px;letter-spacing:1px}}
.page{{display:block;width:100%;max-width:1200px;margin-left:auto;margin-right:auto;margin-bottom:40px;background:#1a1a2e;border-radius:16px;padding:24px;border:1px solid #2a2a4a}}
.page-body{{display:flex;gap:24px;width:100%;max-width:1152px}}
.page-img{{flex-shrink:0;width:220px;display:flex;flex-direction:column}}
.page-img img{{width:100%;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,0.5)}}
.page-img .page-num{{text-align:center;color:#e94560;font-weight:bold;margin-bottom:8px;font-size:14px}}
.page-img .scene{{color:#888;font-size:11px;text-align:center;margin-top:8px;line-height:1.4}}
.page-right{{flex:1;min-width:0;max-width:880px;overflow:hidden}}
.prompt-section{{margin-bottom:16px}}
.prompt-label{{color:#e94560;font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}}
.prompt-text{{color:#aaa;font-size:12px;background:#111;padding:10px 14px;border-radius:6px;line-height:1.5;font-family:monospace;white-space:pre-wrap;word-break:break-word}}
.prompt-text-zh{{color:#888;font-size:12px;background:#0d0d1a;padding:8px 14px;border-radius:6px;line-height:1.5;margin-top:6px;font-family:-apple-system,sans-serif;white-space:pre-wrap;word-break:break-word;border-left:2px solid #e94560}}
.vocab{{margin-top:12px;display:flex;gap:6px;flex-wrap:wrap}}
.vocab span{{background:#252540;color:#aaa;padding:2px 8px;border-radius:4px;font-size:11px;border:1px solid #333}}
.dialogues-section{{}}
.dialogues-title{{color:#fff;font-size:14px;font-weight:bold;margin-bottom:12px;padding-bottom:6px;border-bottom:1px solid #333}}
.dialogues-grid{{display:grid;grid-template-columns:1fr 1fr;gap:5px 12px;min-width:0;overflow:hidden}}
.dlg{{display:flex;gap:8px;padding:6px 10px;background:#111;border-radius:6px;min-width:0}}
.dlg:hover{{background:#1a1a3a}}
.dlg-speaker{{color:#e94560;font-weight:bold;min-width:50px;font-size:12px;flex-shrink:0}}
.dlg-body{{flex:1;min-width:0}}
.dlg-body{{flex:1;min-width:0}}
.dlg-zh{{color:#ddd;font-size:13px;overflow-wrap:break-word;word-break:break-word;min-width:0}}
.dlg-en{{color:#888;font-size:11px;margin-top:1px;overflow-wrap:break-word;word-break:break-word;min-width:0}}
.footer{{text-align:center;padding:32px;color:#555;font-size:12px;border-top:1px solid #222;margin-top:40px}}
</style>
</head>
<body>
<div class="header">
  <h1>{story['title']}</h1>
  <h2>{story.get('title_en','')}</h2>
  <div class="meta">
    <span>{story.get('genre','').upper()}</span>
    <span>{story.get('language_level','')}</span>
    <span>{story.get('total_chapters',0)} 章</span>
    <span>{story.get('total_pages',0)} 页</span>
    <span>约 {story.get('estimated_practice_time','')}</span>
  </div>
</div>
<div class="characters">""")

for c in characters:
    personality = ", ".join(c.get("personality",[]))
    w(f"""  <div class="char-card">
    <div class="role">{c.get('role','')}</div>
    <div class="name">{c['name']}</div>
    <div class="name-en">{c.get('name_en','')}</div>
    <div class="desc">{c.get('visual_description','')}<br><br>{personality}</div>
  </div>""")

w("</div>")

for chapter in story.get("chapters",[]):
    ch_num = chapter["chapter_number"]
    w(f"""<div class="chapter">
  <div class="chapter-title">第{ch_num}章：{chapter['title']}</div>
  <div class="chapter-title-en">Chapter {ch_num}: {chapter.get('title_en','')}</div>
  <div class="chapter-arc">
    {generate_arc_svg(ch_num, chapter.get('pages',[]))}
  </div>
  <div class="chapter-summary">{chapter.get('summary','')}</div>""")

    for page in chapter.get("pages",[]):
        pg_num = page["page_number"]
        img_path = f"{task_dir}/images/chapter{ch_num}_page{pg_num}.png"
        img_b64 = img_to_base64(img_path)
        img_tag = f'<img src="data:image/png;base64,{img_b64}">' if img_b64 else '<div style="width:100%;height:300px;background:#222;display:flex;align-items:center;justify-content:center;color:#555;border-radius:8px">无图片</div>'

        prompt_en = prompts.get((ch_num,pg_num), page.get("image_prompt",""))
        prompt_zh = prompts_zh.get((ch_num,pg_num), page.get("image_prompt_zh", ""))
        if not prompt_zh:
            prompt_zh = "【缺少中文图片提示词】请在分镜 JSON 中补充 storyboard.image_prompt_zh，并重新运行 save_prompts.sh。"
        vocab_focus = page.get("vocabulary_focus",[])
        dialogues = page.get("dialogues",[])

        w(f"""  <div class="page">
    <div class="page-body">
      <div class="page-img">
        <div class="page-num">第 {pg_num} 页</div>
        {img_tag}
        <div class="scene">{page.get('scene_location','')}<br>{page.get('time','')} | {page.get('weather','')}</div>
      </div>
      <div class="page-right">
        <div class="prompt-section">
          <div class="prompt-label">提示词 / Prompt</div>
          <div class="prompt-text">{esc(prompt_en)}</div>
          <div class="prompt-text-zh">{esc(prompt_zh)}</div>
        </div>""")

        if vocab_focus:
            w('        <div class="vocab"><span style="color:#e94560;font-size:11px">词汇重点：</span>')
            for v in vocab_focus:
                w(f"<span>{v}</span>")
            w("        </div>")

        w(f"""        <div class="dialogues-section">
          <div class="dialogues-title">对话 ({len(dialogues)} 句)</div>
          <div class="dialogues-grid">""")

        for dlg in dialogues:
            w(f"""          <div class="dlg">
            <div class="dlg-speaker">{dlg.get('speaker_en',dlg.get('speaker',''))}</div>
            <div class="dlg-body">
              <div class="dlg-zh">{dlg.get('text_zh','')}</div>
              <div class="dlg-en">{dlg.get('text_en','')}</div>
            </div>
          </div>""")

        w("""        </div>
        </div>
      </div>
    </div>
  </div>
</div>""")

    w("</div>")

w(f"""
<div class="footer">
  {story['title']} · 生成时间：2026-04-25 · Scene2Talk 漫剧预览
</div>
</body>
</html>""")

output_path = f"{task_dir}/output/preview.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(html_parts))

size_mb = os.path.getsize(output_path) / 1024 / 1024
print(f"✅ HTML预览页面已生成: {output_path}")
print(f"   文件大小: {size_mb:.1f} MB")
PYEOF

# 在浏览器中打开
open "$TASK_DIR/output/preview.html"
