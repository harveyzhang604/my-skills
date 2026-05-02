#!/usr/bin/env python3
"""
生成故事脉络和角色卡片图
在批量筛选后、详细剧本前执行
"""

import json
import sys
from pathlib import Path
from llm_json_client import LLMJSONClient

def generate_story_arc(task_dir: str) -> dict:
    """生成故事脉络（8个主要章节的情节发展）"""

    outline_path = Path(task_dir) / 'data' / 'story_outline.json'
    with open(outline_path, 'r', encoding='utf-8') as f:
        outline = json.load(f)

    story = outline.get('story', {})

    prompt = f"""基于以下故事大纲，生成详细的故事脉络（Story Arc）。

**故事信息**：
- 标题：{story.get('title')} / {story.get('title_en')}
- 类型：{story.get('genre')}
- 章节数：{story.get('total_chapters')}

**故事梗概**：
{story.get('summary')}

**章节大纲**：
{json.dumps(story.get('chapter_outlines', []), ensure_ascii=False, indent=2)}

请生成故事脉络，包含每个章节的：
1. 章节标题（中英文）
2. 核心事件（2-3句话）
3. 关键转折点
4. 情感基调

参考格式（猴子警长示例）：
1. 反物质爆炸与沉睡（故事起因）
   为了争夺被熊猫大侠带走的盒子，斑马经理设下陷阱困住猴子警长一行...

返回 JSON：
{{
  "story_arc": [
    {{
      "chapter": 1,
      "title": "章节标题",
      "title_en": "Chapter Title",
      "core_events": "核心事件描述（2-3句话）",
      "key_turning_point": "关键转折点",
      "emotional_tone": "情感基调"
    }}
  ]
}}
"""

    client = LLMJSONClient()
    result = client.call(prompt, response_format={"type": "json_object"})

    if not result:
        return {"error": "LLM 调用失败"}

    return result


def generate_character_cards(task_dir: str) -> dict:
    """生成角色卡片图数据"""

    outline_path = Path(task_dir) / 'data' / 'story_outline.json'
    with open(outline_path, 'r', encoding='utf-8') as f:
        outline = json.load(f)

    story = outline.get('story', {})
    characters = story.get('characters', [])

    prompt = f"""基于以下角色信息，生成角色卡片数据。

**故事标题**：{story.get('title')}

**角色列表**：
{json.dumps(characters, ensure_ascii=False, indent=2)}

请为每个角色生成卡片信息：
1. 角色名称（中英文）
2. 简短描述（1-2句话，突出性格特点或关键作用）
3. 阵营分类（主角团队/反派/中立/支援）
4. 视觉描述（用于生成角色头像）

参考格式（猴子警长示例）：
- 猴子警长：森林都市的守护者，打击犯罪的英雄。
- 小鸡敦敦：为成为警察而努力的三黄鸡小鸡。
- 斑马经理：曾加入破坏者联盟，打算过森林都市的防护罩。

返回 JSON：
{{
  "character_cards": [
    {{
      "name": "角色名",
      "name_en": "Character Name",
      "description": "简短描述（1-2句话）",
      "faction": "主角团队/反派/中立/支援",
      "visual_description": "外观描述，用于生成头像图片",
      "image_prompt": "英文图片提示词：portrait of [character], [style], character design"
    }}
  ],
  "factions": {{
    "heroes": ["主角团队角色名列表"],
    "villains": ["反派角色名列表"],
    "neutral": ["中立角色名列表"],
    "support": ["支援角色名列表"]
  }}
}}
"""

    client = LLMJSONClient()
    result = client.call(prompt, response_format={"type": "json_object"})

    if not result:
        return {"error": "LLM 调用失败"}

    return result


def save_story_arc_and_cards(task_dir: str):
    """生成并保存故事脉络和角色卡片"""

    print(f"📖 生成故事脉络...")
    story_arc = generate_story_arc(task_dir)

    arc_path = Path(task_dir) / 'data' / 'story_arc.json'
    with open(arc_path, 'w', encoding='utf-8') as f:
        json.dump(story_arc, f, ensure_ascii=False, indent=2)

    print(f"   ✓ 故事脉络已保存：{arc_path}")

    print(f"\n🎭 生成角色卡片...")
    character_cards = generate_character_cards(task_dir)

    cards_path = Path(task_dir) / 'data' / 'character_cards.json'
    with open(cards_path, 'w', encoding='utf-8') as f:
        json.dump(character_cards, f, ensure_ascii=False, indent=2)

    print(f"   ✓ 角色卡片已保存：{cards_path}")

    # 生成角色头像提示词文件
    prompts_dir = Path(task_dir) / 'character_prompts'
    prompts_dir.mkdir(exist_ok=True)

    for card in character_cards.get('character_cards', []):
        name_en = card.get('name_en', '').replace(' ', '_')
        prompt_file = prompts_dir / f"{name_en}.txt"

        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(card.get('image_prompt', ''))

    print(f"   ✓ 角色头像提示词已保存：{prompts_dir}")

    # 打印摘要
    print(f"\n" + "="*60)
    print(f"📊 故事脉络和角色卡片生成完成")
    print(f"="*60)

    print(f"\n📖 故事脉络（{len(story_arc.get('story_arc', []))} 个章节）：")
    for arc in story_arc.get('story_arc', []):
        print(f"   {arc.get('chapter')}. {arc.get('title')}")

    print(f"\n🎭 角色卡片（{len(character_cards.get('character_cards', []))} 个角色）：")
    factions = character_cards.get('factions', {})
    print(f"   主角团队：{len(factions.get('heroes', []))} 个")
    print(f"   反派：{len(factions.get('villains', []))} 个")
    print(f"   中立：{len(factions.get('neutral', []))} 个")
    print(f"   支援：{len(factions.get('support', []))} 个")

    print(f"\n📁 输出文件：")
    print(f"   - {arc_path}")
    print(f"   - {cards_path}")
    print(f"   - {prompts_dir}/ (角色头像提示词)")

    print(f"\n💡 下一步：")
    print(f"   1. 查看故事脉络和角色卡片")
    print(f"   2. 生成角色头像图片（可选）")
    print(f"   3. 继续生成详细剧本")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法：python3 generate_story_arc_and_cards.py <task_dir>")
        sys.exit(1)

    task_dir = sys.argv[1]
    save_story_arc_and_cards(task_dir)
