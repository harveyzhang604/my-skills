---
name: image-compressor
description: Compress PNG and JPEG images while maintaining visual quality. Use this skill when the user needs to reduce image file size from AI-generated images (ChatGPT, Gemini, etc.) from 2-3MB down to a few hundred KB. Supports PNG and JPEG formats, uses intelligent quality optimization to preserve clarity while dramatically reducing file size.
---

## Image Compression Skill

This skill compresses PNG and JPEG images using intelligent algorithms that maintain visual quality while significantly reducing file size.

### When to Use

- AI-generated images (ChatGPT Image, Gemini, etc.) that are 2-3MB+ and need to be reduced to a few hundred KB
- PNG images that need optimization for web use
- JPEG images that need quality/size optimization
- Batch compression of multiple images
- Converting between PNG and JPEG formats while optimizing

### Supported Formats

- **PNG**: Lossless compression with optional palette reduction
- **JPEG**: Lossy compression with configurable quality

### Usage

#### Single Image Compression

```bash
# Compress a PNG image
python /Users/zhanghua/.claude/skills/image-compressor/scripts/compress.py input.png output.png

# Compress a JPEG image with specific quality
python /Users/zhanghua/.claude/skills/image-compressor/scripts/compress.py input.jpg output.jpg --quality 85

# Compress to a target file size (approximate)
python /Users/zhanghua/.claude/skills/image-compressor/scripts/compress.py input.png output.png --target-size 500kb
```

#### Batch Compression

```bash
# Compress all images in a directory
python /Users/zhanghua/.claude/skills/image-compressor/scripts/compress.py --batch ./images/ --output ./compressed/

# Compress with specific options
python /Users/zhanghua/.claude/skills/image-compressor/scripts/compress.py --batch ./images/ --output ./compressed/ --quality 85 --format jpeg
```

### Options

- `--quality`: JPEG quality (1-100, default: 85). Higher = better quality, larger file
- `--target-size`: Target file size (e.g., "500kb", "1mb"). Script will auto-adjust quality to meet target
- `--format`: Output format (png, jpeg). Default: same as input
- `--png-optimization`: PNG optimization level (1-3, default: 2). Higher = smaller file, slower
- `--preserve-metadata`: Keep image metadata (EXIF, etc.)
- `--backup`: Create backup of original files

### How It Works

1. **PNG Compression**: Uses pngquant for palette reduction and oxipng for additional optimization
2. **JPEG Compression**: Uses mozjpeg or Pillow with optimized encoding tables
3. **Smart Quality Selection**: When target size is specified, automatically finds the best quality setting
4. **Format Conversion**: Can convert PNG ↔ JPEG with appropriate quality adjustments

### Quality Guidelines

- **90-95**: Near-lossless, minimal artifacts, larger files
- **85**: Good balance of quality and size (recommended default)
- **75-80**: Acceptable quality, significantly smaller files
- **60-70**: Noticeable compression artifacts, smallest usable files

### Expected Results

- 2-3MB PNG → 300-800KB (70-85% reduction)
- 2-3MB JPEG → 200-600KB (80-90% reduction)
- Visual quality remains perceptually identical at default settings
