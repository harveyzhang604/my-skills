# cd-generator 完整工作流程说明

## 概述

cd-generator 是为 Scene2Talk 英语口语学习平台生成完整漫画短剧内容的工具链。

## 完整工作流程

### 阶段一：批量大纲生成和评分（模式A）

**目标**：快速生成多个故事变体，通过评分筛选最佳创意

```
用户提供故事方向
    ↓
生成10个不同的故事大纲变体（shanyin-write）
    ↓
LLM 多维度评分（7个维度，0-10分）
    ↓
生成排名对比报告
    ↓
用户查看评分，选择1-2个最佳剧本
```

**命令**：
```bash
/cd-generator --batch \
  --theme "职场新人设计师成长" \
  --batch-size 10 \
  --genre workplace \
  --level B1 \
  --chapters 6 \
  --pages 24
```

**输出**：
- 10个故事大纲（story_outline.json）
- 10个评分报告（story_score.json）
- 1个对比报告（batch_score_comparison.json）

**时间**：30-40分钟

### 阶段二：完整内容生成（模式B）

**目标**：为选中的剧本生成完整的可用内容

```
选中的故事大纲
    ↓
生成详细剧本（shanyin-write）
  - 6章 × 24页 = 144页
  - 每页12-16句英文对话
    ↓
生成分镜描述（shanyin-direct）
  - 144个分镜
  - 16:9横版，左/中/右分区
  - 包含中英文图片提示词
    ↓
提取并保存提示词
  - 144个英文提示词（用于生成图片）
  - 144个中文提示词（用于预览和审稿）
    ↓
内容质检
  - 对话自然度
  - 提示词质量
  - 角色一致性
    ↓
批量生成图片（smart_image_manager.sh）
  - 提示词质量预检
  - 批量提交请求
  - 自动监控循环
  - 智能重试机制
  - 144张图片
    ↓
数据整合
  - final_output.json
  - HTML预览页面
    ↓
导入 Scene2Talk
  - 用于英语口语练习
```

**命令**：
```bash
# 继续已选中的任务
/cd-generator --continue <task_dir>

# 或从头开始
/cd-generator \
  --theme "设计师的第一步" \
  --genre workplace \
  --level B1 \
  --chapters 6 \
  --pages 24
```

**输出**：
- 6章完整剧本（144页）
- 144个分镜描述
- 144个英文提示词 + 144个中文提示词
- 144张图片
- final_output.json（可导入 Scene2Talk）
- HTML预览页面

**时间**：3-4小时

### 阶段三：导入 Scene2Talk

**目标**：将生成的内容导入到口语练习平台

```
final_output.json
    ↓
Scene2Talk 项目
    ↓
英语口语练习
  - 故事背景
  - 角色对话
  - 口语任务
  - 图片场景
```

## 四个 Skills 的职责

### 1. cd-generator（主编排）
- 协调整个工作流程
- 管理任务目录和进度
- 调用其他 skills
- 批量图片生成管理（smart_image_manager.sh）
- 数据整合和输出

### 2. shanyin-write（编剧）
- **批量模式**：生成10个不同的故事大纲变体
- **完整模式**：生成详细剧本（每章24页，每页12-16句对话）
- 确保对话适合口语练习
- 输出结构化 JSON

### 3. shanyin-direct（导演）
- 将剧本转换为视觉分镜
- 生成16:9横版构图（左/中/右或斜向分区）
- 输出中英文图片提示词
- 确保画面适合 Scene2Talk 背景

### 4. chatgpt-image（单图生成）
- **仅用于用户单图请求**
- **不参与 cd-generator 批处理**
- cd-generator 使用自己的 smart_image_manager.sh

## 关键特性

### 批量大纲模式
- ✅ 快速生成多个创意变体
- ✅ LLM 多维度评分
- ✅ 排名对比报告
- ✅ 用户选择最佳创意

### 完整生成模式
- ✅ 详细剧本（适合口语练习）
- ✅ 视觉分镜（16:9横版）
- ✅ 中英文提示词
- ✅ 内容质检
- ✅ 智能图片生成
- ✅ 数据整合
- ✅ HTML预览

### 图片生成管理
- ✅ 提示词质量预检（LLM审稿）
- ✅ 批量提交和监控
- ✅ 智能重试机制
- ✅ 支持 OpenCLI 和 YouMind API 两种模式

## 使用建议

### 快速测试
```bash
# 批量模式：3个变体，2章×3页
/cd-generator --batch \
  --theme "咖啡店的故事" \
  --batch-size 3 \
  --chapters 2 \
  --pages 3

# 完整模式：2章×3页
/cd-generator \
  --theme "咖啡店的故事" \
  --chapters 2 \
  --pages 3
```

### 正式生产
```bash
# 批量模式：10个变体，6章×24页
/cd-generator --batch \
  --theme "职场新人成长" \
  --batch-size 10 \
  --chapters 6 \
  --pages 24

# 选择最佳剧本后继续
/cd-generator --continue <selected_task_dir>
```

## 评分标准

### 7个评分维度（每项0-10分）
1. **故事吸引力**：情节是否引人入胜
2. **角色设定**：角色是否立体鲜明
3. **冲突设计**：冲突递进是否合理
4. **口语练习适配度**：对话场景是否自然
5. **情感曲线**：情感变化是否流畅
6. **职场真实性**：场景和流程是否真实
7. **创意新颖度**：故事是否有新意

### 推荐标准
- 平均分 ≥7.0：推荐继续开发
- 平均分 <7.0：需要改进或放弃

## 文件输出结构

```
/Users/zhanghua/.claude/skills/cd-generator/output/
└── YYYYMMDD_HHMMSS_任务名称/
    ├── data/
    │   ├── story_outline.json      # 故事大纲
    │   ├── story_score.json        # 评分结果
    │   └── progress.json           # 进度跟踪
    ├── scripts/
    │   ├── chapter1.json           # 第1章剧本
    │   └── chapter2.json           # 第2章剧本
    ├── storyboards/
    │   ├── chapter1_page1.json     # 分镜描述
    │   └── ...
    ├── prompts/
    │   ├── chapter1_page1.txt      # 英文提示词（用于生成图片）
    │   └── ...
    ├── prompts_zh/
    │   ├── chapter1_page1.txt      # 中文提示词（用于预览）
    │   └── ...
    ├── images/
    │   └── (生成的图片)
    ├── quality/
    │   └── content_quality_report.md
    └── output/
        ├── final_output.json       # 最终数据（可导入 Scene2Talk）
        └── preview.html            # HTML预览
```

## 版本信息

- cd-generator: v2.9.0
- 更新日期: 2026-05-01
- 主要改进: 批量生成和评分功能
