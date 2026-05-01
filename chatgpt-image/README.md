# ChatGPT Image Generator

使用 OpenCLI 调用 ChatGPT Image 2 生成图片，支持循环检查机制和自动下载保存。

## 使用方法

```bash
# 基本使用 - 使用默认提示词生成图片
/skill chatgpt-image

# 使用自定义提示词
/skill chatgpt-image "你的中文提示词"

# 指定输出目录
/skill chatgpt-image "提示词" --output ~/Desktop
```

## 功能特性

- 使用 OpenCLI 调用 ChatGPT Image 2 生成图片
- 智能循环检查机制（5分钟、7分钟、10分钟三次检查）
- 自动下载生成的图片到指定位置
- 支持自定义提示词（原样传递，不做优化）
- 支持自定义输出目录

## 工作原理

1. 调用 `opencli chatgpt image` 命令提交生成请求
2. 进入等待循环，每隔一段时间检查生成状态
3. 图片生成完成后自动下载到本地
4. 返回生成的图片文件路径

## 注意事项

- 需要提前登录 ChatGPT 网页版（chatgpt.com）
- 图片生成时间较长，请耐心等待
- 如果三次检查都未完成，会返回 ChatGPT 链接供手动查看
