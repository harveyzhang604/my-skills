# Gemini 图片生成备选方案

## 功能说明

当使用 OpenCLI 模式（ChatGPT Image）生成图片时，如果遇到以下限额错误：
- "Image generation limit reached"
- "You've reached your limit"
- "Limit has been reached"
- "达到限制"
- "已达到限额"

系统会**自动切换**到 Gemini Image 生成图片，无需手动干预。

## 工作原理

### 1. 提交阶段检测

在 `submit_image_request_opencli()` 函数中：
1. 首先尝试使用 ChatGPT Image 提交请求
2. 检查返回结果中是否包含限额错误关键词
3. 如果检测到限额错误，自动调用 `submit_image_request_gemini()`
4. Gemini 生成成功后，记录到 `image_links.json`，标记为 `generation_mode: "gemini_fallback"`

### 2. 监控循环中的重试

监控循环检测到图片生成失败（ERROR 状态）时：
1. 调用 `submit_image_request()` 重新提交
2. `submit_image_request()` 会调用 `submit_image_request_opencli()`
3. 如果再次遇到限额错误，自动切换到 Gemini

## Gemini 生成流程

`submit_image_request_gemini()` 函数的工作流程：

1. **调用 OpenCLI Gemini**：
   ```bash
   opencli gemini image "$prompt" --op "$IMAGES_DIR"
   ```

2. **查找生成的图片**：
   - Gemini 默认保存到 `~/Pictures/gemini/`
   - 通过时间戳查找最新生成的图片
   - 移动到任务的 `images/` 目录

3. **记录到 JSON**：
   ```json
   {
     "chapter": 1,
     "page": 1,
     "filename": "chapter1_page1.png",
     "link": "gemini://generated",
     "status": "completed",
     "generation_mode": "gemini_fallback",
     "fallback_reason": "chatgpt_limit_reached"
   }
   ```

## 使用示例

### 正常使用（无需额外配置）

```bash
# 运行智能图片管理器
/Users/zhanghua/.claude/skills/cd-generator/scripts/smart_image_manager.sh "$TASK_DIR"
```

如果遇到 ChatGPT 限额，会看到类似日志：

```
📤 [OpenCLI] 提交: 第1章第5页 (尝试 1)
❌ [OpenCLI] 提交失败，未解析到 ChatGPT 链接；详见 image_generation_page5_submit.log
   错误: Image generation limit reached
⚠️  检测到 ChatGPT Image 限额错误，切换到 Gemini Image...
📤 [Gemini] 提交: 第1章第5页 (备选方案)
✅ [Gemini] 图片生成成功: chapter1_page5.png
```

## 查看生成模式

检查 `image_links.json` 中的 `generation_mode` 字段：

```bash
cat "$TASK_DIR/image_links.json" | jq '.images[] | {chapter, page, generation_mode, fallback_reason}'
```

输出示例：
```json
{
  "chapter": 1,
  "page": 1,
  "generation_mode": "chatgpt_image_service_opencli",
  "fallback_reason": null
}
{
  "chapter": 1,
  "page": 5,
  "generation_mode": "gemini_fallback",
  "fallback_reason": "chatgpt_limit_reached"
}
```

## 注意事项

### 1. Gemini 图片特点

- **同步生成**：Gemini 直接返回图片，无需等待和监控
- **无链接**：记录为 `"link": "gemini://generated"`，不是真实的对话链接
- **立即完成**：状态直接标记为 `"completed"`

### 2. 提示词兼容性

- Gemini 只支持纯文字 prompt，不支持上传参考图
- 提示词会自动传递给 Gemini，无需修改
- 如果提示词过于复杂，Gemini 可能生成效果不如 ChatGPT

### 3. 图片质量

- Gemini 和 ChatGPT 的生成风格可能不同
- 建议在批量生成前先测试单张图片
- 如果 Gemini 效果不理想，可以等 ChatGPT 限额恢复后重新生成

## 手动使用 Gemini

如果想直接使用 Gemini 生成单张图片：

```bash
# 方法1：使用 OpenCLI 命令
opencli gemini image "16:9 widescreen manga scene..." --op ~/Downloads

# 方法2：调用 Gemini 函数（需要在脚本中）
submit_image_request_gemini 1 1 "your prompt here" 0
```

## 故障排查

### 问题1：Gemini 生成失败

**症状**：
```
❌ [Gemini] 图片生成失败
```

**可能原因**：
1. OpenCLI Gemini 未配置或未登录
2. Gemini 服务不可用
3. 提示词不符合 Gemini 要求

**解决方法**：
```bash
# 测试 Gemini 是否可用
opencli gemini image "test image" --op ~/Downloads

# 检查 OpenCLI 配置
opencli doctor
```

### 问题2：找不到生成的图片

**症状**：
```
❌ [Gemini] 图片生成失败
```

**可能原因**：
- Gemini 保存路径不是默认的 `~/Pictures/gemini/`
- 图片生成时间戳判断失败

**解决方法**：
```bash
# 检查 Gemini 默认保存路径
ls -lt ~/Pictures/gemini/ | head -5

# 手动移动图片
mv ~/Pictures/gemini/latest.png "$TASK_DIR/images/chapter1_page1.png"
```

### 问题3：ChatGPT 和 Gemini 都失败

**症状**：
```
❌ Gemini 备选方案也失败了
```

**解决方法**：
1. 检查网络连接
2. 等待一段时间后重试
3. 考虑使用 YouMind API 模式（需要配置 API Key）

## 与 YouMind 模式的区别

| 特性 | OpenCLI + Gemini 备选 | YouMind API 模式 |
|------|---------------------|-----------------|
| 主要提供商 | ChatGPT Image | YouMind API |
| 备选方案 | Gemini Image | 无 |
| 需要配置 | 无（使用 OpenCLI） | 需要 API Key |
| 触发条件 | ChatGPT 限额时自动 | 手动切换模式 |
| 生成方式 | 异步（ChatGPT）<br>同步（Gemini） | 同步 |

## 版本历史

- **v2.16.0** (2026-05-03): 添加 Gemini 作为 ChatGPT 限额时的自动备选方案
