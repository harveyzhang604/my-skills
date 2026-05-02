# ChatGPT Image Generator

独立的 ChatGPT Image/OpenCLI 生图服务。它可以直接生成单图，也可以被 `cd-generator` 或其它 skill 复用。

## 单图使用

```bash
/Users/zhanghua/.claude/skills/chatgpt-image/run.sh "你的提示词" "$HOME/Pictures/chatgpt"
```

## 服务脚本

```bash
SERVICE=/Users/zhanghua/.claude/skills/chatgpt-image/scripts/opencli_image_service.py

python3 "$SERVICE" submit --prompt "$PROMPT"
python3 "$SERVICE" status --link "$CHATGPT_LINK"
python3 "$SERVICE" download --link "$CHATGPT_LINK" --output "$OUTPUT_FILE"
python3 "$SERVICE" generate --prompt "$PROMPT" --output "$OUTPUT_FILE"
```

调用方负责批量、任务目录、提示词质检和进度；本服务只负责单张图的提交、检查和下载。
