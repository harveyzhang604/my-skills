# cd-generator 批量生成和评分功能

## 新增功能

### 1. 剧本评分系统

**脚本**：`scripts/score_story_outline.py`

**功能**：使用 LLM 对故事大纲进行多维度评分

**评分维度**（每项 0-10 分）：
- 故事吸引力 (story_appeal)
- 角色设定 (character_design)
- 冲突设计 (conflict_design)
- 口语练习适配度 (speaking_practice_fit)
- 情感曲线 (emotional_arc)
- 职场真实性 (workplace_realism)
- 创意新颖度 (originality)

**使用方法**：

```bash
# 单个故事评分
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/score_story_outline.py <task_dir>

# 批量评分（生成对比报告）
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/score_story_outline.py <task_dir1> <task_dir2> <task_dir3> ...
```

**输出**：
- 单个评分：`<task_dir>/data/story_score.json`
- 批量对比：`<output_base>/batch_score_comparison.json`

### 2. 批量生成故事大纲

**脚本**：`scripts/batch_generate_outlines.sh`

**功能**：批量生成多个故事大纲变体，用于对比和选择

**使用方法**：

```bash
/Users/zhanghua/.claude/skills/cd-generator/scripts/batch_generate_outlines.sh \
  --theme "设计师的第一步" \
  --batch-size 10 \
  --genre workplace \
  --level B1 \
  --chapters 6 \
  --pages 24
```

**参数**：
- `--theme`：故事主题（必需）
- `--batch-size`：生成数量（默认 10）
- `--genre`：类型（默认 workplace）
- `--level`：语言难度（默认 B1）
- `--chapters`：章节数（默认 6）
- `--pages`：每章页数（默认 24）

**工作流程**：
1. 创建批次目录
2. 为每个变体创建任务目录
3. 调用 `scripts/generate_outline_with_llm.py` 自动生成 `data/story_outline.json`
4. 保留 `data/outline_request.txt` 作为人工复核和失败重试参考
5. 保存批次信息

### 3. 完整批量工作流

```bash
# 步骤 1：批量生成故事大纲
./scripts/batch_generate_outlines.sh \
  --theme "职场新人成长" \
  --batch-size 10 \
  --genre workplace \
  --level B1

# 步骤 2：批量评分
python3 ./scripts/score_story_outline.py \
  /path/to/task1 \
  /path/to/task2 \
  /path/to/task3 \
  ...

# 步骤 3：查看对比报告
cat /path/to/output/batch_score_comparison.json

# 步骤 4：选择最佳剧本，继续完整流程
# 使用原有的 cd-generator 流程完成选中的剧本
```

脚本模式不会直接“调用 skill 说明书”。`batch_generate_outlines.sh` 通过真实执行器 `generate_outline_with_llm.py` 调用模型；对话模式里的 `/cd-generator` 才由 AI 读取并应用 `/shanyin-write` skill。

## 评分报告示例

```json
{
  "total_stories": 10,
  "ranking": [
    {
      "rank": 1,
      "task_dir": "/path/to/task1",
      "title": "设计师的第一步",
      "title_en": "Designer's First Step",
      "average_score": 8.21,
      "recommendation": "推荐",
      "brief_comment": "故事节奏紧凑，角色成长线清晰，职场场景真实",
      "scores": {
        "story_appeal": 8.5,
        "character_design": 8.0,
        "conflict_design": 8.5,
        "speaking_practice_fit": 9.0,
        "emotional_arc": 7.5,
        "workplace_realism": 8.5,
        "originality": 7.5
      }
    }
  ],
  "top_recommendations": [
    {
      "rank": 1,
      "title": "设计师的第一步",
      "average_score": 8.21
    },
    {
      "rank": 2,
      "title": "新人的挑战",
      "average_score": 7.86
    }
  ]
}
```

## 配置要求

评分功能使用与内容质检相同的 LLM 配置：

```bash
# config/llm.env
CD_GENERATOR_LLM_BASE_URL=https://your-api.com/v1
CD_GENERATOR_LLM_MODEL=claude-sonnet-4-6
CD_GENERATOR_LLM_API_KEY=your-key
CD_GENERATOR_LLM_ENDPOINT_MODE=claude
```

## 图片生成说明

**重要**：cd-generator 使用自己的 `smart_image_manager.sh` 进行批量编排，但每张图片的 OpenCLI 提交、状态检查和下载统一调用 `chatgpt-image` skill 的服务脚本。

- `chatgpt-image` skill 是独立单图/OpenCLI 服务，可供多个 skills 复用
- cd-generator 批处理使用 `smart_image_manager.sh` 管理批量、质检和任务状态
- 支持 OpenCLI 和 YouMind API 两种模式

## 使用建议

1. **快速测试**：先生成 3-5 个变体，评分后选择最佳的
2. **正式生产**：生成 10 个变体，选择前 2 名继续开发
3. **评分标准**：平均分 ≥7.0 推荐继续开发
4. **变体设计**：每个变体应在情节、角色、冲突上有明显差异
