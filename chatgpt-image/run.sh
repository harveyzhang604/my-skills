#!/bin/bash

# ChatGPT Image Generator
# 使用 OpenCLI 调用 ChatGPT Image 2 生成图片

set +e

# 默认参数
PROMPT="${1:-东方美女抖音带货视频}"
OUTPUT_DIR="${2:-$HOME/Pictures/chatgpt}"

# 确保输出目录存在
mkdir -p "$OUTPUT_DIR"

echo "🎨 开始生成图片..."
echo "📝 提示词: $PROMPT"
echo "📁 输出目录: $OUTPUT_DIR"
echo ""

# ========== 第一步：提交生成请求 ==========
echo "📤 提交图片生成请求到 ChatGPT..."
initial_result=$(opencli chatgpt image "$PROMPT" --verbose 2>&1)

# 提取对话链接
chat_link=$(echo "$initial_result" | grep "link:" | sed 's/.*link: 🔗 //' | head -1)

if [ -z "$chat_link" ]; then
    echo "❌ 错误：无法获取 ChatGPT 链接"
    exit 1
fi

echo ""
echo "✅ 请求已提交！"
echo "🔗 ChatGPT 对话链接: $chat_link"
echo ""
echo "⏰ 开始定时检查并下载图片..."
echo ""

# 等待时间配置（秒）
WAIT_TIMES=(60 60 60 60 60 120 180)
WAIT_LABELS=("1分钟" "1分钟" "1分钟" "1分钟" "1分钟" "2分钟" "3分钟")

# ========== 第二步：循环检查并下载 ==========
for i in {0..6}; do
    wait_seconds=${WAIT_TIMES[$i]}
    wait_label=${WAIT_LABELS[$i]}
    attempt=$((i + 1))

    echo "⏳ 第 $attempt 次检查（等待 $wait_label）..."
    sleep "$wait_seconds"

    echo "🔍 打开 ChatGPT 页面检查图片..."

    # 打开页面
    page_result=$(opencli browser open "$chat_link" 2>&1)

    # 等待页面加载
    sleep 5

    # 截图保存当前状态
    screenshot_path="$OUTPUT_DIR/check_${attempt}_$(date +%Y%m%d_%H%M%S).png"
    opencli browser screenshot "$screenshot_path" 2>&1 > /dev/null

    # 先检查图片是否已完整加载（优先检查）
    img_ready=$(opencli browser eval "
(() => {
  // 查找生成的图片
  let img = document.querySelector('img[src*=\"chatgpt.com/backend-api/\"]');
  if (!img) img = document.querySelector('img[alt=\"Generated image\"]');

  if (!img) return 'no_image';

  // 检查图片是否已加载完成
  if (!img.complete) return 'loading';
  if (img.naturalWidth === 0 || img.naturalHeight === 0) return 'invalid';

  return 'ready:' + img.naturalWidth + 'x' + img.naturalHeight;
})()
" 2>&1)

    echo "   图片状态: $img_ready"

    # 如果图片已就绪，直接下载，不再检查页面文字
    if echo "$img_ready" | grep -q "^ready:"; then
        echo "✅ 发现生成的图片，开始下载..."

        # 使用 canvas 方式在浏览器中下载图片
        download_result=$(opencli browser eval "
(async () => {
  // 优先通过 src URL 特征查找图片
  let img = document.querySelector('img[src*=\"chatgpt.com/backend-api/\"]');
  if (!img) img = document.querySelector('img[alt=\"Generated image\"]');
  if (!img) return 'No image found';

  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  const dataUrl = canvas.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = 'chatgpt_generated_image.png';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  return 'Downloaded';
})()
" 2>&1)

        # 等待下载完成
        sleep 3

        # 查找最新下载的图片
        latest_download=$(ls -t ~/Downloads/*.png 2>/dev/null | head -1)

        if [ -n "$latest_download" ]; then
            filename="chatgpt_image_$(date +%Y%m%d_%H%M%S).png"
            mv "$latest_download" "$OUTPUT_DIR/$filename"

            file_size=$(ls -lh "$OUTPUT_DIR/$filename" | awk '{print $5}')
            echo "   ✓ 完成 ($file_size)"
            echo ""
            echo "🎉 成功下载图片！"
            echo "📁 保存位置: $OUTPUT_DIR/$filename"
            echo "🔗 ChatGPT 对话链接: $chat_link"
            exit 0
        else
            echo "   ⚠️  下载失败，未找到下载的文件"
        fi
    else
        echo "⚠️  图片未就绪或未找到"
        if echo "$img_ready" | grep -q "loading"; then
            echo "   图片正在加载中..."
        elif echo "$img_ready" | grep -q "invalid"; then
            echo "   图片尺寸无效..."
        elif echo "$img_ready" | grep -q "no_image"; then
            echo "   未找到生成的图片..."
        fi
    fi

    echo "   💡 已保存截图: $screenshot_path"
    echo ""
done

# ========== 第三步：所有检查都未完成 ==========
echo ""
echo "⚠️  经过 7 次检查（共约 10 分钟），未能自动下载图片"
echo ""
echo "📸 已保存 7 张截图到: $OUTPUT_DIR"
echo "   你可以查看截图了解生成进度"
echo ""
echo "📋 请手动操作："
echo "   1. 访问 ChatGPT 链接: $chat_link"
echo "   2. 查看图片是否已生成"
echo "   3. 右键保存图片到: $OUTPUT_DIR"
echo ""

exit 1
