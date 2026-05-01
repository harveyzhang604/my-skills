---
name: chatgpt-image
description: Use when generating images through OpenCLI and ChatGPT Image, including single-image requests and cd-generator batch image generation support.
trigger: 当用户想要使用 ChatGPT 生成图片时
---

# ChatGPT Image Generator Skill

使用 OpenCLI 调用 ChatGPT Image 2 生成图片的 skill。

## 核心功能

1. 接收用户提示词（单图请求原样传递；被 `cd-generator` 调用时使用其英文 `prompts/` 文件）
2. 调用 `opencli chatgpt image` 命令提交生成请求
3. 实现智能循环检查机制：
   - 第1次检查：等待 5 分钟
   - 第2次检查：再等待 7 分钟
   - 第3次检查：再等待 10 分钟
4. 图片生成完成后自动下载到指定位置
5. 返回生成的图片文件路径或 ChatGPT 链接

## 使用流程

### 步骤 1: 接收参数

从用户输入中提取：
- `prompt`: 图片生成提示词（必需）
- `output_dir`: 输出目录（可选，默认为 `~/Pictures/chatgpt`）

### 步骤 2: 执行生成命令

```bash
opencli chatgpt image "<prompt>" --op <output_dir> --verbose
```

### 步骤 3: 循环检查机制

实现三次检查循环：

```bash
# 第1次检查（5分钟后）
sleep 300
result1=$(opencli chatgpt image "<prompt>" --op <output_dir> --verbose 2>&1)

# 检查是否成功
if [[ "$result1" == *"✓"* ]]; then
  echo "图片生成完成"
  exit 0
fi

# 第2次检查（再等7分钟）
sleep 420
result2=$(opencli chatgpt image "<prompt>" --op <output_dir> --verbose 2>&1)

if [[ "$result2" == *"✓"* ]]; then
  echo "图片生成完成"
  exit 0
fi

# 第3次检查（再等10分钟）
sleep 600
result3=$(opencli chatgpt image "<prompt>" --op <output_dir> --verbose 2>&1)

if [[ "$result3" == *"✓"* ]]; then
  echo "图片生成完成"
  exit 0
fi

# 三次检查都未完成
echo "⚠️ 图片生成超时，请手动访问链接查看"
```

### 步骤 4: 返回结果

- 成功：返回图片文件路径
- 超时：返回 ChatGPT 对话链接

## 实现要点

1. **默认不优化用户提示词**：单图请求中，用户提供的提示词必须原样传递给 ChatGPT。
2. **cd-generator 批处理例外**：如果由 `cd-generator` 调用，图片生成由 `/Users/zhanghua/.claude/skills/cd-generator/scripts/smart_image_manager.sh` 统一管理；此时只读取 `prompts/` 里的英文提示词，不读取 `prompts_zh/`，也不要把英文提示词翻译成中文。
3. **足够的等待时间**：图片生成需要较长时间，必须设置足够的超时时间
4. **循环检查**：不能一次性等待，要分三次检查，每次间隔不同时间
5. **错误处理**：如果三次检查都未完成，提供 ChatGPT 链接供用户手动查看

## 依赖要求

- OpenCLI 已安装并配置
- 已登录 ChatGPT 网页版（chatgpt.com）
- ChatGPT 账号支持 Image 2 功能

## 示例用法

```bash
# 使用默认提示词
/chatgpt-image

# 使用自定义提示词
/chatgpt-image "东方美女抖音带货视频"

# 指定输出目录
/chatgpt-image "科技感未来城市" --output ~/Desktop/ai-images
```

## 16:9宽屏漫画分镜设计规范

**重要**：所有提示词必须是16:9宽屏比例！

### 分镜原则

1. **禁止上下分区**：宽屏不适合上下分区，会显得画面狭长
2. **使用垂直或斜向分区**：根据内容灵活选择
3. **主场景占60-70%**：突出主要内容
4. **副场景占30-40%**：补充远景/特写/细节

### 推荐分镜模式

#### 模式A：左侧大主场景 + 右侧上下小场景
```
┌─────────┬───────┐
│         │ 上小  │
│  主场景  │ (50%) │
│ (60-70%)│       │
│         ├───────┤
│         │ 下小  │
│         │ (50%) │
└─────────┴───────┘
```
- 适用：单人情感表达、远景→主体→特写叙事

#### 模式B：垂直三分割（远景-主场景-特写）
```
┌─────┬─────────┬─────┐
│远景 │ 主场景   │特写 │
│25%  │ (50%)   │25%  │
└─────┴─────────┴─────┘
```
- 适用：多人互动、重逢场景、对比画面

#### 模式C：斜向动态分区
```
┲━━━━━━━━━━━━━━━
   ╲  主场景   ╱
    ╲   60%   ╱
     ╲       ╱
      ╲下特写╱
       ╲   ╱
```
- 适用：动态场景、情绪递进、叙事感

### 构图要素

- **远景/Establishing shot**：交代环境、氛围
- **主场景/Main scene**：人物互动、核心动作
- **特写/Close-up**：表情细节、关键道具、情感高潮
- **对话气泡**：每页1-3个短英文气泡，不要超过3个

### 示例提示词结构

```
16:9 widescreen manga panel. [分区方式描述]. [主场景描述]. [副场景描述]. [氛围/风格]. Speech bubbles: '英文对话1' and '英文对话2'. Modern manga style. English text only.
```

### 常见错误

❌ 上下分区（40%/60%）——宽屏不适合
❌ 单一场景无层次——缺少远景和特写
❌ 过多对话气泡（>3个）——画面拥挤
❌ 中文/日文/韩文文字——只允许英文

## 注意事项

1. 确保 ChatGPT 账号已登录且 cookie 有效
2. 图片生成时间通常需要 5-15 分钟
3. 如果网络不稳定，可能需要更长时间
4. 建议在后台运行，避免阻塞其他任务
