---
name: chatgpt-image
description: Use when generating, checking, or downloading ChatGPT Image outputs through OpenCLI, either for a direct single-image user request or as a reusable image service called by another skill.
trigger: 当用户要用 ChatGPT Image/OpenCLI 生成图片、检查图片状态、下载图片，或其它 skill 需要复用生图能力时
---

# ChatGPT Image Generator Skill

这个 skill 是独立的 ChatGPT Image 生图模块。它不负责故事、分镜、批量进度或任务目录，只负责“一张图”的 OpenCLI 操作：提交提示词、检查 ChatGPT 链接状态、下载生成图片。

## 职责边界

- `chatgpt-image`：单图服务层，封装 OpenCLI、链接解析、浏览器挂接修复、状态检查、下载保存。
- `cd-generator`：编排层，负责批量、提示词质检、节流、`image_links.json`、进度、任务目录和最终审查；每张图的 OpenCLI 操作调用本 skill 的服务脚本。
- 其它 skills：如果需要生图，也应调用本 skill，不要复制 OpenCLI 提交/检查/下载逻辑。

## 核心脚本

```bash
/Users/zhanghua/.claude/skills/chatgpt-image/scripts/opencli_image_service.py
```

命令：

```bash
# 提交一张图，返回 ChatGPT 对话链接 JSON
python3 "$SERVICE" submit --prompt "$PROMPT" --repair-retries 2

# 检查链接里的图片是否生成
python3 "$SERVICE" status --link "$CHATGPT_LINK" --repair-retries 1

# 下载已生成图片到指定文件
python3 "$SERVICE" download --link "$CHATGPT_LINK" --output "$OUTPUT_FILE" --repair-retries 1

# 单图端到端生成：提交、等待、下载
python3 "$SERVICE" generate --prompt "$PROMPT" --output "$OUTPUT_FILE" --wait-schedule "60,60,60,120,180"
```

所有命令都输出 JSON，调用方必须按 JSON 解析，不要 grep OpenCLI 原始输出。

## 用户单图入口

```bash
/Users/zhanghua/.claude/skills/chatgpt-image/run.sh "提示词" "$HOME/Pictures/chatgpt"
```

默认不改写用户提示词。调用方如果需要风格、比例、安全区或双语气泡约束，应在调用前自己生成好最终 prompt。

## 输出约定

常见字段：

- `ok`: 操作是否成功。
- `status`: `pending`、`READY:宽x高`、`PENDING`、`ERROR`、`completed`、`submit_failed`、`download_failed`。
- `link`: ChatGPT 对话链接。
- `warning`: OpenCLI 返回异常但已经拿到链接时的警告。
- `submit_exit_code`、`submit_attempts`、`opencli_repaired`: 供批量编排记录和诊断。
- `output_path`、`file_size`: 下载成功时返回。
- `error`: 失败原因。

## 稳定性策略

- OpenCLI 浏览器挂接异常会自动执行 `opencli browser close` 和 `opencli doctor` 后重试。
- 如果 OpenCLI 输出里已经包含 ChatGPT 链接，即使命令 exit code 非 0，也返回 `ok: true` 并附带 `warning`，由调用方后续轮询确认结果。
- 下载时只认本次下载开始后的 PNG，避免误拿 `~/Downloads` 里的旧文件。
- 批量调用方应先提交 1 张验证链路，连续失败时停止提交，避免刷出大量无效请求。

## 16:9 漫画提示词注意

本 skill 可以生成任何图片，但用于 Scene2Talk/cd-generator 时，调用方应提前把 prompt 处理好：

- 16:9 landscape / widescreen。
- 画面内气泡/字幕使用中英双语，英文在上、中文在下。
- 顶部 12% 避开 UI，左右 6% 留安全边距。
- 每个视觉场景最多 2 个气泡，整张图最多 6 个，默认优先 1-3 个。
