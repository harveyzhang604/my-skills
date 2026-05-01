#!/usr/bin/env python3
"""
剧本大纲评分脚本
使用 LLM 对故事大纲进行多维度评分
"""

import json
import sys
from pathlib import Path
from llm_json_client import LLMJSONClient

def score_story_outline(outline_path: str) -> dict:
    """评分单个故事大纲"""

    with open(outline_path, 'r', encoding='utf-8') as f:
        outline = json.load(f)

    story = outline.get('story', {})

    # 构建评分提示词
    prompt = f"""请对以下故事大纲进行专业评分（0-10分）：

**故事信息**：
- 标题：{story.get('title')} / {story.get('title_en')}
- 类型：{story.get('genre')}
- 语言难度：{story.get('language_level')}
- 章节数：{story.get('total_chapters')}

**故事梗概**：
{story.get('logline')}

{story.get('summary')}

**角色设定**：
{json.dumps([{{
    'name': c.get('name'),
    'role': c.get('role'),
    'personality': c.get('personality')
}} for c in story.get('characters', [])], ensure_ascii=False, indent=2)}

**章节大纲**：
{json.dumps([{{
    'chapter': i+1,
    'title': ch.get('title'),
    'summary': ch.get('summary')
}} for i, ch in enumerate(story.get('chapter_outlines', []))], ensure_ascii=False, indent=2)}

请从以下维度评分（每项0-10分）：

1. **故事吸引力** (story_appeal)：情节是否引人入胜，有悬念和转折
2. **角色设定** (character_design)：角色是否立体，性格鲜明，关系有张力
3. **冲突设计** (conflict_design)：是否有清晰的冲突递进，压力升级合理
4. **口语练习适配度** (speaking_practice_fit)：对话场景是否自然，适合口语练习
5. **情感曲线** (emotional_arc)：情感变化是否流畅，有起伏和高潮
6. **职场真实性** (workplace_realism)：（如果是职场类）场景和流程是否真实可信
7. **创意新颖度** (originality)：故事是否有新意，避免俗套

请返回 JSON 格式：
{{
  "scores": {{
    "story_appeal": 8.5,
    "character_design": 7.0,
    "conflict_design": 8.0,
    "speaking_practice_fit": 9.0,
    "emotional_arc": 7.5,
    "workplace_realism": 8.5,
    "originality": 7.0
  }},
  "total_score": 55.5,
  "average_score": 7.93,
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["不足1", "不足2"],
  "recommendation": "推荐/不推荐/需改进",
  "brief_comment": "一句话总评"
}}
"""

    client = LLMJSONClient()
    result = client.call(prompt, response_format={"type": "json_object"})

    if not result:
        return {
            "error": "LLM 调用失败",
            "scores": {},
            "total_score": 0,
            "average_score": 0
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
