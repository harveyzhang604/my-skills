#!/usr/bin/env python3
"""从ChatGPT对话链接批量下载已生成的图片"""
import json
import subprocess
import os
import time
import sys
import shutil
from pathlib import Path

from task_path_guard import require_task_dir

TASK_DIR = str(require_task_dir(sys.argv[1]))
IMAGES_DIR = str((Path(sys.argv[2]).expanduser().resolve(strict=False)))
if not IMAGES_DIR.startswith(str(Path(TASK_DIR).resolve(strict=False)) + "/"):
    raise SystemExit(f"错误：images_dir must be inside task_dir: {TASK_DIR}")

# JS代码：查找并下载ChatGPT页面上的生成图片
JS_FIND_AND_DOWNLOAD = """
(async () => {
    const selectors = [
        'img[alt="Generated image"]',
        'img[alt="generated image"]',
        '[class*="imagegen"] img',
        'img[src*="estuary/content"]',
    ];
    let imgEl = null;
    for (const sel of selectors) {
        imgEl = document.querySelector(sel);
        if (imgEl && imgEl.src && imgEl.src.includes('estuary')) break;
        imgEl = null;
    }
    if (!imgEl) {
        const allImgs = document.querySelectorAll('img');
        for (const img of allImgs) {
            if (img.src && img.src.includes('estuary') && img.naturalWidth > 100) {
                imgEl = img;
                break;
            }
        }
    }
    if (!imgEl) return 'no-image';
    const resp = await fetch(imgEl.src);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'image.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return 'ok';
})()
"""

with open(f"{TASK_DIR}/image_links.json", 'r') as f:
    data = json.load(f)

images = [i for i in data.get('images', []) if i.get('chapter') in [1, 2, 3, 4]]

downloaded = 0
already_exists = 0
failed = 0

print(f"前4章共 {len(images)} 张，开始逐个检查下载...")
print("")

for idx, img in enumerate(images, 1):
    chapter = img.get('chapter', 0)
    page = img.get('page', 0)
    link = img.get('link', '')
    filename = img.get('filename', f'chapter{chapter}_page{page}.png')
    filepath = os.path.join(IMAGES_DIR, filename)

    if os.path.exists(filepath):
        already_exists += 1
        continue

    if not link:
        continue

    # 打开ChatGPT对话页面
    try:
        subprocess.run(
            ['opencli', 'browser', 'open', link],
            capture_output=True, text=True, timeout=20
        )
    except:
        print(f"[{idx:2d}/96] 第{chapter}章第{page:2d}页: ⏰ 打开超时")
        failed += 1
        continue

    # 等待页面充分加载
    time.sleep(6)

    try:
        r2 = subprocess.run(
            ['opencli', 'browser', 'eval', JS_FIND_AND_DOWNLOAD],
            capture_output=True, text=True, timeout=20
        )
        result = r2.stdout.strip().strip('"').strip("'")

        if 'ok' in result:
            time.sleep(3)
            downloads_dir = os.path.expanduser("~/Downloads")
            png_files = [os.path.join(downloads_dir, f) for f in os.listdir(downloads_dir)
                         if f.endswith('.png')]

            if png_files:
                latest = max(png_files, key=os.path.getmtime)
                size = os.path.getsize(latest)

                if size > 500000:
                    shutil.move(latest, filepath)
                    size_mb = size / 1024 / 1024
                    print(f"[{idx:2d}/96] 第{chapter}章第{page:2d}页: ✅ ({size_mb:.1f}MB)")
                    downloaded += 1
                else:
                    if os.path.exists(latest):
                        os.remove(latest)
                    print(f"[{idx:2d}/96] 第{chapter}章第{page:2d}页: ❌ 文件太小")
                    failed += 1
            else:
                print(f"[{idx:2d}/96] 第{chapter}章第{page:2d}页: ❌ 未找到下载文件")
                failed += 1
        elif 'no-image' in result:
            print(f"[{idx:2d}/96] 第{chapter}章第{page:2d}页: ⏳ 未生成")
            failed += 1
        else:
            print(f"[{idx:2d}/96] 第{chapter}章第{page:2d}页: ❌ {result[:50]}")
            failed += 1
    except Exception as e:
        print(f"[{idx:2d}/96] 第{chapter}章第{page:2d}页: ⏰ 超时")
        failed += 1

print("")
print("=" * 50)
print(f"✅ 本次新下载: {downloaded} 张")
print(f"✓ 已存在: {already_exists} 张")
print(f"📊 总计完成: {downloaded + already_exists}/96 张")
