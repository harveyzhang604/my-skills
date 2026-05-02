#!/bin/bash

# 智能图片生成管理器
# 功能：提交请求 → 自动监控 → 失败重试 → 完成通知
# 支持两种模式：
#   1. opencli (默认): 通过 chatgpt-image skill 的 OpenCLI 服务生成图片
#   2. youmind: 使用 YouMind API 直接生成图片
# 通过 config/youmind.env 中的 YKM_DIRECT_API_MODE 控制

set -e

TASK_DIR="$1"
GUARD="/Users/zhanghua/.claude/skills/cd-generator/scripts/task_path_guard.py"
MAX_RETRIES=2
CHECK_INTERVAL=60  # 1分钟检查一次
MAX_WAIT_TIME=1200  # 20分钟超时
SYNC_SCRIPT="/Users/zhanghua/.claude/skills/cd-generator/scripts/sync_task_status.sh"
SCRIPT_DIR="/Users/zhanghua/.claude/skills/cd-generator/scripts"
CHATGPT_IMAGE_SERVICE="/Users/zhanghua/.claude/skills/chatgpt-image/scripts/opencli_image_service.py"

# 检测图片生成模式
# 读取 youmind.env 配置
YKM_CONFIG_FILE="/Users/zhanghua/.claude/skills/cd-generator/config/youmind.env"
IMAGE_GENERATION_MODE="opencli"  # 默认为 opencli 模式

if [ -f "$YKM_CONFIG_FILE" ]; then
    # 检查是否启用了 YouMind API 模式
    if grep -q "YKM_DIRECT_API_MODE=true" "$YKM_CONFIG_FILE" 2>/dev/null; then
        IMAGE_GENERATION_MODE="youmind"
    fi
fi

if [ -z "$TASK_DIR" ]; then
    echo "用法: $0 <task_dir>"
    exit 1
fi

TASK_DIR="$(python3 "$GUARD" "$TASK_DIR")"

IMAGES_DIR="$TASK_DIR/images"
STORYBOARDS_DIR="$TASK_DIR/storyboards"
PROMPTS_DIR="$TASK_DIR/prompts"
IMAGE_LINKS_FILE="$TASK_DIR/image_links.json"
LOG_FILE="$TASK_DIR/image_generation.log"

mkdir -p "$IMAGES_DIR"

# 输出模式信息
echo "🔧 图片生成模式: $IMAGE_GENERATION_MODE" | tee -a "$LOG_FILE"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

sync_task_status() {
    if [ -x "$SYNC_SCRIPT" ]; then
        "$SYNC_SCRIPT" "$TASK_DIR" | tee -a "$LOG_FILE"
    fi
}

audit_generated_images() {
    local audit_script="$SCRIPT_DIR/audit_generated_images.py"
    if [ -f "$audit_script" ]; then
        log "🔎 运行图片文件审查..."
        python3 "$audit_script" "$TASK_DIR" 2>&1 | tee -a "$LOG_FILE" || true
        log "📄 图片审查报告: $TASK_DIR/quality/image_audit.json"
    fi
}

audit_storyboard_prompts() {
    local audit_script="$SCRIPT_DIR/audit_storyboards.py"
    if [ -f "$audit_script" ]; then
        log "🔎 运行分镜/图片提示词提交前审查..."
        if ! python3 "$audit_script" "$TASK_DIR" 2>&1 | tee -a "$LOG_FILE"; then
            log "🛑 分镜/图片提示词审查未通过，停止 OpenCLI 批量提交。请先修复 quality/storyboard_audit.json。"
            return 1
        fi
        log "✅ 分镜/图片提示词提交前审查通过"
    fi
    return 0
}

image_file_exists() {
    local filename="$1"
    [ -s "$IMAGES_DIR/$filename" ]
}

get_prompt_for_page() {
    local storyboard_file="$1"
    local chapter="$2"
    local page="$3"
    local prompt_file="$PROMPTS_DIR/chapter${chapter}_page${page}.txt"

    if [ -s "$prompt_file" ]; then
        cat "$prompt_file"
        return 0
    fi

    cat "$storyboard_file" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('storyboard', {}).get('image_prompt', ''))" 2>/dev/null || true
}

should_submit_request() {
    local chapter="$1"
    local page="$2"
    local filename="chapter${chapter}_page${page}.png"

    if image_file_exists "$filename"; then
        return 1
    fi

    if [ ! -f "$IMAGE_LINKS_FILE" ]; then
        return 0
    fi

    python3 << EOF
import json, sys
with open("$IMAGE_LINKS_FILE", "r", encoding="utf-8") as f:
    data = json.load(f)
for img in data.get("images", []):
    if int(img.get("chapter", 0)) == $chapter and int(img.get("page", 0)) == $page:
        status = img.get("status")
        link = img.get("link")
        if link and status in {"pending", "retrying", "failed"}:
            sys.exit(1)
        if status == "completed":
            sys.exit(1)
        break
sys.exit(0)
EOF
}

# 提示词质量检查
check_prompt_quality() {
    local prompt="$1"
    PROMPT_TEXT="$prompt" SCRIPT_DIR="$SCRIPT_DIR" python3 << 'PYEOF'
import json
import os
import sys

sys.path.insert(0, os.environ["SCRIPT_DIR"])
from llm_json_client import OpenAICompatibleJSONClient

prompt = os.environ["PROMPT_TEXT"]
result = OpenAICompatibleJSONClient().request_json("audit_image_prompt", {"prompt": prompt})
if result.get("needs_optimization"):
    for issue in result.get("issues", []):
        print(f"- {issue}")
    reason = result.get("reason")
    if reason:
        print(f"- {reason}")
    sys.exit(1)
sys.exit(0)
PYEOF
}

# 优化提示词
optimize_prompt() {
    local prompt="$1"
    PROMPT_TEXT="$prompt" SCRIPT_DIR="$SCRIPT_DIR" python3 << 'PYEOF'
import os
import sys

sys.path.insert(0, os.environ["SCRIPT_DIR"])
from llm_json_client import OpenAICompatibleJSONClient

prompt = os.environ["PROMPT_TEXT"]
result = OpenAICompatibleJSONClient().request_json("optimize_image_prompt", {"prompt": prompt})
print(result.get("optimized_prompt") or prompt)
PYEOF
}

# 使用 YouMind API 直接生成图片
submit_image_request_youmind() {
    local chapter=$1
    local page=$2
    local prompt="$3"
    local retry_count=${4:-0}
    local output_file="$IMAGES_DIR/chapter${chapter}_page${page}.png"

    log "📤 [YouMind API] 提交: 第${chapter}章第${page}页"

    # 调用 Python 脚本生成图片
    set +e
    result=$("$SCRIPT_DIR/youmind_image_client.py" "$prompt" --output "$output_file" --verbose 2>&1)
    exit_code=$?
    set -e

    if [ $exit_code -eq 0 ] && [ -s "$output_file" ]; then
        log "✅ [YouMind API] 图片生成成功: chapter${chapter}_page${page}.png"

        # 记录到 JSON (YouMind 模式不需要链接，直接标记为完成)
        python3 << EOF
import json
import os
from datetime import datetime

links_file = "$IMAGE_LINKS_FILE"

if os.path.exists(links_file):
    with open(links_file, "r") as f:
        data = json.load(f)
else:
    data = {"images": []}

# 检查是否已存在该图片的记录
existing = None
for i, img in enumerate(data["images"]):
    if img["chapter"] == $chapter and img["page"] == $page:
        existing = i
        break

image_data = {
    "chapter": $chapter,
    "page": $page,
    "filename": f"chapter${chapter}_page${page}.png",
    "link": "youmind://generated",
    "prompt": $(echo "$prompt" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))"),
    "status": "completed",
    "retry_count": $retry_count,
    "submitted_at": datetime.utcnow().isoformat() + "Z",
    "completed_at": datetime.utcnow().isoformat() + "Z",
    "generation_mode": "youmind_api"
}

if existing is not None:
    data["images"][existing] = image_data
else:
    data["images"].append(image_data)

with open(links_file, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
EOF
        return 0
    else
        log "❌ [YouMind API] 图片生成失败: $result"
        return 1
    fi
}

# 使用 chatgpt-image skill 提交图片生成请求 (OpenCLI 浏览器模式)
submit_image_request_opencli() {
    local chapter=$1
    local page=$2
    local prompt="$3"
    local retry_count=${4:-0}
    local result=""
    local combined_result=""
    local exit_code=0
    local link=""
    local submit_warning=""
    local opencli_repaired="false"
    local submit_log="$TASK_DIR/image_generation_page${page}_submit.log"
    local attempt

    log "📤 [OpenCLI] 提交: 第${chapter}章第${page}页 (尝试 $((retry_count + 1)))"

    : > "$submit_log"
    set +e
    result=$(python3 "$CHATGPT_IMAGE_SERVICE" submit --prompt "$prompt" --repair-retries 2 2>&1)
    exit_code=$?
    set -e
    echo "$result" >> "$submit_log"

    parsed=$(SERVICE_RESULT="$result" python3 << 'PYEOF'
import json
import os
import shlex

raw = os.environ["SERVICE_RESULT"]
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    data = {"link": "", "warning": "", "submit_exit_code": "", "submit_attempts": 1, "opencli_repaired": False, "error": "chatgpt-image service returned non-JSON output"}
else:
    pass

fields = {
    "link": data.get("link", ""),
    "submit_warning": data.get("warning", ""),
    "submit_exit_code": data.get("submit_exit_code", ""),
    "attempt": data.get("submit_attempts", 1),
    "opencli_repaired": "true" if data.get("opencli_repaired") else "false",
    "service_error": data.get("error", ""),
}
for name, value in fields.items():
    print(f"{name}={shlex.quote(str(value))}")
PYEOF
)
    eval "$parsed"
    combined_result="$result"
    if [ -z "$submit_exit_code" ]; then
        submit_exit_code="$exit_code"
    fi
    if [ -z "$attempt" ] || [ "$attempt" = "0" ]; then
        attempt=1
    fi

    if [ -z "$link" ]; then
        log "❌ [OpenCLI] 提交失败，未解析到 ChatGPT 链接；详见 $submit_log"
        if [ -n "$service_error" ]; then
            log "   错误: $service_error"
        fi
        return 1
    fi

    log "✅ [OpenCLI] 已提交: $link"
    if [ -n "$submit_warning" ]; then
        log "⚠️  [OpenCLI] $submit_warning"
    fi

    # 记录到 JSON
    CHAPTER="$chapter" \
PAGE="$page" \
PROMPT_TEXT="$prompt" \
LINK="$link" \
RETRY_COUNT="$retry_count" \
SUBMIT_EXIT_CODE="$submit_exit_code" \
SUBMIT_ATTEMPTS="$attempt" \
SUBMIT_LOG_NAME="$(basename "$submit_log")" \
SUBMIT_WARNING="$submit_warning" \
OPENCLI_REPAIRED="$opencli_repaired" \
SUBMIT_OUTPUT_TAIL="${combined_result: -2000}" \
IMAGE_LINKS_FILE="$IMAGE_LINKS_FILE" \
python3 << 'EOF'
import json
import os
from datetime import datetime

links_file = os.environ["IMAGE_LINKS_FILE"]
chapter = int(os.environ["CHAPTER"])
page = int(os.environ["PAGE"])

if os.path.exists(links_file):
    with open(links_file, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {"images": []}

# 检查是否已存在该图片的记录
existing = None
for i, img in enumerate(data["images"]):
    if int(img.get("chapter", 0)) == chapter and int(img.get("page", 0)) == page:
        existing = i
        break

image_data = {
    "chapter": chapter,
    "page": page,
    "filename": f"chapter{chapter}_page{page}.png",
    "link": os.environ["LINK"],
    "prompt": os.environ["PROMPT_TEXT"].strip(),
    "status": "pending",
    "retry_count": int(os.environ["RETRY_COUNT"]),
    "submitted_at": datetime.utcnow().isoformat() + "Z",
    "updated_at": datetime.utcnow().isoformat() + "Z",
    "generation_mode": "chatgpt_image_service_opencli",
    "submit_exit_code": int(os.environ["SUBMIT_EXIT_CODE"]),
    "submit_attempts": int(os.environ["SUBMIT_ATTEMPTS"]),
    "submit_log": os.environ["SUBMIT_LOG_NAME"],
    "submit_warning": os.environ["SUBMIT_WARNING"],
    "opencli_repaired": os.environ["OPENCLI_REPAIRED"] == "true",
    "submit_output_tail": os.environ["SUBMIT_OUTPUT_TAIL"],
}

if existing is not None:
    data["images"][existing] = image_data
else:
    data["images"].append(image_data)

data["images"].sort(key=lambda img: (int(img.get("chapter", 0)), int(img.get("page", 0))))

with open(links_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
EOF

    return 0
}

# 统一的提交函数，根据模式选择实现
submit_image_request() {
    local chapter=$1
    local page=$2
    local prompt="$3"
    local retry_count=${4:-0}

    log "📤 提交: 第${chapter}章第${page}页 (尝试 $((retry_count + 1)))"

    # 质量检查
    if ! check_prompt_quality "$prompt"; then
        log "⚠️  提示词质量警告，自动优化..."
        prompt=$(optimize_prompt "$prompt")
        log "✓ 优化后: ${prompt:0:80}..."
    fi

    # 根据模式选择提交方式
    if [ "$IMAGE_GENERATION_MODE" = "youmind" ]; then
        submit_image_request_youmind $chapter $page "$prompt" $retry_count
    else
        submit_image_request_opencli $chapter $page "$prompt" $retry_count
    fi
}

# 检查单个图片状态
check_image_status() {
    local link="$1"
    local status
    local result

    set +e
    result=$(python3 "$CHATGPT_IMAGE_SERVICE" status --link "$link" --repair-retries 1 2>&1)
    set -e
    status=$(SERVICE_RESULT="$result" python3 << 'PYEOF'
import json
import os

try:
    data = json.loads(os.environ["SERVICE_RESULT"])
    print(data.get("status") or "PENDING")
except json.JSONDecodeError:
    print("PENDING")
PYEOF
)
    echo "${status:-PENDING}"
}

# 下载图片
download_image() {
    local link="$1"
    local filename="$2"
    local result
    local ok

    set +e
    result=$(python3 "$CHATGPT_IMAGE_SERVICE" download \
        --link "$link" \
        --output "$IMAGES_DIR/$filename" \
        --repair-retries 1 2>&1)
    set -e
    ok=$(SERVICE_RESULT="$result" python3 << 'PYEOF'
import json
import os

try:
    data = json.loads(os.environ["SERVICE_RESULT"])
    print("1" if data.get("ok") and data.get("status") == "completed" else "0")
except json.JSONDecodeError:
    print("0")
PYEOF
)
    [ "$ok" = "1" ]
}

# 主流程
main() {
    log "🎨 智能图片生成管理器启动"
    log "📁 任务目录: $TASK_DIR"
    log "🔧 生成模式: $IMAGE_GENERATION_MODE"
    log ""

    # 先同步已有文件，避免重复提交已经生成完成的图片
    sync_task_status

    # OpenCLI 批量提交前先做本地结构审查，避免把旧 prompt 直接送去生成
    audit_storyboard_prompts || return 1

    # 第一阶段：提交缺失请求
    log "━━━ 第一阶段：提交图片生成请求 ━━━"

    submitted_count=0
    skipped_count=0
    consecutive_submit_failures=0

    for storyboard_file in "$STORYBOARDS_DIR"/*.json; do
        if [ ! -f "$storyboard_file" ]; then
            continue
        fi

        filename=$(basename "$storyboard_file")
        chapter=$(echo "$filename" | grep -o 'chapter[0-9]*' | grep -o '[0-9]*')
        page=$(echo "$filename" | grep -o 'page[0-9]*' | grep -o '[0-9]*')

        if ! should_submit_request "$chapter" "$page"; then
            log "⏭️  第${chapter}章第${page}页：已有图片或待检查链接，跳过提交"
            ((skipped_count+=1))
            consecutive_submit_failures=0
            continue
        fi

        # 提取提示词（优先使用 prompts/ 中的人工优化版本）
        prompt=$(get_prompt_for_page "$storyboard_file" "$chapter" "$page")

        if [ -z "$prompt" ]; then
            log "⚠️  第${chapter}章第${page}页：未找到提示词"
            continue
        fi

        if submit_image_request $chapter $page "$prompt"; then
            ((submitted_count+=1))
            consecutive_submit_failures=0
        else
            ((consecutive_submit_failures+=1))
            log "❌ 第${chapter}章第${page}页：提交失败（连续失败 $consecutive_submit_failures/3）"
            if [ $consecutive_submit_failures -ge 3 ]; then
                log "🛑 OpenCLI 连续 3 次提交失败，停止批量提交。先检查 image_generation.log 和 image_generation_page*_submit.log，避免刷出整批失败。"
                break
            fi
        fi
        sleep 2
    done

    log ""
    log "✅ 提交阶段完成：新提交 $submitted_count 个，跳过 $skipped_count 个"
    log ""
    sync_task_status

    # YouMind API 模式：同步生成，无需监控循环
    if [ "$IMAGE_GENERATION_MODE" = "youmind" ]; then
        log "━━━ YouMind API 模式：同步生成完成 ━━━"
        log ""
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log "📊 最终报告"
        log "   📁 保存位置: $IMAGES_DIR"
        log "   📋 详细记录: $IMAGE_LINKS_FILE"
        log "   📝 日志文件: $LOG_FILE"
        sync_task_status
        return 0
    fi

    # OpenCLI 模式：进入监控循环
    log "━━━ 第二阶段：自动监控和下载 ━━━"
    log "⏰ 每 $((CHECK_INTERVAL / 60)) 分钟检查一次"
    log ""

    start_time=$(date +%s)
    check_round=1

    while true; do
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))

        if [ $elapsed -gt $MAX_WAIT_TIME ]; then
            log "⏰ 已达到最大等待时间 ($((MAX_WAIT_TIME / 60)) 分钟)"
            break
        fi

        log "🔍 第 $check_round 轮检查 (已等待 $((elapsed / 60)) 分钟)"

        # 读取所有待处理的图片
        pending_count=0
        completed_count=0
        failed_count=0

        if [ ! -f "$IMAGE_LINKS_FILE" ]; then
            log "⚠️  未找到 image_links.json，无法进入监控"
            break
        fi

        total=$(cat "$IMAGE_LINKS_FILE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('images', [])))")

        if [ "$total" -eq 0 ]; then
            log "⚠️  没有可监控的图片记录"
            break
        fi

        for i in $(seq 0 $((total - 1))); do
            info=$(cat "$IMAGE_LINKS_FILE" | python3 -c "import sys, json; data=json.load(sys.stdin); img=data['images'][$i]; print(f\"{img['chapter']}|{img['page']}|{img['link']}|{img['filename']}|{img['status']}|{img.get('retry_count', 0)}\")")

            IFS='|' read -r chapter page link filename status retry_count <<< "$info"

            if image_file_exists "$filename"; then
                if [ "$status" != "completed" ]; then
                    log "   第${chapter}章第${page}页: ✅ 本地图片已存在，更新状态"
                    sync_task_status
                fi
                ((completed_count+=1))
                continue
            fi

            if [ "$status" = "completed" ]; then
                log "   第${chapter}章第${page}页: ⚠️  状态为完成但本地文件缺失，改回待检查"
                sync_task_status
                ((pending_count+=1))
                continue
            fi

            if [ -z "$link" ] || [ "$link" = "None" ]; then
                log "   第${chapter}章第${page}页: ⏳ 无生成链接，等待补交"
                ((pending_count+=1))
                continue
            fi

            # 检查状态
            check_status=$(check_image_status "$link" $chapter $page)

            if echo "$check_status" | grep -q "^READY:"; then
                log "   第${chapter}章第${page}页: ✅ 已生成，开始下载..."

                if download_image "$link" "$filename"; then
                    file_size=$(ls -lh "$IMAGES_DIR/$filename" | awk '{print $5}')
                    log "   ✓ 下载完成 ($file_size)"

                    # 更新状态为completed
                    python3 << EOF
import json
with open("$IMAGE_LINKS_FILE", "r") as f:
    data = json.load(f)
data["images"][$i]["status"] = "completed"
data["images"][$i]["completed_at"] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
data["images"][$i]["file_size"] = "$file_size"
with open("$IMAGE_LINKS_FILE", "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
EOF
                    sync_task_status
                    ((completed_count+=1))
                else
                    log "   ❌ 下载失败"
                    ((pending_count+=1))
                fi

            elif echo "$check_status" | grep -q "ERROR"; then
                log "   第${chapter}章第${page}页: ❌ 生成失败"

                # 检查是否可以重试
                if [ $retry_count -lt $MAX_RETRIES ]; then
                    log "   🔄 准备重试 ($((retry_count + 1))/$MAX_RETRIES)"

                    # 读取原始提示词并优化
                    prompt=$(cat "$IMAGE_LINKS_FILE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['images'][$i]['prompt'])")
                    optimized_prompt=$(optimize_prompt "$prompt")

                    # 重新提交
                    if submit_image_request $chapter $page "$optimized_prompt" $((retry_count + 1)); then
                        # 更新状态
                        python3 << EOF
import json
with open("$IMAGE_LINKS_FILE", "r") as f:
    data = json.load(f)
data["images"][$i]["status"] = "retrying"
with open("$IMAGE_LINKS_FILE", "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
EOF
                    else
                        log "   ❌ 重试提交失败，保留当前记录等待后续处理"
                        ((pending_count+=1))
                    fi
                else
                    log "   ⚠️  已达到最大重试次数"
                    python3 << EOF
import json
with open("$IMAGE_LINKS_FILE", "r", encoding="utf-8") as f:
    data = json.load(f)
data["images"][$i]["status"] = "failed"
data["images"][$i]["failed_at"] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
with open("$IMAGE_LINKS_FILE", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
EOF
                    sync_task_status
                    ((failed_count+=1))
                fi

            else
                log "   第${chapter}章第${page}页: ⏳ 生成中..."
                ((pending_count+=1))
            fi
        done

        log ""
        log "📊 当前状态: ✅ $completed_count | ⏳ $pending_count | ❌ $failed_count"
        log ""
        sync_task_status

        # 如果全部完成，退出
        if [ $pending_count -eq 0 ] && [ $failed_count -eq 0 ]; then
            log "🎉 所有图片生成完成！"
            break
        fi

        # 等待下一轮检查
        if [ $pending_count -gt 0 ]; then
            log "⏰ 等待 $((CHECK_INTERVAL / 60)) 分钟后进行下一轮检查..."
            sleep $CHECK_INTERVAL
            ((check_round+=1))
        else
            break
        fi
    done

    # 最终报告
    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "📊 最终报告"
    log "   ✅ 成功: $completed_count 张"
    log "   ❌ 失败: $failed_count 张"
    log "   📁 保存位置: $IMAGES_DIR"
    log "   📋 详细记录: $IMAGE_LINKS_FILE"
    log "   📝 日志文件: $LOG_FILE"
    sync_task_status
    audit_generated_images

    if [ $failed_count -gt 0 ]; then
        log ""
        log "⚠️  失败的图片需要手动处理："
        cat "$IMAGE_LINKS_FILE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for img in data['images']:
    if img['status'] == 'failed' or img.get('retry_count', 0) >= $MAX_RETRIES:
        print(f\"   第{img['chapter']}章第{img['page']}页: {img['link']}\")
"
    fi
}

# 运行主流程
main
