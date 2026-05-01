# Comic Drama Generator - 优化总结

## 📋 优化概览

本次优化彻底重构了漫剧生成器的工作流程，实现了智能化、自动化的图片生成管理。

## 🎯 核心改进

### 1. 严格的工作流程控制

**之前的问题**：
- 边生成数据边生成图片，导致混乱
- 重复提交相同的图片请求
- 无法追踪哪个提示词对应哪个图片

**现在的方案**：
```
第1-4步：数据准备（故事、剧本、分镜、提示词）
   ↓
第5步：智能图片生成（一键完成提交、监控、下载）
   ↓
第6-7步：数据整合
```

### 2. 提示词质量管理

**提示词单独保存**：
- 每个分镜同时产出英文和中文提示词
- 英文位置：`$TASK_DIR/prompts/chapterX_pageY.txt`，实际图片生成只使用英文
- 中文位置：`$TASK_DIR/prompts_zh/chapterX_pageY.txt`，HTML预览直接展示中文，不临时翻译

**质量预检机制**：
提交前自动检查：
- ❌ 过多特效词汇（sparkle, light bulb, dramatic shadow）
- ❌ 提示词过长（>80词）
- ❌ 复杂情绪转换（→ 符号）
- ✅ 发现问题自动优化

### 3. 智能图片生成管理器

**核心脚本**：`smart_image_manager.sh`

**功能特性**：

#### 3.1 提交阶段
- 遍历所有分镜文件
- 质量预检每个提示词
- 自动优化有问题的提示词
- 记录所有链接到 `image_links.json`

#### 3.2 监控阶段
- 自动进入监控循环（每1分钟检查一次）
- 检测三种状态：READY、ERROR、PENDING
- 发现完成立即下载
- 每轮检查后报告进度

#### 3.3 重试机制
- 失败时自动优化提示词
- 重新提交请求
- 最多重试2次
- 超过次数标记为最终失败

#### 3.4 完成报告
- 显示成功、失败、生成中的数量
- 列出所有失败图片的链接
- 生成详细日志文件

### 4. 实时进度报告

**报告时机**：
- 每完成一个主要步骤
- 章节剧本：每章完成后
- 分镜设计：每3个完成后
- 图片提交：每个请求提交后
- 图片检查：每轮检查后

**报告格式**：
```
✅ [步骤名称]：[具体内容]
   - [关键指标1]
   - [关键指标2]
```

### 5. 完整的日志系统

**日志文件**：`$TASK_DIR/image_generation.log`

**记录内容**：
- 每个操作的时间戳
- 提示词质量检查结果
- 优化操作详情
- 提交和下载结果
- 失败原因分析

## 📁 文件组织结构

```
/Users/zhanghua/.claude/skills/cd-generator/
├── SKILL.md                          # 主文档（已优化）
├── scripts/
│   ├── smart_image_manager.sh       # 智能图片生成管理器（新）
│   ├── generate_images.sh           # 简单批量提交（旧，保留）
│   ├── check_and_download.sh        # 手动检查下载（旧，保留）
│   └── check_images.sh              # 单个图片检查（旧，保留）
└── output/
    └── YYYYMMDD_HHMMSS_任务名称/
        ├── README.md
        ├── data/
        │   ├── story_outline.json
        │   └── progress.json
        ├── scripts/
        │   ├── chapter1.json
        │   └── chapter2.json
        ├── storyboards/
        │   ├── chapter1_page1.json
        │   └── ...
        ├── prompts/                  # 英文提示词目录，用于图片生成
        ├── prompts_zh/               # 中文提示词目录，用于HTML预览
        │   ├── chapter1_page1.txt
        │   └── ...
        ├── images/
        │   └── (生成的图片)
        ├── image_links.json          # 新增：链接记录
        ├── image_generation.log      # 新增：详细日志
        └── output/
            └── final_output.json
```

## 🚀 使用方式

### 完整流程

```bash
# 1. 初始化任务
TASK_ID="$(date +%Y%m%d_%H%M%S)_设计师的第一步"
TASK_DIR="/Users/zhanghua/.claude/skills/cd-generator/output/$TASK_ID"
mkdir -p "$TASK_DIR"/{data,scripts,storyboards,prompts,prompts_zh,images,output}

# 2-4. 生成数据（故事、剧本、分镜、提示词）
# ... 使用 shanyin-write 和 shanyin-direct ...

# 5. 一键智能图片生成
/Users/zhanghua/.claude/skills/cd-generator/scripts/smart_image_manager.sh "$TASK_DIR"

# 脚本会自动：
# - 提交所有请求（带质量检查）
# - 监控生成状态（每1分钟）
# - 下载完成的图片
# - 重试失败的图片
# - 生成最终报告

# 6. 数据整合
# ... 整合所有数据到 final_output.json ...
```

### 配置参数

在 `smart_image_manager.sh` 中可调整：

```bash
CHECK_INTERVAL=60     # 检查间隔（秒），默认1分钟
MAX_WAIT_TIME=1200    # 最大等待时间（秒），默认20分钟
MAX_RETRIES=2         # 最大重试次数，默认2次
```

## 🔍 提示词优化指南

### 好的提示词特征

✅ **简洁清晰**：
```
Vertical 1:3 manga panel. TOP: Modern office building exterior, young woman at entrance. MIDDLE: Woman and man shaking hands, welcoming gesture. BOTTOM: Close-up handshake, friendly smiles. Modern manga style, bright professional atmosphere.
```

✅ **结构化**：明确分为 TOP/MIDDLE/BOTTOM 三部分

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

### 自动优化规则

智能管理器会自动：
1. 去除特效词汇（sparkle, light bulb effect, dramatic shadow, stress line, celebration effect）
2. 简化复杂描述（"with complex details and flourishes" → "with details"）
3. 去除情绪转换符号（"→" → " to "）

## 📊 监控示例

```
🎨 智能图片生成管理器启动
📁 任务目录: /path/to/task

━━━ 第一阶段：提交图片生成请求 ━━━
📤 提交: 第1章第1页 (尝试 1)
✅ 已提交: https://chatgpt.com/c/...
📤 提交: 第1章第2页 (尝试 1)
⚠️ 提示词质量警告，自动优化...
✓ 优化后: Vertical 1:3 manga panel...
✅ 已提交: https://chatgpt.com/c/...
...
✅ 所有请求已提交

━━━ 第二阶段：自动监控和下载 ━━━
⏰ 每 1 分钟检查一次

🔍 第 1 轮检查 (已等待 1 分钟)
   第1章第1页: ✅ 已生成，开始下载...
   ✓ 下载完成 (3.5M)
   第1章第2页: ⏳ 生成中...
   第1章第3页: ❌ 生成失败
   🔄 准备重试 (1/2)
   ...

📊 当前状态: ✅ 1 | ⏳ 2 | ❌ 0

⏰ 等待 1 分钟后进行下一轮检查...

🔍 第 2 轮检查 (已等待 10 分钟)
   ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 最终报告
   ✅ 成功: 5 张
   ❌ 失败: 1 张
   📁 保存位置: /path/to/images
   📋 详细记录: /path/to/image_links.json
   📝 日志文件: /path/to/image_generation.log
```

## 🎓 设计理念

### 合理性
- 严格的工作流程顺序
- 数据准备与图片生成分离
- 提示词质量预防机制

### 控制性
- 完整的状态管理（pending → retrying → completed/failed）
- 所有操作可追溯（日志文件）
- 清晰的文件组织结构

### 监控性
- 实时进度报告
- 每轮检查后状态更新
- 详细的日志记录

### 兜底性
- 最大等待时间限制（20分钟）
- 失败自动重试（最多2次）
- 最终报告列出所有失败项

### 自进化
- 从失败中学习（自动优化提示词）
- 质量预防（提交前检查）
- 持续改进（日志分析）

## 🔄 与旧版本的对比

| 特性 | 旧版本 | 新版本 |
|------|--------|--------|
| 工作流程 | 边生成数据边生成图片 | 严格分离：数据→图片 |
| 提示词管理 | 只在JSON中 | 单独保存为.txt文件 |
| 质量控制 | 失败后手动优化 | 提交前自动检查 |
| 监控方式 | 手动运行脚本 | 自动监控循环 |
| 重试机制 | 手动重试 | 自动重试（最多2次）|
| 进度报告 | 无或不完整 | 实时详细报告 |
| 日志记录 | 无 | 完整日志文件 |

## 📝 后续优化方向

1. **提示词模板库**：预定义常见场景的提示词模板
2. **成功率统计**：分析哪类提示词成功率高
3. **并行生成**：支持多个任务并行处理
4. **Web界面**：可视化监控和管理
5. **A/B测试**：同一场景生成多个版本对比

---

**版本**：v2.8.4
**更新日期**：2026-05-01
**版本范围**：仅限 `cd-generator` skill，与 Sense Talk / Scene2Talk 主项目版本分开
**作者**：Claude (Sonnet 4.6)
