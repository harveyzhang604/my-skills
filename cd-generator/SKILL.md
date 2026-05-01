---
name: cd-generator
description: Use when generating complete comic drama content for English speaking practice, including story outline, chapter scripts, page storyboards, image prompts, optional Story-Guided missions, images, and preview output.
metadata:
  version: 2.8.4
  version_scope: cd-generator skill only, separate from the Scene2Talk app version.
---

# Comic Drama Generator (漫剧生成器)

为 Scene2Talk 英语口语学习平台生成完整的漫画短剧内容。

## 版本边界

本文件的版本只代表 `cd-generator` skill 自身能力版本，不代表 Sense Talk / Scene2Talk 主项目版本。

- Skill 版本记录：`/Users/zhanghua/.claude/skills/cd-generator/skill-version.json`
- Skill 工作目录：`/Users/zhanghua/.claude/skills/cd-generator/`
- 主项目版本来源：Sense Talk 项目自己的 `package.json`
- 禁止把 `cd-generator` 的版本号同步到主项目 `package.json`，也不要用主项目版本号覆盖本 skill 版本。
- 所有任务目录必须位于 `/Users/zhanghua/.claude/skills/cd-generator/output/`。如果传入 `cd_generator_output/<task>` 或 `output/<task>`，脚本会自动解析到 skill 的 output 目录；如果传入项目 worktree 下的绝对路径，脚本会直接拒绝。

## 核心原则与工作模式

### 两种工作模式

**模式A：批量大纲模式**（用于快速筛选创意）
1. 用户提供故事方向和主题
2. 生成10个不同的故事大纲变体
3. 使用 LLM 多维度评分
4. 用户查看评分报告，选择1-2个最佳剧本
5. 对选中的剧本继续模式B

**模式B：完整生成模式**（生成可用于 Scene2Talk 的完整内容）
1. ✅ 数据准备阶段：故事大纲 → 详细剧本 → 分镜 → 提示词 → 内容质检
2. ✅ 图片生成阶段：最后统一生成所有图片
3. ✅ 数据整合：生成 final_output.json 和 HTML 预览
4. ✅ 导入 Scene2Talk：用于英语口语练习

**禁止**：边生成数据边生成图片，这会导致混乱和重复请求。

## Scene2Talk 内容标准

`cd-generator` 的产物优先服务当前 Scene2Talk 项目，不只是“漫画故事”，而是可用于英语口语练习的沉浸式背景和对话任务。

**故事与对白**：
- 生产规格默认按 6-8 章规划，每章 24 页；测试时可显式缩短。
- 每页必须有一个清楚的口语练习目标：打招呼、确认需求、解释原因、争取时间、接受反馈、澄清误会、表达压力、提出方案、总结承诺等。
- 对白要像真实口语，不要像书面汇报。优先使用短句、追问、停顿、反应句、澄清句、修正句和自然职场表达。
- 剧情不能一路平铺直叙。每章需要有递进的压力或转折：误会、时间限制、客户临时改需求、同事反馈、信息不对称、小失败、补救、阶段性胜利。
- 冲突要现实，不要为了戏剧性而夸张。工作场景可以参考真实公司常见流程：brief、kickoff、standup、design review、client feedback、handoff、deadline、revision、presentation。

**16:9 图片背景**：
- 图片默认是 16:9 landscape / widescreen，用作口语练习页面背景。
- **分镜构图原则**：
  - ✅ **垂直分区**：左/中/右三分区，或按比例分区（如左30% | 中50% | 右20%）
  - ✅ **斜向分区**：左斜60°或右斜60°斜线分割，创造动感
  - ❌ **避免上下分区**：16:9宽屏不适合上下分割，空间利用率低
  - ✅ **根据内容灵活选择**：静态情感用垂直分区，动态互动用斜向分区
- **多镜头叙事**：每张图应包含多个景别，通过分区实现：
  - 广角 establishing shot（环境铺垫）
  - 中景 medium shot（主体互动）
  - 特写 close-up（情感细节）
  - 视线自然流动：环境 → 主体 → 情感
- **分区比例建议**：
  - 主场景占50-70%，辅助场景各占15-25%
  - 对角线构图引导视线
  - 避免机械的三等分，根据内容灵活调整
- **人物和构图**：
  - 人物和活动分布在左/中/右，不要全部挤在一个角落
  - 关键表情、眼神、手势放在视觉焦点区域
  - 对白气泡位置要避开UI遮挡区域
- **文字要求**：
  - 每张图 1-3 个短英文 speech bubbles
  - 过场页至少一个英文 caption
  - 画面内所有文字必须是英文
  - 禁止中文、日文、韩文、伪文字、乱码

## 依赖 Skills 与调用边界

本 skill 编排另外两个能力：

- `/shanyin-write`：负责故事大纲和逐章剧本。被 `cd-generator` 调用时必须使用 `shanyin-write` 的 `cd-generator Mode`，输出结构化 JSON，不走原始交互式暂停流程。
- `/shanyin-direct`：负责每页漫画分镜和中英文图片提示词。被 `cd-generator` 调用时必须使用 `shanyin-direct` 的 `cd-generator Mode`，输出 16:9 横版 `storyboard` JSON，不输出九列拍摄分镜表，不暂停等待确认。

**图片生成**：`cd-generator` 使用自己的 `scripts/smart_image_manager.sh` 统一批量提交、监控和下载，不调用 `/chatgpt-image` skill。`/chatgpt-image` skill 仅用于单图请求。

如果依赖 skill 的原始说明要求”每一步暂停等待用户确认”，在 `cd-generator` 批处理模式中由本 skill 的阶段门控替代，不在子 skill 内暂停。

## 输入参数

### 模式A：批量大纲模式

```bash
/cd-generator --batch \
  --theme "职场新人成长" \
  --batch-size 10 \
  --genre workplace \
  --level B1 \
  --chapters 6 \
  --pages 24
```

**参数说明**：
- `--batch`：启用批量大纲模式
- `--theme`：故事主题或方向（必需）
- `--batch-size`：生成变体数量（默认10）
- `--genre`：类型（romance/revenge/fantasy/family/workplace）
- `--level`：语言难度（A2/B1/B2）
- `--chapters`：章节数（默认6）
- `--pages`：每章页数（默认24）

### 模式B：完整生成模式

```typescript
{
  story_theme: string,        // 故事主题（如"设计师的第一步"）
  genre: string,              // 类型：romance/revenge/fantasy/family/workplace
  language_level: string,     // 语言难度：A2/B1/B2
  total_chapters?: number,    // 生产默认6-8；测试可设为1-2
  pages_per_chapter?: number, // 生产默认24；测试可设为3-6
  art_style?: string,         // 画风：manga（默认）
  task_dir?: string          // 可选：继续已有任务（用于批量模式选中后继续）
}
```

## 文件组织结构

每个任务在 skill 的 output 目录下创建独立文件夹：

```
/Users/zhanghua/.claude/skills/cd-generator/output/
└── YYYYMMDD_HHMMSS_任务名称/
    ├── README.md                    # 任务说明和图片链接记录
    ├── data/
    │   ├── story_outline.json      # 故事大纲
    │   └── progress.json           # 进度跟踪
    ├── scripts/
    │   ├── chapter1.json           # 第1章剧本
    │   └── chapter2.json           # 第2章剧本
    ├── storyboards/
    │   ├── chapter1_page1.json     # 分镜描述（含提示词）
    │   ├── chapter1_page2.json
    │   └── ...
    ├── prompts/
    │   ├── chapter1_page1.txt      # 英文图片提示词：用于实际生成图片
    │   ├── chapter1_page2.txt
    │   └── ...
    ├── prompts_zh/
    │   ├── chapter1_page1.txt      # 中文图片提示词：用于HTML预览和人工审稿
    │   ├── chapter1_page2.txt
    │   └── ...
    ├── missions/                    # 对话任务（可选，用于Story-Guided Free Talk）
    │   ├── chapter1_page1.json     # 第1章第1页对话任务
    │   ├── chapter1_page2.json
    │   └── ...
    ├── images/
    │   └── (生成的图片文件)
    ├── quality/
    │   ├── content_quality_report.md   # 内容质检报告
    │   └── content_quality_report.json # 机器可读质检结果
    ├── image_links.json            # 图片生成链接记录
    └── output/
        └── final_output.json       # 最终整合数据
```

## 工作流程

### 第0步：初始化任务目录

```bash
TASK_ID="$(date +%Y%m%d_%H%M%S)_${story_theme}"
TASK_DIR="/Users/zhanghua/.claude/skills/cd-generator/output/$TASK_ID"

mkdir -p "$TASK_DIR"/{data,scripts,storyboards,prompts,prompts_zh,missions,images,output}

# 创建进度跟踪文件
cat > "$TASK_DIR/data/progress.json" << EOF
{
  "workflow": "Comic Drama Generation",
  "theme": "${story_theme}",
  "total_chapters": ${total_chapters},
  "pages_per_chapter": ${pages_per_chapter},
  "status": {
    "story_planning": "pending",
    "chapter_scripts": "pending",
    "storyboards": "pending",
    "prompts_saved": "pending",
    "content_quality": "pending",
    "images": "pending",
    "conversation_missions": "pending",
    "integration": "pending"
  },
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "✅ 任务目录已创建: $TASK_DIR"
```

### 第1步：故事策划

调用 `/shanyin-write` 生成故事大纲。此处使用 `cd-generator mode`：直接输出 JSON，不在 `/shanyin-write` 内暂停确认。

**调用输入**：给 `/shanyin-write` 的故事策划输入必须包含：
- `story_theme`、`genre`、`language_level`、`total_chapters`、`pages_per_chapter`、`art_style`
- Scene2Talk 口语练习定位：真实场景、可说出口的英语、每页有练习目标
- 目标产物：`data/story_outline.json`
- 输出约束：JSON only，不要 Markdown 解释，不暂停确认

**输出**：`$TASK_DIR/data/story_outline.json`

**策划要求**：
- 明确 6-8 章整体弧线：开场目标、第一次受挫、关系/协作变化、中段压力升级、关键误会或失败、补救行动、展示/交付、余波与成长。
- 每章拆成 4-8 个可滑动的剧情阶段，后续用于 Story-Test 顶部进度条，例如“剧情导入 / 新人问候 / 确认任务 / 发现问题 / 争取支持 / 修改方案 / 汇报结果”。
- 公司、岗位和工作流要真实可信。名称要像正常公司名，职位要像真实职场岗位，不要生硬拼词。
- 故事目标必须能转化成口语练习任务，不写纯内心戏或长旁白驱动的章节。

**完成后立即报告**：
```
✅ 第1步完成：故事策划
   - 故事标题：{title}
   - 角色数量：{character_count}
   - 章节数：{total_chapters}
```

**更新进度**：
```bash
# 更新 progress.json 中的 story_planning 状态为 "completed"
```

### 第2步：逐章创作剧本

为每一章调用 `/shanyin-write` 生成详细剧本。此处使用 `cd-generator mode`：每章直接输出结构化 JSON。

**调用输入**：给 `/shanyin-write` 的单章剧本输入必须包含：
- 完整 `story_outline.json`
- 当前 `chapter_number` 和对应 `chapter_outlines[]`
- 前一章结尾状态（如有）和下一章衔接目标（如有）
- 每页需要服务口语练习：12-16 句短英文对白、自然反应、澄清、追问、修正、承诺等
- 目标产物：`scripts/chapter{N}.json`
- 输出约束：JSON only，不要 Markdown 解释，不暂停确认

**输出**：`$TASK_DIR/scripts/chapter{N}.json`

**剧本要求**：
- 每页 12-16 句英文对白，适合移动端逐句练口语；单句通常控制在 4-14 个英文单词，B2 可以稍长。
- 每页至少包含一个对话动作：询问、确认、解释、拒绝、协商、道歉、鼓励、复述、总结之一。
- 每页要有一个微小变化：信息新增、情绪变化、关系推进、任务阻碍、决定被修改、角色态度改变。
- 英文对白优先自然口语，例如 “Could you walk me through it?”、“I might be missing something.”、“Can we narrow the options?”，避免整页都是正式陈述句。
- 中文翻译服务理解即可，不要反过来影响英文口语自然度。

**每章完成后立即报告**：
```
✅ 第2步进度：第{N}章剧本已完成
   - 页数：{pages_count}
   - 对话数：{dialogue_count}
```

**全部完成后报告**：
```
✅ 第2步完成：所有章节剧本已生成
   - 总章节：{total_chapters}
   - 总页数：{total_pages}
   - 总对话：{total_dialogues}
```

### 第3步：分镜设计

为每页调用 `/shanyin-direct` 生成详细分镜描述。此处使用 `cd-generator mode`：每页直接输出漫画分镜 JSON，不输出拍摄用九列表。

**调用输入**：给 `/shanyin-direct` 的每页输入必须包含：
- 故事标题、类型、语言等级和画风
- 角色视觉设定和本页出场角色
- 章节号、页号、场景地点、该页剧情目标
- 本页英文对白和中文翻译
- 前后页连续性提示（如角色位置、道具、情绪状态）
- Scene2Talk 约束：16:9 横版背景、左/中/右或斜向分区、英文可见文字

**输出**：`$TASK_DIR/storyboards/chapter{N}_page{M}.json`

**每个分镜包含**：
```json
{
  "chapter": 1,
  "page": 1,
  "storyboard": {
    "composition": "16:9 widescreen manga scene with vertical or diagonal panel zones",
    "left_zone": "supporting environment, setup, or secondary character action",
    "center_zone": "main characters, gestures, eye contact, props, and story action",
    "right_zone": "reaction, close-up detail, or next visual beat",
    "diagonal_flow": "optional diagonal split direction if better for motion or tension",
    "visual_elements": {...},
    "art_style": "Modern manga style",
    "mood": "...",
    "color_scheme": "...",
    "image_prompt": "完整的英文提示词。实际生成图片只使用这个字段。",
    "image_prompt_zh": "完整的中文图片提示词。HTML预览直接展示这个字段，不在预览阶段临时翻译。"
  }
}
```

**分镜要求**：
- `image_prompt` 必须明确写出：16:9 landscape / widescreen composition。
- `image_prompt` 必须明确使用左/中/右三分区、非均匀横向分区，或斜向分区；不要使用 TOP/MIDDLE/BOTTOM 上下分区。
- `image_prompt` 必须把人物、动作、对话气泡和重要道具分布在横向阅读路径中，避免挤在角落或贴近画面边缘，适配 Story-Test 的顶部信息、右侧漫画导航、提示面板和底部语音条。
- 画面中应加入 1-3 个短英文 speech bubbles/captions，内容从该页英文对白中提炼，短、自然、可读；过场页至少加入一个英文 caption。
- 画面内任何可见文字都必须 English only。提示词中要明确：no Chinese, no Japanese, no Korean, no pseudo text, no random glyphs, no unreadable text。
- 不要把完整 12-16 句对白塞进图片，只放最能代表场景的 1-3 句短气泡；完整练习对白仍保存在 JSON 中。

**每完成3个分镜报告一次**：
```
✅ 第3步进度：已完成 {count}/{total} 个分镜
```

**全部完成后报告**：
```
✅ 第3步完成：所有分镜描述已生成
   - 总分镜数：{total_storyboards}
```

### 第4步：提取并保存提示词

**重要**：每个分镜必须同时包含英文 `image_prompt` 和中文 `image_prompt_zh`。

- `image_prompt`：英文图片提示词，保存到 `prompts/`，只用于实际图片生成
- `image_prompt_zh`：中文图片提示词，保存到 `prompts_zh/`，只用于 HTML 预览和人工审稿
- 禁止在 HTML 预览阶段再临时翻译英文提示词；预览页应该直接显示已经产出的中文提示词

```bash
/Users/zhanghua/.claude/skills/cd-generator/scripts/save_prompts.sh "$TASK_DIR"
```

**完成后报告**：
```
✅ 第4步完成：所有提示词已保存
   - 英文提示词文件数：{count}
   - 中文提示词文件数：{count}
   - 英文保存位置：$TASK_DIR/prompts/
   - 中文保存位置：$TASK_DIR/prompts_zh/
```

**更新进度**：
```bash
# 更新 progress.json 中的 prompts_saved 状态为 "completed"
```

### 第5步：内容质检

**重要**：图片生成前必须先跑内容质检。质检 `error` 为 0 才进入图片生成；`warning/info` 可以继续，但要在报告中说明。

如果本次要交付 Story-Guided Free Talk，请先执行“第9步：生成对话任务”，再运行本步骤；这样质检可以同时检查 `missions/` 的结构和角色合理性。如果先做了内容质检，后来又生成 missions，需要重新运行本步骤。

内容质检需要模型语义审稿。模型配置统一放在 skill 本地配置文件：
```bash
/Users/zhanghua/.claude/skills/cd-generator/config/llm.env
```

该文件已加入 `.gitignore`，不要提交。脚本会自动读取其中的 `CD_GENERATOR_LLM_BASE_URL`、`CD_GENERATOR_LLM_MODEL`、`CD_GENERATOR_LLM_API_KEY`、`CD_GENERATOR_LLM_ENDPOINT_MODE`。

```bash
/Users/zhanghua/.claude/skills/cd-generator/scripts/validate_content.sh "$TASK_DIR"
```

**检查内容**：
- 每页对话是否为 12-16 句
- 英文是否适合口语练习：由模型判断自然度、口语性、跟读压力
- 剧情是否有微冲突/转折/任务推进，而不是平铺直叙
- 中文翻译是否齐全
- 角色名是否与 `story.characters` 一致：由模型审稿 + 本地结构检查
- A2/B1/B2 难度是否明显跑偏：由模型语义判断
- 分镜是否同时包含英文 `image_prompt` 和中文 `image_prompt_zh`
- 图片提示词是否符合 Scene2Talk 16:9 背景要求：中间 3/4 放关键人物和动作，上下 1/8 留安静安全区，画面内文字 English only，包含短英文漫画气泡/字幕
- 如果已生成 `missions/`：检查 Story-Guided 角色、结构化 beats、target phrases 是否合理

**输出**：
- `$TASK_DIR/quality/content_quality_report.md`
- `$TASK_DIR/quality/content_quality_report.json`

**完成后报告**：
```
✅ 第5步完成：内容质检
   - 结果：通过 / 未通过
   - error：{error_count}
   - warning：{warning_count}
   - info：{info_count}
   - 报告：$TASK_DIR/quality/content_quality_report.md
```

**更新进度**：
```bash
# error 为 0 时，将 progress.json 中的 content_quality 状态更新为 "completed"
# error > 0 时，将 content_quality 状态更新为 "failed"，修复文本后重新运行质检
```

### 第6步：智能图片生成

**重要**：这是最后一步！只有在前5步全部完成且内容质检没有 error 后才执行。

使用智能图片生成管理器，一键完成提交、监控、下载全流程。图片生成只读取 `$TASK_DIR/prompts/` 中的英文提示词，不使用中文提示词。

```bash
/Users/zhanghua/.claude/skills/cd-generator/scripts/smart_image_manager.sh "$TASK_DIR"
```

**OpenCLI 稳定性策略（必须遵守）**：

- 大批量生成前，先提交 1 张验证链路；第 1 张拿不到 `https://chatgpt.com/...` 链接时，不要继续提交整批。
- OpenCLI 可能被 Chrome 扩展页挡住，典型错误是 `Cannot access a chrome-extension:// URL of different extension`、`Detached while handling command`、`attach failed`。脚本会自动执行 `opencli browser close` + `opencli doctor` 后重试。
- 如果输出里已经有 ChatGPT 链接，即使同时混入 `Detached while handling command` 或非 0 exit code，也先按“已提交 pending”记录；后续监控/下载阶段再确认图片是否真正生成。
- 连续 3 张提交失败时停止批量提交，先检查 `$TASK_DIR/image_generation.log` 和 `$TASK_DIR/image_generation_pageN_submit.log`，避免刷出 24 个无效失败。
- 下载时只认本次下载开始后的 PNG 文件，避免误把 `~/Downloads` 里的旧图当成当前页图片。

**严格节流提交（如需每 120 秒一张）**：

当用户明确要求“每两分钟提交一张”时，使用专门节流脚本。建议先跑第 1 张：

```bash
/Users/zhanghua/.claude/skills/cd-generator/scripts/submit_opencli_rate_limited.py "$TASK_DIR" \
  --start 1 --end 1 --interval 120 --force --stop-on-first-failure
```

第 1 张成功记录链接后，再跑剩余页：

```bash
/Users/zhanghua/.claude/skills/cd-generator/scripts/submit_opencli_rate_limited.py "$TASK_DIR" \
  --start 2 --end 24 --interval 120 --max-submit-failures 3
```

该脚本会把每页提交日志写入 `$TASK_DIR/image_generation_pageN_submit.log`，并把 `submit_exit_code`、`submit_attempts`、`submit_warning`、`opencli_repaired`、`last_submit_error` 写入 `image_links.json`。

**两种生成模式**：

图片生成支持两种模式，通过 `config/youmind.env` 中的 `YKM_DIRECT_API_MODE` 控制：

1. **OpenCLI 模式**（默认）：使用浏览器自动化调用 ChatGPT Image 2
   - 需要登录 ChatGPT 网页版
   - 异步生成，需要监控循环
   - 适合有 ChatGPT Plus 订阅的用户

2. **YouMind API 模式**：直接调用 YouMind API 生成图片
   - 需要配置 YouMind API Key
   - 同步生成，无需等待
   - 更适合批量生成

**切换到 YouMind API 模式**：
```bash
# 编辑配置文件
cat > /Users/zhanghua/.claude/skills/cd-generator/config/youmind.env << 'EOF'
YKM_API_KEY=your-youmind-api-key
YKM_BASE_URL=https://api.youmind.ai/v1
YKM_IMAGE_MODEL=gpt-image-1
YKM_DIRECT_API_MODE=true
EOF
```

**智能管理器功能**：

#### 6.1 提示词质量预检
提交前由模型审稿每个英文图片提示词：
- 判断是否过度抽象、画面过复杂、情绪转换难渲染、特效过多、主体不清
- 发现问题后由模型改写为更具体、可渲染的英文提示词
- 使用 `scripts/llm_json_client.py` 统一调用 LLM 进行语义判断
- 支持 OpenAI-compatible 和 Claude Messages 两种 API 模式
- 不使用固定禁词或 grep/sed 规则做语义判断

#### 6.2 批量提交请求
```
📤 提交图片生成请求...
   第1章第1页：✓ 质量检查通过，已提交 (模式: opencli/youmind)
   第1章第2页：⚠️ 提示词质量警告，自动优化后提交
   第1章第3页：✓ 质量检查通过，已提交
   ...
✅ 所有请求已提交
```

提交阶段的判定原则：
- 以 ChatGPT 链接为准：有链接即进入 `pending`，不要因为 stderr 里有 `Detached` 就误判失败。
- 无链接且是浏览器挂接错误：自动修复并重试。
- 无链接且连续失败：停止批量提交，先修复 OpenCLI/登录/浏览器状态。

#### 6.3 自动监控循环 (OpenCLI 模式)
提交完成后自动进入监控模式（仅 OpenCLI 模式）：
- ⏰ 每1分钟检查一次所有图片状态
- 🔍 检测三种状态：READY（已完成）、ERROR（失败）、PENDING（生成中）
- 📊 每轮检查后报告进度

**YouMind API 模式**：同步生成，直接返回图片，无需监控循环。

**监控过程报告**（OpenCLI 模式）：
```
━━━ 第一阶段：提交图片生成请求 ━━━
✅ 所有请求已提交

━━━ 第二阶段：自动监控和下载 ━━━
⏰ 每 1 分钟检查一次

🔍 第 1 轮检查 (已等待 1 分钟)
   第1章第1页: ✅ 已生成，开始下载...
   ✓ 下载完成 (3.5M)
   第1章第2页: ⏳ 生成中...
   第1章第3页: ❌ 生成失败
   🔄 准备重试 (1/2)
   📤 提交: 第1章第3页 (尝试 2)
   ⚠️ 提示词质量警告，自动优化...
   ✓ 优化后: 16:9 widescreen manga scene with left/center/right zones...
   ✅ 已提交: https://chatgpt.com/c/...

📊 当前状态: ✅ 1 | ⏳ 2 | ❌ 0

⏰ 等待 1 分钟后进行下一轮检查...

🔍 第 2 轮检查 (已等待 2 分钟)
   第1章第2页: ✅ 已生成，开始下载...
   ✓ 下载完成 (3.4M)
   第1章第3页: ⏳ 生成中...
   ...

📊 当前状态: ✅ 2 | ⏳ 1 | ❌ 0
```

#### 6.4 智能重试机制
发现失败时自动处理：
1. 读取原始提示词
2. 自动优化（去除特效词汇、简化描述）
3. 重新提交请求
4. 最多重试2次
5. 超过重试次数标记为最终失败

#### 6.5 完成报告
全部完成或达到最大等待时间（20分钟）后：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 最终报告
   ✅ 成功: 5 张
   ❌ 失败: 1 张
   📁 保存位置: /path/to/images
   📋 详细记录: /path/to/image_links.json
   📝 日志文件: /path/to/image_generation.log

⚠️ 失败的图片需要手动处理：
   第2章第3页: https://chatgpt.com/c/...
```

**配置参数**：

**通用参数**：
- `CHECK_INTERVAL=60` - 检查间隔（秒），默认1分钟（仅 OpenCLI 模式）
- `MAX_WAIT_TIME=1200` - 最大等待时间（秒），默认20分钟（仅 OpenCLI 模式）
- `MAX_RETRIES=2` - 最大重试次数，默认2次

**图片生成模式配置**（`config/youmind.env`）：
```bash
# OpenCLI 模式（默认）
YKM_DIRECT_API_MODE=false

# 或 YouMind API 模式
YKM_DIRECT_API_MODE=true
YKM_API_KEY=your-youmind-api-key
YKM_BASE_URL=https://api.youmind.ai/v1
YKM_IMAGE_MODEL=gpt-image-1
YKM_TIMEOUT=300
```

### 第7步：手动处理失败图片（如有）

如果智能管理器报告有失败的图片，可以手动处理：

**OpenCLI 模式**：

1. **查看失败原因**：
```bash
# 查看详细日志
cat "$TASK_DIR/image_generation.log" | grep "第X章第Y页"

# 查看某一页 OpenCLI 原始提交输出
cat "$TASK_DIR/image_generation_pageY_submit.log"

# 查看结构化状态
python3 - "$TASK_DIR" <<'PY'
import json, sys
task = sys.argv[1]
with open(f"{task}/image_links.json", encoding="utf-8") as f:
    data = json.load(f)
for img in data.get("images", []):
    if img.get("status") in {"submit_failed", "failed"} or img.get("last_submit_error"):
        print(img.get("chapter"), img.get("page"), img.get("status"), img.get("last_submit_error"))
PY
```

2. **手动优化提示词**：
```bash
# 编辑提示词文件
vim "$TASK_DIR/prompts/chapterX_pageY.txt"
```

3. **手动重新提交**：
```bash
prompt=$(cat "$TASK_DIR/prompts/chapterX_pageY.txt")
opencli chatgpt image "$prompt" --verbose
# 记录新的链接，等待1分钟后检查
```

如果是 OpenCLI 浏览器挂接问题，先执行：
```bash
opencli browser close
opencli doctor
```

**YouMind API 模式**：

1. **查看失败原因**：
```bash
# 查看详细日志
cat "$TASK_DIR/image_generation.log" | grep "第X章第Y页"
```

2. **手动调用 YouMind API**：
```bash
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/youmind_image_client.py \
  "$(cat $TASK_DIR/prompts/chapterX_pageY.txt)" \
  --output "$TASK_DIR/images/chapterX_pageY.png" \
  --verbose
```

### 第7.5步：批量下载已生成的图片（OpenCLI 模式）

**重要**：OpenCLI 模式下，图片提交后不会自动下载。需要使用专用脚本从 ChatGPT 对话页面提取并下载图片。

**下载原理**：
1. 逐个打开 `image_links.json` 中的 ChatGPT 对话链接
2. 用 `opencli browser eval` 执行 JS，从页面中查找 `img[alt="Generated image"]` 或 `img[src*="estuary/content"]`
3. 用 JS `fetch()` 下载图片 blob，触发浏览器下载到 `~/Downloads/`
4. 将下载的文件移动到 `$TASK_DIR/images/` 目录

**使用方法**：
```bash
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/download_chatgpt_images.py "$TASK_DIR" "$IMAGES_DIR"
```

**参数**：
- `$TASK_DIR`：任务目录路径
- `$IMAGES_DIR`：图片保存目录，通常为 `$TASK_DIR/images`

**只下载指定章节**：
```bash
# 修改脚本中的过滤条件，例如只下载第1-2章
images = [i for i in data.get('images', []) if i.get('chapter') in [1, 2]]
```

**注意事项**：
- 需要先登录 ChatGPT 网页版（通过 `opencli browser` 自动化窗口）
- 每张图片需要约 10 秒（打开页面 6 秒 + JS 执行 3 秒 + 下载 1 秒）
- 96 张图片约需 15-20 分钟
- 部分图片可能显示"未生成"，需要稍后重新运行脚本
- 建议多次运行脚本，直到所有已生成的图片都下载完成
- 遇到 ChatGPT 速率限制时，暂停后重新运行

**多轮下载策略**：
```bash
# 第一轮下载
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/download_chatgpt_images.py "$TASK_DIR" "$IMAGES_DIR"

# 等待 ChatGPT 生成更多图片后，再次运行（只下载未完成的）
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/download_chatgpt_images.py "$TASK_DIR" "$IMAGES_DIR"
```

**完成后报告**：
```
✅ 第7.5步完成：图片下载
   - 总计: {downloaded}/{total} 张
   - 第1章: {ch1_count}/24
   - 第2章: {ch2_count}/24
   ...
```

### 第8步：数据整合

所有图片下载完成后，整合所有数据：

```bash
/Users/zhanghua/.claude/skills/cd-generator/scripts/integrate_final_output.py "$TASK_DIR"
```

**完成后报告**：
```
✅ 第8步完成：数据整合
   - 最终文件：$TASK_DIR/output/final_output.json
   - 总章节：{total_chapters}
   - 总页数：{total_pages}
   - 总对话：{total_dialogues}
   - 图片数：{image_count}
```

### 第9步：生成对话任务（Conversation Missions）

**可选步骤**：如果需要支持 Story-Guided Free Talk 模式（自由对话 + 故事引导），生成每页的对话任务元数据。推荐在图片生成前、内容质检前执行；如果放在图片之后执行，必须重新运行第5步内容质检。

使用辅助脚本：
```bash
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/generate_conversation_missions.py "$TASK_DIR"
```

该步骤也需要模型语义抽取，直接复用 `config/llm.env`。

**生成内容**：
- 为每页创建 `missions/chapter{N}_page{M}.json`
- 包含：场景、角色、任务摘要、结构化必达剧情节点（must_hit_beats）、目标短语（target_phrases）
- 模型根据 `data/story_outline.json`、页面对话和 `language_level` 抽取自由对话任务
- 脚本只做 JSON 规范化和结构校验，不用关键词算法判断剧情意图
- 脚本会合并重复/重叠的 beats，并优先把 `greet_introduce` 放在自由对话开场
- 如果模型返回的 JSON 被包在代码块里或有轻微格式问题，客户端会自动进行一次 JSON 修复重试

**任务结构示例**：
```json
{
  "page": 1,
  "chapter": 1,
  "scene": "第一天到设计公司报到",
  "user_role": "Lin Xiao",
  "ai_role": "Alex",
  "mission_summary": "在办公室场景中，从打招呼...到表达学习意愿...",
  "must_hit_beats": [
    {
      "id": "beat_1_greet_introduce",
      "label": "Greet and introduce yourself",
      "label_zh": "打招呼并介绍自己",
      "intent": "greet_introduce",
      "acceptance_criteria": "Learner greets the mentor and introduces themself in any natural wording.",
      "example_phrases": ["Hi, I'm Lin Xiao. Nice to meet you!"],
      "source_dialogue_indices": [1]
    },
    {
      "id": "beat_2_explain_arrival",
      "label": "Explain arriving early or timing",
      "label_zh": "解释到达时间或早到原因",
      "intent": "explain_arrival",
      "acceptance_criteria": "Learner explains they came ahead of time or cared about not being late.",
      "example_phrases": ["I arrived 15 minutes early because I didn't want to be late."],
      "source_dialogue_indices": [3]
    }
  ],
  "target_phrases": [
    "Hi, I'm Lin Xiao. Nice to meet you!",
    "I arrived 15 minutes early because...",
    "To be honest, I'm a bit nervous..."
  ],
  "vocabulary_focus": ["introduce", "nervous", "excited", "learn"],
  "estimated_turns": 12,
  "language_level": "B1",
  "director_mode": "llm_semantic_v1",
  "success_rule": "Complete all must_hit_beats semantically in order; exact wording is not required."
}
```

**完成后报告**：
```
✅ 第9步完成：对话任务已生成
   - 任务文件数：{mission_count}
   - 保存位置：$TASK_DIR/missions/
   - 用途：支持自由对话模式的故事引导
```

**更新进度**：
```bash
# 脚本会自动更新 progress.json 中的 conversation_missions 状态
```

### 第10步：生成HTML预览

数据整合完成后，生成可视化预览HTML页面，方便快速查看所有内容。

使用辅助脚本：
```bash
/Users/zhanghua/.claude/skills/cd-generator/scripts/generate_preview.sh "$TASK_DIR"
```

**预览页面包含**：
- 顶部：故事标题、类型、语言难度、预计时长（居中）
- 情感曲线：每章 SVG 可视化图表，展示情感变化轨迹
- 角色卡片：每个角色的视觉描述和性格
- 每章每页：左侧图片（220px宽）+ 右侧英文图片提示词、中文图片提示词、对话（统一居中布局）
- 对话：双列网格排列（中英双语）

**页面设计规范（精确 CSS）：
```css
/* 页面居中约束 */
body { background: #0f0f0f; color: #e0e0e0 }
.chapter { margin: 32px auto; max-width: 1200px; text-align: center }
.page { display: block; width: 100%; max-width: 1200px; margin-left: auto; margin-right: auto; margin-bottom: 40px; background: #1a1a2e; border-radius: 16px; padding: 24px; border: 1px solid #2a2a4a }

/* 左图右文布局 */
.page-body { display: flex; gap: 24px; width: 100%; max-width: 1152px }
.page-img { flex-shrink: 0; width: 220px; display: flex; flex-direction: column }
.page-img img { width: 100%; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5) }
.page-right { flex: 1; min-width: 0; max-width: 880px; overflow: hidden }

/* 文字约束（防止溢出撑破布局） */
.dlg { display: flex; gap: 8px; padding: 6px 10px; background: #111; border-radius: 6px; min-width: 0 }
.dlg-body { flex: 1; min-width: 0 }
.dlg-zh { color: #ddd; font-size: 13px; overflow-wrap: break-word; word-break: break-word; min-width: 0 }
.dlg-en { color: #888; font-size: 11px; overflow-wrap: break-word; word-break: break-word; min-width: 0 }
.dialogues-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5px 12px; min-width: 0; overflow: hidden }
.prompt-text { overflow-wrap: break-word; word-break: break-word }
.prompt-text-zh { overflow-wrap: break-word; word-break: break-word }
```
- **核心原则**：每个 flex 子元素都要有 `min-width: 0` 防止溢出
- **居中**：`margin-left: auto; margin-right: auto` 或 `margin: auto`（块级元素）
- **约束**：`max-width` + `overflow: hidden` 双重保险

**完成后**：
```bash
open "$TASK_DIR/output/preview.html"
```

```
✅ 第10步完成：HTML预览已生成
   - 预览文件：$TASK_DIR/output/preview.html
   - 已在浏览器中打开
```

### 第11步：生成 Story-Guided 详细报告（可选）

如果已经生成 `missions/`，可以生成一份更详细的调试报告，用来检查图片、提示词、对话、mission 和质检结果之间的匹配程度。

```bash
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/generate_story_guided_report.py "$TASK_DIR" --force
```

生成后会自动用系统默认浏览器打开报告；批处理时可加 `--no-open` 只生成不打开。

**输出**：
- `$TASK_DIR/output/story_guided_report.html`：自包含 HTML，嵌入实际图片和所有中间数据。
- `$TASK_DIR/quality/story_guided_alignment_report.json`：模型生成的页面级匹配评分。

**报告包含**：
- 实际生成图片
- 英文 `image_prompt` 和中文 `image_prompt_zh`
- 每页对话和中英翻译
- Story-Guided mission、beats、target phrases
- 内容质检问题
- 图片提示词/对话/mission 的匹配评分和问题说明

## 完整工作流程总结

```
第0步：初始化任务目录 ✅
   ↓
第1步：故事策划 ✅ → 报告进度
   ↓
第2步：逐章创作剧本 ✅ → 每章报告进度
   ↓
第3步：分镜设计 ✅ → 每3个报告进度
   ↓
第4步：提取并保存提示词 ✅ → 报告进度
   ↓
第9步：生成对话任务 ✅（可选；如需要 Story-Guided，建议在质检前生成）
   ↓
第5步：内容质检 ✅
   ↓
第6步：智能图片生成 ✅
   ├─ 6.1 提示词质量预检
   ├─ 6.2 批量提交请求 → 每个报告
   ├─ 6.3 自动监控循环 → 每轮报告
   ├─ 6.4 智能重试机制 → 失败时自动处理
   └─ 6.5 完成报告
   ↓
第7步：手动处理失败图片（如有）
   ↓
第7.5步：批量下载已生成的图片 ✅（OpenCLI 模式专用）
   ↓
第8步：数据整合 ✅ → 报告进度
   ↓
第10步：生成HTML预览 ✅
   ↓
第11步：生成 Story-Guided 详细报告 ✅（可选）
```

**关键特性**：
- ✅ 严格的顺序控制：数据准备 → 图片生成
- ✅ 实时进度报告：每个关键节点都报告
- ✅ 质量预防：提交前检查提示词质量
- ✅ 自动监控：无需手动干预
- ✅ 智能重试：失败自动优化重试
- ✅ 完整日志：所有操作可追溯
- ✅ HTML预览：最终输出可视化预览页面
- ✅ 对话任务：支持 Story-Guided Free Talk 模式，并可纳入内容质检

## 提示词优化指南

### 好的提示词特征

✅ **简洁清晰**：
```
16:9 widescreen manga scene with three vertical zones. LEFT 25%: modern office entrance with morning light and a nervous young designer holding a tote bag. CENTER 55%: the designer and mentor shake hands beside a reception desk, friendly eye contact and one short English speech bubble, "Welcome aboard." RIGHT 20%: close-up of the handshake and a badge on the desk. Modern manga style, bright professional atmosphere, all visible text English only.
```

✅ **结构化**：明确使用 LEFT/CENTER/RIGHT 或 diagonal zones，适合 16:9 横版背景

✅ **具体但不过度**：描述关键元素，不要过多细节

### 需要避免的提示词

❌ **过多特效**：
```
stress lines, determination sparkles, dramatic shadows, light bulb effect, success stars, approval checkmarks
```

❌ **过于复杂的场景**：
```
multiple coffee cups, crumpled papers scattered everywhere, elaborate designs with complex details and flourishes
```

❌ **复杂的情绪转换**：
```
dejection → enlightenment → triumph (一张图里包含太多情绪变化)
```

### 优化示例

**原始（失败）**：
```
16:9 widescreen manga scene with too many events: the designer fails, learns a lesson, suddenly understands, presents a final logo, the client approves, everyone celebrates with sparkles, light bulb effects, dramatic shadows, golden triumph lighting, and many speech bubbles across the whole image.
```

**优化后（成功）**：
```
16:9 widescreen manga scene with a diagonal split from lower-left to upper-right. LEFT 30%: young designer at a desk, one rough logo sketch and a crossed-out note. CENTER 50%: mentor points calmly at the screen while the designer revises the logo, focused expressions and one short English speech bubble, "Let's simplify it." RIGHT 20%: close-up of the cleaner logo version on the monitor. Modern manga style, clean composition, all visible text English only.
```

**改进点**：
- 去掉 "light bulb effect", "celebration effects", "golden triumph lighting"
- 简化情绪描述："dejection → enlightenment → triumph" 改为直接描述画面
- 保持核心构图和人物动作

## 进度报告规范

**必须**在以下时机报告进度：

1. 每完成一个主要步骤（第1-8步）
2. 章节剧本：每章完成后
3. 分镜设计：每3个完成后
4. 图片提交：每个请求提交后
5. 图片检查：每个图片检查后

**报告格式**：
```
✅ [步骤名称]：[具体内容]
   - [关键指标1]
   - [关键指标2]
   - [关键指标3]
```

## 错误处理

### 图片生成失败

1. **检测失败**：页面包含错误信息
   - "I was unable to generate the image"
   - "encountered an error"
   - "抱歉"

2. **处理流程**：
   - 标记为失败状态
   - 分析提示词问题
   - 优化提示词
   - 重新提交请求
   - 更新链接记录

### 图片生成超时

1. **检测超时**：10分钟后仍无图片
2. **处理流程**：
   - 标记为超时
   - 优化提示词（可能过于复杂）
   - 重新提交请求

## 使用示例

### 完整工作流：从批量筛选到成品

#### 第一阶段：批量生成和评分（模式A）

```bash
# 步骤1：用户提供故事方向
# 例如："职场新人设计师的成长故事，要有真实的工作场景和人际关系"

# 步骤2：批量生成10个故事大纲
/cd-generator --batch \
  --theme "设计师的第一步" \
  --batch-size 10 \
  --genre workplace \
  --level B1

# 步骤3：为每个大纲生成内容（自动调用 /shanyin-write）
# 系统会自动生成10个不同角度的故事大纲

# 步骤4：批量评分
# 系统自动调用评分脚本，生成排名报告

# 步骤5：用户查看评分报告
# 报告包含：排名、平均分、优缺点、推荐度
# 用户选择1-2个最佳剧本继续开发
```

**预期输出**：
- 10个故事大纲（story_outline.json）
- 10个评分报告（story_score.json）
- 1个对比报告（batch_score_comparison.json）
- 推荐继续开发的剧本列表

**预计时间**：30-40分钟

#### 第二阶段：完整生成（模式B）

```bash
# 步骤6：用户选择最佳剧本（例如选择了第3个）
# 继续完整流程

/cd-generator --continue <task_dir_3>

# 或者从头开始生成单个完整剧本
/cd-generator \
  --theme "设计师的第一步" \
  --genre workplace \
  --level B1 \
  --chapters 6 \
  --pages 24
```

**完整流程**：
1. 生成详细剧本（每章24页，每页12-16句对话）
2. 生成分镜描述（16:9横版，左/中/右分区）
3. 提取中英文图片提示词
4. 内容质检（对话、提示词、角色一致性）
5. 批量生成图片（144张，约2-3小时）
6. 数据整合（final_output.json）
7. 生成HTML预览

**预期输出**：
- 6章完整剧本（144页）
- 144个分镜描述
- 144个英文提示词 + 144个中文提示词
- 144张图片
- 1个完整数据文件（可导入 Scene2Talk）
- 1个HTML预览页面

**预计时间**：3-4小时

#### 第三阶段：导入 Scene2Talk

```bash
# 步骤7：将生成的数据导入 Scene2Talk 项目
# 使用 final_output.json 中的数据
# 包含：故事信息、角色、章节、页面、对话、图片路径

# Scene2Talk 使用这些数据进行英语口语练习
```

### 快速测试模式

```bash
# 测试批量模式（3个变体，2章×3页）
/cd-generator --batch \
  --theme "咖啡店的故事" \
  --batch-size 3 \
  --genre workplace \
  --level A2 \
  --chapters 2 \
  --pages 3

# 测试完整模式（2章×3页）
/cd-generator \
  --theme "咖啡店的故事" \
  --genre workplace \
  --level A2 \
  --chapters 2 \
  --pages 3
```

**预期输出**：
- 批量模式：3个大纲 + 评分报告（5-10分钟）
- 完整模式：6页完整内容 + 6张图片（15-25分钟）

---

**版本**：v2.9.0
**更新日期**：2026-05-01
**主要改进**：
- **新增批量生成和评分功能**
  - 新增 `scripts/score_story_outline.py`：使用 LLM 对故事大纲进行多维度评分
  - 新增 `scripts/batch_generate_outlines.sh`：批量生成多个故事大纲变体
  - 新增 `BATCH_SCORING.md`：批量生成和评分功能文档
  - 支持生成10个剧本变体，评分后选择最佳的1-2个继续开发
- **理清图片生成架构**
  - 明确 cd-generator 使用自己的 `smart_image_manager.sh`
  - `/chatgpt-image` skill 仅用于单图请求，不参与批处理
  - 更新依赖 Skills 说明，移除对 `/chatgpt-image` 的调用
- **评分维度**（每项0-10分）
  - 故事吸引力、角色设定、冲突设计
  - 口语练习适配度、情感曲线
  - 职场真实性、创意新颖度
- **对齐 shanyin-write 接口**
  - 明确 `/shanyin-write` 在 `cd-generator Mode` 下的故事策划和单章剧本输入字段
  - 强化 JSON-only、不暂停确认和 Scene2Talk 口语练习输出约束
- **对齐 shanyin-direct 接口**
  - 明确 `/shanyin-direct` 在 `cd-generator Mode` 下的输入字段和输出 JSON
  - 统一分镜为 16:9 横版 left/center/right 或 diagonal zones
  - 移除旧的竖版 `TOP/MIDDLE/BOTTOM` 和 top/bottom safe-band 强约束
- **完成历史错放数据清理**
  - 确认 `20260429_235435_bakery_adventure` 已保留在 skill 正确输出目录
  - 旧项目 worktree 副本已移出原路径，项目侧只保留迁移说明
- **修复输出目录污染**
  - 新增 `scripts/task_path_guard.py`，统一规范 `TASK_DIR`
  - 主要脚本在写入前都会拒绝 Sense Talk 项目/worktree 下的 `cd_generator_output`
  - 相对路径 `cd_generator_output/<task>` 会映射到 `/Users/zhanghua/.claude/skills/cd-generator/output/<task>`
- **版本与主项目解耦**
  - 新增 `skill-version.json` 作为 `cd-generator` 的机器可读版本源
  - 明确本 skill 版本不等于 Sense Talk / Scene2Talk 主项目 `package.json` 版本
  - 整理本 skill 的 `.gitignore`，忽略本地任务输出、日志、密钥和缓存，避免生成产物混入技能版本

**历史版本**：
- v2.8.4: 对齐 shanyin-write 和 shanyin-direct 接口
- v2.8.3: 对齐 shanyin-direct 的 16:9 横版 storyboard JSON 契约
- v2.8.2: 清理历史错放数据副本，确认项目侧只保留迁移说明
- v2.8.1: 增加 TASK_DIR 路径护栏，阻止生成数据写入 Sense Talk 项目 worktree
- v2.8.0: 增加 skill 独立版本源和版本边界，避免与 Sense Talk 主项目版本混用
- v2.7: 增加第7.5步批量下载已生成图片，支持 OpenCLI 模式下从 ChatGPT 对话链接提取并下载图片
- v2.5: 增加 YouMind API 图片生成模式、HTML 预览、Story-Guided 详细报告
- v2.4: 分离数据准备和图片生成、Story-Guided Free Talk 支持、内容质检
- v2.3: 基础漫剧生成功能

## Story-Guided Free Talk 系统

Story-Guided Free Talk 的目标是：用户可以自由说，不必背固定台词；系统在后台用 `must_hit_beats` 追踪剧情节点，必要时温和提示或拉回。

**技能内已有三个辅助文件**：
- `scripts/llm_json_client.py`：OpenAI-compatible JSON 模型客户端，统一承接语义审稿、mission 抽取和 director 判断。
- `scripts/generate_conversation_missions.py`：用模型从章节剧本生成每页 mission。
- `scripts/conversation_director.py`：用模型判断用户是否语义完成当前 beat。
- `scripts/story_guided_integration.ts`：框架无关的 TypeScript 类型和 prompt builder，作为后续接入主项目的参考，不直接调用主项目运行时代码。

**mission 约定**：
- `user_role`、`ai_role`、`target_phrases` 由模型根据故事角色和页面对话判断，脚本会过滤明显舞台/系统角色。
- `must_hit_beats` 必须是结构化对象，至少包含 `id`、`label`、`label_zh`、`intent`、`acceptance_criteria`。
- `acceptance_criteria` 是语义验收标准，不是关键词列表；用户自然改写也应该被接受。
- `intent` 只接受固定枚举；如果模型返回未知 intent，会保留到 `model_intent_raw`，标准字段写为 `other_goal`。

**Director 引导模式**：
- `continue`：当前节点完成，自然推进到下一节点。
- `redirect`：用户偏题，先短暂回应，再拉回当前节点。
- `hint`：同一节点多轮未完成，给出轻提示。
- `encourage`：还在当前节点内，继续鼓励表达。
- 模型调用失败时不会崩溃，也不会用关键词规则乱判完成；会安全返回 `beat_completed=false` 和 `encourage/hint`。

**模型配置示例**：
`config/llm.env` 已加入 `.gitignore`，不要提交。

```bash
# Claude 网关 / Anthropic Messages 风格
CD_GENERATOR_LLM_BASE_URL=https://your-domain.example.com/claude/v1/messages
CD_GENERATOR_LLM_MODEL=claude-sonnet-4-6
CD_GENERATOR_LLM_API_KEY=your-key
CD_GENERATOR_LLM_ENDPOINT_MODE=claude

# Ollama 本地 OpenAI-compatible 服务
CD_GENERATOR_LLM_BASE_URL=http://localhost:11434/v1
CD_GENERATOR_LLM_MODEL=llama3.2:3b
CD_GENERATOR_LLM_API_KEY=ollama
CD_GENERATOR_LLM_ENDPOINT_MODE=openai

# OpenAI-compatible 云端服务
CD_GENERATOR_LLM_BASE_URL=https://api.openai.com/v1
CD_GENERATOR_LLM_MODEL=gpt-4o-mini
CD_GENERATOR_LLM_API_KEY=sk-...
CD_GENERATOR_LLM_ENDPOINT_MODE=openai
```

**验证命令**：
```bash
python3 /Users/zhanghua/.claude/skills/cd-generator/scripts/test_story_guided.py
python3 -m py_compile /Users/zhanghua/.claude/skills/cd-generator/scripts/*.py
bash -n /Users/zhanghua/.claude/skills/cd-generator/scripts/*.sh
```
预期：单元测试显示 `OK`，编译和 shell 语法检查无输出即通过。

**性能指引**：
- `smart_image_manager.sh` 提示词质量检查：每张图片约 1-2 次模型调用（检查 + 可能的优化）
- `generate_conversation_missions.py`：每页约 1 次模型调用。
- `validate_content.sh`：每页约 1 次模型调用。
- `generate_story_guided_report.py --force`：每页约 1 次匹配审稿调用；不加 `--force` 会复用缓存。
- `ConversationDirector.analyze_user_input()`：每轮用户输入 1 次模型调用；本地小模型延迟通常取决于硬件，云端取决于网关和模型。

**后续升级方向**：
1. 收集模型误判样本，给每个 beat 增加 `acceptance_examples`、`reject_examples`、`hint_phrases`。
2. 为常见口语场景沉淀少量 prompt 模板，让模型判断更稳定。
3. 后续接入主项目时，把 `ConversationDirector` 的模型调用替换成主项目统一 AI service。

**主项目集成边界**：
- 当前 skill 只提供 mission 生成、director 判断、报告生成和 TypeScript helper。
- `scripts/story_guided_integration.ts` 提供 `StoryGuidedReplyAdapter`，后续主项目只需要实现 `generateReply()` 去调用现有语音/AI 回复接口。
- 主项目接入时再确认 `generateEnglishAssistantReply` 或等价函数的参数、对话历史结构、UI 进度状态，不在 skill 仓库里直接修改主项目代码。
