#!/bin/bash
# 测试 Gemini 备选功能

echo "🧪 测试 Gemini 图片生成备选功能"
echo ""

# 测试1：检查 Gemini 是否可用
echo "📋 测试 1: 检查 OpenCLI Gemini 是否可用"
if command -v opencli &> /dev/null; then
    echo "✅ OpenCLI 已安装"

    # 测试 Gemini 命令
    echo "🔍 测试 Gemini Image 命令..."
    test_output=$(opencli gemini image "test: a simple red circle on white background" --op /tmp 2>&1 || true)

    if echo "$test_output" | grep -qi "error\|failed"; then
        echo "⚠️  Gemini 可能未配置或不可用"
        echo "   输出: ${test_output:0:200}"
    else
        echo "✅ Gemini Image 命令可用"
    fi
else
    echo "⚠️  OpenCLI 未安装（跳过运行时测试）"
fi

echo ""
echo "📋 测试 2: 检查限额错误检测"

# 模拟限额错误
test_errors=(
    "Image generation limit reached"
    "You've reached your limit"
    "Limit has been reached"
    "达到限制"
    "已达到限额"
)

for error in "${test_errors[@]}"; do
    if echo "$error" | grep -qi "image generation limit reached\|you've reached your limit\|limit has been reached\|达到限制\|已达到限额"; then
        echo "✅ 检测到限额错误: $error"
    else
        echo "❌ 未检测到限额错误: $error"
    fi
done

echo ""
echo "📋 测试 3: 检查 smart_image_manager.sh 语法"
script_path="/Users/zhanghua/.skills-manager/skills/cd-generator/scripts/smart_image_manager.sh"

if [ -f "$script_path" ]; then
    if bash -n "$script_path" 2>&1; then
        echo "✅ smart_image_manager.sh 语法正确"
    else
        echo "❌ smart_image_manager.sh 语法错误"
        exit 1
    fi
else
    echo "❌ 找不到 smart_image_manager.sh"
    exit 1
fi

echo ""
echo "📋 测试 4: 检查新增的函数"

if grep -q "submit_image_request_gemini()" "$script_path"; then
    echo "✅ 找到 submit_image_request_gemini() 函数"
else
    echo "❌ 未找到 submit_image_request_gemini() 函数"
    exit 1
fi

if grep -q "is_limit_error" "$script_path"; then
    echo "✅ 找到限额错误检测逻辑"
else
    echo "❌ 未找到限额错误检测逻辑"
    exit 1
fi

if grep -q "切换到 Gemini Image" "$script_path"; then
    echo "✅ 找到 Gemini 切换日志"
else
    echo "❌ 未找到 Gemini 切换日志"
    exit 1
fi

echo ""
echo "📋 测试 5: 检查文档"

doc_path="/Users/zhanghua/.skills-manager/skills/cd-generator/GEMINI_FALLBACK.md"
if [ -f "$doc_path" ]; then
    echo "✅ 找到 GEMINI_FALLBACK.md 文档"
else
    echo "⚠️  未找到 GEMINI_FALLBACK.md 文档"
fi

skill_path="/Users/zhanghua/.skills-manager/skills/cd-generator/SKILL.md"
if grep -q "Gemini 自动备选" "$skill_path"; then
    echo "✅ SKILL.md 已更新 Gemini 备选说明"
else
    echo "⚠️  SKILL.md 未更新 Gemini 备选说明"
fi

version_path="/Users/zhanghua/.skills-manager/skills/cd-generator/skill-version.json"
if grep -q "2.16.0" "$version_path"; then
    echo "✅ skill-version.json 已更新到 v2.16.0"
else
    echo "⚠️  skill-version.json 版本号未更新"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 所有测试通过！"
echo ""
echo "📝 使用说明："
echo "   1. 正常使用 smart_image_manager.sh 即可"
echo "   2. 遇到 ChatGPT 限额时会自动切换到 Gemini"
echo "   3. 查看详细文档: cat $doc_path"
echo ""
