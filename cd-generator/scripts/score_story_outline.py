#!/usr/bin/env python3
"""
剧本大纲评分脚本
使用 LLM 对故事大纲进行多维度评分
"""

import json
import sys
from pathlib import Path
from llm_json_client import OpenAICompatibleJSONClient

def score_story_outline(outline_path: str) -> dict:
    """评分单个故事大纲"""

    with open(outline_path, 'r', encoding='utf-8') as f:
        outline = json.load(f)

    story = outline.get('story', {})

    # 构建评分数据
    characters = [
        {'name': c.get('name'), 'role': c.get('role'), 'personality': c.get('personality')}
        for c in story.get('characters', [])
    ]

    chapters = [
        {'chapter': i+1, 'title': ch.get('title'), 'summary': ch.get('summary')}
        for i, ch in enumerate(story.get('chapter_outlines', []))
    ]

    scoring_prompt = f"""请对以下故事大纲进行专业评分（0-10分）：

**故事信息**：
- 标题：{story.get('title')} / {story.get('title_en')}
- 类型：{story.get('genre')}
- 语言难度：{story.get('language_level')}
- 章节数：{story.get('total_chapters')}

**故事梗概**：
{story.get('logline')}

{story.get('summary')}

**角色设定**：
{json.dumps(characters, ensure_ascii=False, indent=2)}

**章节大纲**：
{json.dumps(chapters, ensure_ascii=False, indent=2)}

请从以下维度严格评分（每项0-10分）：

1. **故事吸引力** (story_appeal)：开头是否抓人、情节是否紧凑、有无意外转折（9-10分=优秀，7-8分=良好，5-6分=及格，0-4分=不及格）
2. **角色深度** (character_depth)：角色是否立体、有背景故事、性格复杂、动机清晰
3. **角色成长** (character_growth)：主角是否有明显的成长弧线和内心变化
4. **冲突层次** (conflict_layers)：是否有多层次冲突（外部威胁+内部矛盾+人际冲突）
5. **情感共鸣** (emotional_resonance)：是否能引发情感共鸣、情感转折是否自然有力
6. **世界观构建** (world_building)：背景设定是否丰富、有独特性、细节充实
7. **创意新颖度** (originality)：是否避免俗套、有独特创意、让人眼前一亮
8. **对话自然度** (dialogue_quality)：对话是否符合角色、生动自然、适合口语练习
9. **节奏把控** (pacing)：8章节奏是否合理、有张有弛、高潮设置恰当
10. **主题深度** (theme_depth)：是否有深刻主题、给人启发、不仅仅是娱乐

**评分要严格**：大部分故事应该在6-8分区间，只有真正优秀的故事才能达到9分以上。

请返回 JSON 格式：
{{
  "scores": {{
    "story_appeal": 7.5,
    "character_depth": 6.5,
    "character_growth": 7.0,
    "conflict_layers": 6.0,
    "emotional_resonance": 7.0,
    "world_building": 6.5,
    "originality": 6.0,
    "dialogue_quality": 7.5,
    "pacing": 7.0,
    "theme_depth": 6.5
  }},
  "total_score": 67.5,
  "average_score": 6.75,
  "strengths": ["具体优点1", "具体优点2", "具体优点3"],
  "weaknesses": ["具体不足1", "具体不足2", "具体不足3"],
  "recommendation": "推荐/不推荐/需改进",
  "brief_comment": "一句话总评"
}}"""

    try:
        client = OpenAICompatibleJSONClient()
        result = client.request_json("generic_scoring", {
            "story_title": story.get('title'),
            "story_genre": story.get('genre'),
            "prompt": scoring_prompt
        })
    except Exception as e:
        print(f"   ⚠️ LLM 调用失败: {e}")
        # 返回默认分数
        result = {
            "scores": {
                "story_appeal": 6.0,
                "character_depth": 6.0,
                "character_growth": 6.0,
                "conflict_layers": 6.0,
                "emotional_resonance": 6.0,
                "world_building": 6.0,
                "originality": 6.0,
                "dialogue_quality": 6.0,
                "pacing": 6.0,
                "theme_depth": 6.0
            },
            "total_score": 60.0,
            "average_score": 6.0,
            "strengths": ["故事结构完整"],
            "weaknesses": ["未能评分"],
            "recommendation": "需改进",
            "brief_comment": "LLM调用失败，使用默认分数"
        }

    # 添加故事基本信息
    result['story_info'] = {
        'title': story.get('title'),
        'title_en': story.get('title_en'),
        'genre': story.get('genre'),
        'language_level': story.get('language_level')
    }

    return result


def batch_score_outlines(task_dirs: list) -> list:
    """批量评分多个故事大纲"""

    results = []

    for task_dir in task_dirs:
        outline_path = Path(task_dir) / 'data' / 'story_outline.json'

        if not outline_path.exists():
            print(f"⚠️  {task_dir}: 未找到 story_outline.json")
            continue

        print(f"📊 评分中: {task_dir}")
        score_result = score_story_outline(str(outline_path))

        # 保存评分结果
        score_path = Path(task_dir) / 'data' / 'story_score.json'
        with open(score_path, 'w', encoding='utf-8') as f:
            json.dump(score_result, f, ensure_ascii=False, indent=2)

        results.append({
            'task_dir': task_dir,
            'score': score_result
        })

        # 打印简要结果
        avg = score_result.get('average_score', 0)
        rec = score_result.get('recommendation', 'N/A')
        comment = score_result.get('brief_comment', '')
        print(f"   ✓ 平均分: {avg:.2f}/10 | {rec} | {comment}\n")

    return results


def generate_comparison_report(results: list, output_path: str):
    """生成对比报告"""

    # 按平均分排序
    sorted_results = sorted(
        results,
        key=lambda x: x['score'].get('average_score', 0),
        reverse=True
    )

    report = {
        'total_stories': len(results),
        'ranking': [],
        'top_recommendations': []
    }

    for i, item in enumerate(sorted_results, 1):
        score = item['score']
        info = score.get('story_info', {})

        ranking_item = {
            'rank': i,
            'task_dir': item['task_dir'],
            'title': info.get('title'),
            'title_en': info.get('title_en'),
            'average_score': score.get('average_score', 0),
            'recommendation': score.get('recommendation'),
            'brief_comment': score.get('brief_comment'),
            'scores': score.get('scores', {})
        }

        report['ranking'].append(ranking_item)

        # 推荐前2名
        if i <= 2 and score.get('average_score', 0) >= 7.0:
            report['top_recommendations'].append(ranking_item)

    # 保存报告
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 打印报告
    print("\n" + "="*60)
    print("📊 剧本评分对比报告")
    print("="*60 + "\n")

    for item in report['ranking']:
        print(f"🏆 第 {item['rank']} 名：{item['title']} / {item['title_en']}")
        print(f"   平均分：{item['average_score']:.2f}/10")
        print(f"   推荐度：{item['recommendation']}")
        print(f"   评价：{item['brief_comment']}")
        print(f"   目录：{item['task_dir']}")
        print()

    if report['top_recommendations']:
        print("\n✨ 推荐继续开发的剧本：")
        for item in report['top_recommendations']:
            print(f"   • {item['title']} (平均分 {item['average_score']:.2f})")
    else:
        print("\n⚠️  没有达到推荐标准（≥7.0分）的剧本")

    print(f"\n📄 详细报告已保存：{output_path}\n")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法：")
        print("  单个评分：python3 score_story_outline.py <task_dir>")
        print("  批量评分：python3 score_story_outline.py <task_dir1> <task_dir2> ...")
        sys.exit(1)

    task_dirs = sys.argv[1:]

    if len(task_dirs) == 1:
        # 单个评分
        outline_path = Path(task_dirs[0]) / 'data' / 'story_outline.json'
        result = score_story_outline(str(outline_path))

        # 保存结果
        score_path = Path(task_dirs[0]) / 'data' / 'story_score.json'
        with open(score_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 批量评分
        results = batch_score_outlines(task_dirs)

        # 生成对比报告
        output_dir = Path(task_dirs[0]).parent
        report_path = output_dir / 'batch_score_comparison.json'
        generate_comparison_report(results, str(report_path))