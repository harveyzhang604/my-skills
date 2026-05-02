#!/usr/bin/env python3
"""
自动生成A1级别的章节剧本
"""
import json
import sys
from pathlib import Path

def generate_simple_dialogues(page_num, scene_type, characters):
    """生成A1级别的简单对话"""
    dialogues = []

    # 根据场景类型生成不同的对话
    if scene_type == "dream":
        dialogues = [
            {"speaker": "旁白", "speaker_en": "Narrator", "text_zh": f"{characters[0]}在睡觉。", "text_en": f"{characters[0]} is sleeping."},
            {"speaker": "神秘声音", "speaker_en": "Voice", "text_zh": "来...来这里...", "text_en": "Come... come here...", "emotion": "神秘"},
            {"speaker": characters[0], "speaker_en": characters[0], "text_zh": "什么？", "text_en": "What?", "emotion": "困惑"},
            {"speaker": "神秘声音", "speaker_en": "Voice", "text_zh": "森林之心...", "text_en": "Heart of Forest...", "emotion": "神秘"},
            {"speaker": characters[0], "speaker_en": characters[0], "text_zh": "啊！", "text_en": "Ah!", "emotion": "惊恐"},
            {"speaker": "旁白", "speaker_en": "Narrator", "text_zh": f"{characters[0]}醒了。", "text_en": f"{characters[0]} wakes up."},
        ]
    elif scene_type == "meet":
        dialogues = [
            {"speaker": characters[0], "speaker_en": characters[0], "text_zh": "你好。", "text_en": "Hello.", "emotion": "谨慎"},
            {"speaker": characters[1], "speaker_en": characters[1], "text_zh": "你好。", "text_en": "Hello.", "emotion": "警觉"},
            {"speaker": characters[0], "speaker_en": characters[0], "text_zh": "你也来了？", "text_en": "You came too?", "emotion": "惊讶"},
            {"speaker": characters[1], "speaker_en": characters[1], "text_zh": "是的。", "text_en": "Yes.", "emotion": "点头"},
            {"speaker": characters[0], "speaker_en": characters[0], "text_zh": "为什么？", "text_en": "Why?", "emotion": "疑惑"},
            {"speaker": characters[1], "speaker_en": characters[1], "text_zh": "我不知道。", "text_en": "I don't know.", "emotion": "摇头"},
        ]
    elif scene_type == "discover":
        dialogues = [
            {"speaker": characters[0], "speaker_en": characters[0], "text_zh": "看！", "text_en": "Look!", "emotion": "兴奋"},
            {"speaker": characters[1], "speaker_en": characters[1], "text_zh": "什么？", "text_en": "What?", "emotion": "好奇"},
            {"speaker": characters[0], "speaker_en": characters[0], "text_zh": "这里有光。", "text_en": "There is light here.", "emotion": "指着"},
            {"speaker": characters[1], "speaker_en": characters[1], "text_zh": "真的！", "text_en": "Really!", "emotion": "惊讶"},
            {"speaker": characters[0], "speaker_en": characters[0], "text_zh": "我们进去吗？", "text_en": "Do we go in?", "emotion": "犹豫"},
            {"speaker": characters[1], "speaker_en": characters[1], "text_zh": "好的。", "text_en": "OK.", "emotion": "点头"},
        ]
    else:  # action
        dialogues = [
            {"speaker": characters[0], "speaker_en": characters[0], "text_zh": "快！", "text_en": "Quick!", "emotion": "着急"},
            {"speaker": characters[1], "speaker_en": characters[1], "text_zh": "我来了！", "text_en": "I'm coming!", "emotion": "跑"},
            {"speaker": characters[0], "speaker_en": characters[0], "text_zh": "小心！", "text_en": "Be careful!", "emotion": "警告"},
            {"speaker": characters[1], "speaker_en": characters[1], "text_zh": "好的！", "text_en": "OK!", "emotion": "点头"},
            {"speaker": "旁白", "speaker_en": "Narrator", "text_zh": "他们一起行动。", "text_en": "They act together."},
        ]

    return dialogues

def generate_chapter(chapter_num, story_outline):
    """生成一个章节的完整剧本"""
    chapter_outline = story_outline['story']['chapter_outlines'][chapter_num - 1]

    chapter = {
        "chapter_number": chapter_num,
        "title": chapter_outline['title'],
        "title_en": chapter_outline['title_en'],
        "summary": chapter_outline['summary'],
        "pages": []
    }

    # 生成24页
    characters = ["Bart", "Ah Ling", "Xiao Jin", "Da Da", "Duo Duo"]
    scene_types = ["dream", "meet", "discover", "action"]

    for page_num in range(1, 25):
        scene_type = scene_types[(page_num - 1) % len(scene_types)]
        page_chars = [characters[(page_num - 1) % len(characters)],
                     characters[(page_num) % len(characters)]]

        page = {
            "page_number": page_num,
            "page_title": f"Page {page_num}",
            "scene_location": "Forest",
            "time": "Day" if page_num % 2 == 0 else "Night",
            "weather": "Clear",
            "emotional_arc": "Calm → Excited",
            "vocabulary_focus": ["hello", "come", "look", "go"],
            "dialogues": generate_simple_dialogues(page_num, scene_type, page_chars)
        }

        chapter['pages'].append(page)

    return chapter

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_chapters_a1.py <task_dir>")
        sys.exit(1)

    task_dir = Path(sys.argv[1])
    story_file = task_dir / "data" / "story_outline.json"

    # 读取故事大纲
    with open(story_file, 'r', encoding='utf-8') as f:
        story_outline = json.load(f)

    # 生成8章
    for chapter_num in range(1, 9):
        print(f"📝 正在生成第{chapter_num}章...")
        chapter = generate_chapter(chapter_num, story_outline)

        output_file = task_dir / "scripts" / f"chapter{chapter_num}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chapter, f, ensure_ascii=False, indent=2)

        print(f"✅ 第{chapter_num}章完成！")

    print("\n🎉 所有章节生成完成！")

if __name__ == "__main__":
    main()
