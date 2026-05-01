#!/bin/bash

# 检查并下载已提交的ChatGPT图片生成请求
# 用法: ./check_images.sh <chat_link> <output_dir> <filename>

set +e

CHAT_LINK="$1"
OUTPUT_DIR="$2"
FILENAME="${3:-chatgpt_image.png}"

if [ -z "$CHAT_LINK" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "用法: $0 <chat_link> <output_dir> [filename]"
    exit 1
fi

# 确保输出目录存在
mkdir -p "$OUTPUT_DIR"

echo "🔍 检查图片生成状态..."
echo "🔗 链接: $CHAT_LINK"
echo "📁 输出目录: $OUTPUT_DIR"
echo ""

# 打开页面
echo "📖 打开 ChatGPT 页面..."
opencli browser open "$CHAT_LINK" 2>&1 > /dev/null

# 等待页面加载
sleep 5

# 检查图片是否已完整加载
img_status=$(opencli browser eval "
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

echo "图片状态: $img_status"

# 如果图片已就绪，下载
if echo "$img_status" | grep -q "^ready:"; then
    echo "✅ 图片已生成，开始下载..."

    # 使用 canvas 方式在浏览器中下载图片
    opencli browser eval "
(async () => {
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
" 2>&1 > /dev/null

    # 等待下载完成
    sleep 3

    # 查找最新下载的图片
    latest_download=$(ls -t ~/Downloads/*.png 2>/dev/null | head -1)

    if [ -n "$latest_download" ]; then
        mv "$latest_download" "$OUTPUT_DIR/$FILENAME"
        file_size=$(ls -lh "$OUTPUT_DIR/$FILENAME" | awk '{print $5}')
        echo "✓ 下载完成 ($file_size)"
        echo "📁 保存位置: $OUTPUT_DIR/$FILENAME"
        exit 0
    else
        echo "❌ 下载失败，未找到下载的文件"
        exit 1
    fi
else
    echo "⚠️  图片未就绪"
    if echo "$img_status" | grep -q "loading"; then
        echo "   状态: 正在加载中..."
    elif echo "$img_status" | grep -q "invalid"; then
        echo "   状态: 图片尺寸无效"
    elif echo "$img_status" | grep -q "no_image"; then
        echo "   状态: 未找到生成的图片"
    fi
    exit 2
fi
