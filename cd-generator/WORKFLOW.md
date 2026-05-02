# cd-generator 完整工作流程说明

## 概述

cd-generator 是为 Scene2Talk 英语口语学习平台生成完整漫画短剧内容的工具链。

## 完整工作流程

### 阶段一：批量大纲生成和评分

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

---

### 阶段二：故事脉络、全量角色卡和场景基调图

**目标**：为选中的剧本生成完整故事框架和视觉连续性资产

```
选中的故事大纲
    ↓
生成故事脉络（8个章节的情节发展）
  - 每章核心事件
  - 关键转折点
  - 情感基调
    ↓
抽取全量角色/实体卡
  - 主角、反派、盟友、关键家人
  - 前世身份、组织/族群代表
  - 拟人化 AI、古代文明/系统等视觉实体
  - 每张卡包含中英双语介绍、视觉描述、连续性标签
  - 英文字段用于后续图片提示词拼接，中文字段用于人工审稿
  - 每张卡包含英文参考图提示词
    ↓
生成角色头像提示词
    ↓
生成统一视觉资产 sheet
  - 角色、群体、AI、文明遗迹、记忆森林等扩展实体统一处理
  - 固定 16:9、2 行 x 4 列
  - 每张 8 格
  - 超过 8 个自动拆成多张
  - 最后一张不足 8 个就留空格
    ↓
裁切成单独资产卡图片并命名
    ↓
生成 2 张场景基调图提示词
  - 自然/神秘森林基调
  - 古代/数字文明或对立阵营基调
  - 不是纯氛围图，也不是精确地图
  - 要包含核心场景样貌、风格情绪、可复用视觉元素、材质/色彩规则和粗略空间关系
  - 可以有中心石门/AI核心、左右延展树根/通道、前中后景等空间锚点，但不锁死精确方位
    ↓
（可选）生成角色头像图和场景基调图
    ↓
用户确认后继续
```

**命令**：
```bash
# 生成故事脉络、全量角色卡和场景基调图提示词
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/generate_story_arc_and_cards.py <task_dir>

# （可选）生成视觉资产 sheet、自动裁切资产卡、生成场景基调图
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/generate_visual_reference_images.py <task_dir>
```

**输出**：
- story_arc.json（故事脉络）
- character_cards.json（全量角色/实体卡 + 场景基调卡）
- character_prompts/（角色头像提示词）
- character_sheets/（角色/实体统一视觉资产 sheet，固定 2x4，每张 8 格）
- character_images/（从 sheet 裁切出的单独角色/实体资产卡）
- scene_tone_prompts/（2 张场景基调图提示词）
- scene_tone_images/（场景基调图，可选）

**示例格式**：

**故事脉络**（参考猴子警长）：
```
1. 反物质爆炸与沉睡（故事起因）
   为了争夺被熊猫大侠带走的盒子，斑马经理设下陷阱困住猴子警长一行...

2. 寻找"失落的太阳"与永动镇危机
   猴子警长在沉睡一年后醒来，此时的森林都市正因反物质爆炸引发的恶劣天气陷入灾难...

3. 藏金镇的核弹危机
   离开永动镇后，他们来到了藏金镇，遇到了梦想造火箭的金雕...
```

**角色卡片**（参考猴子警长）：
```
核心阵营与陆地群像：
- 猴子警长：森林都市的守护者，打击犯罪的英雄。
- 小鸡敦敦：为成为警察而努力的三黄鸡小鸡。
- 兔子警长：应对暴力事件的专家。

破坏者联盟与深海一族：
- 白虎大帝：破坏者联盟的首领，妄图建立一个由黑白动物统治的世界。
- 弗兰熊：最懂科学的天才，最有品位的坏蛋。
```

**时间**：10-15分钟

---

### 阶段三：完整内容生成

**目标**：为选中的剧本生成完整的可用内容

```
选中的故事大纲 + 故事脉络 + 角色设定
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
生成带角色/场景文字参考的增强提示词
  - 从 character_cards.json 匹配本页角色/实体
  - 从 scene_tone_cards 匹配场景基调
  - 输出 prompts_with_refs/，作为实际提交给生图服务的 prompt
    ↓
内容质检
  - 对话自然度
  - 提示词质量
  - 角色一致性
    ↓
批量生成图片（smart_image_manager.sh 调用 chatgpt-image 服务）
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

---

### 阶段四：导入 Scene2Talk

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
- 提交前生成 `prompts_with_refs/`，把本页角色卡和场景基调卡的英文文字参考并入 prompt
- 每张图的 OpenCLI 提交/检查/下载调用 chatgpt-image 服务
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

### 4. chatgpt-image（独立生图服务）
- 负责单张图的 OpenCLI 提交、状态检查、下载和浏览器挂接修复
- 可直接响应用户单图请求
- 可被 cd-generator 或其它 skills 复用
- 不负责批量进度、任务目录、提示词质检或 `image_links.json`
- 当前 OpenCLI 文本命令不支持直接附加本地角色卡图片；需要图片参考时由调用方先把角色卡文字描述并入 prompt，未来切到支持 image reference 的 API 后再接入 `.refs.json` 中的图片路径

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
    │   ├── chapter1_page1.txt      # 基础英文提示词
    │   └── ...
    ├── prompts_with_refs/
    │   ├── chapter1_page1.txt      # 实际提交生图的增强提示词
    │   ├── chapter1_page1.refs.json # 本页匹配到的角色/场景参考元数据
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
