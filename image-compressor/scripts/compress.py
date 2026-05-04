#!/usr/bin/env python3
"""
Image Compression Script
Compress PNG and JPEG images while maintaining visual quality.
"""

import argparse
import os
import shutil
import sys
import platform
from pathlib import Path
from PIL import Image
from PIL.JpegImagePlugin import JpegImageFile
from PIL.PngImagePlugin import PngImageFile
import io
import tempfile


def get_file_size(path):
    """Get file size in bytes."""
    return os.path.getsize(path)


def format_size(size_bytes):
    """Format bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f}MB"


def parse_target_size(size_str):
    """Parse target size string like '500kb', '1mb', '2.5mb' to bytes."""
    size_str = size_str.lower().strip()
    if size_str.endswith('kb'):
        return int(float(size_str[:-2]) * 1024)
    elif size_str.endswith('mb'):
        return int(float(size_str[:-2]) * 1024 * 1024)
    elif size_str.endswith('b'):
        return int(size_str[:-1])
    else:
        return int(size_str)


def calculate_psnr(img1, img2):
    """Calculate PSNR between two images. Higher is better."""
    import numpy as np
    import math

    if img1.mode != img2.mode:
        img2 = img2.convert(img1.mode)
    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.LANCZOS)

    arr1 = np.array(img1).astype(np.float64)
    arr2 = np.array(img2).astype(np.float64)

    mse = np.mean((arr1 - arr2) ** 2)
    if mse == 0:
        return float('inf')

    max_pixel = 255.0
    psnr = 20 * math.log10(max_pixel / math.sqrt(mse))
    return psnr


def calculate_ssim(img1, img2):
    """Calculate SSIM between two images. 1.0 is perfect match."""
    import numpy as np

    if img1.mode != 'RGB':
        img1 = img1.convert('RGB')
    if img2.mode != 'RGB':
        img2 = img2.convert('RGB')
    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.LANCZOS)

    arr1 = np.array(img1).astype(np.float64)
    arr2 = np.array(img2).astype(np.float64)

    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    mu1 = np.mean(arr1)
    mu2 = np.mean(arr2)
    sigma1_sq = np.var(arr1)
    sigma2_sq = np.var(arr2)
    sigma12 = np.mean((arr1 - mu1) * (arr2 - mu2))

    numerator = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
    denominator = (mu1 ** 2 + mu2 ** 2 + C1) * (sigma1_sq + sigma2_sq + C2)

    return numerator / denominator


def assess_quality(original_path, compressed_path):
    """Assess image quality after compression."""
    try:
        img1 = Image.open(original_path)
        img2 = Image.open(compressed_path)

        psnr = calculate_psnr(img1, img2)
        ssim = calculate_ssim(img1, img2)

        if ssim >= 0.98 and psnr >= 45:
            rating = "Excellent - Virtually identical"
        elif ssim >= 0.95 and psnr >= 40:
            rating = "Very Good - Barely noticeable differences"
        elif ssim >= 0.90 and psnr >= 35:
            rating = "Good - Minor differences visible on close inspection"
        elif ssim >= 0.85 and psnr >= 30:
            rating = "Acceptable - Some quality loss visible"
        else:
            rating = "Noticeable quality loss"

        return {'psnr': psnr, 'ssim': ssim, 'rating': rating}
    except Exception as e:
        return {'psnr': None, 'ssim': None, 'rating': f"Could not assess: {e}"}


def compress_jpeg(input_path, output_path, quality=85, target_size=None):
    """
    Compress JPEG image.
    If target_size is specified, will try to find optimal quality.
    """
    img = Image.open(input_path)

    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    if target_size:
        # Binary search for optimal quality
        min_quality = 30
        max_quality = 95
        best_result = None
        best_quality = quality

        while min_quality <= max_quality:
            mid_quality = (min_quality + max_quality) // 2
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=mid_quality, optimize=True)
            size = buffer.tell()

            if size <= target_size:
                best_result = buffer.getvalue()
                best_quality = mid_quality
                min_quality = mid_quality + 1
            else:
                max_quality = mid_quality - 1

        if best_result:
            with open(output_path, 'wb') as f:
                f.write(best_result)
            return best_quality
        else:
            # Fallback to minimum quality
            img.save(output_path, format='JPEG', quality=30, optimize=True)
            return 30
    else:
        img.save(output_path, format='JPEG', quality=quality, optimize=True)
        return quality


def compress_png(input_path, output_path, optimization_level=2, target_size=None):
    """
    Compress PNG image using Pillow's optimization.
    For better compression, converts to palette mode if possible.
    """
    img = Image.open(input_path)

    # Try palette mode for non-photographic images
    if img.mode in ('RGB', 'RGBA'):
        # Convert to palette mode with adaptive palette
        if img.mode == 'RGBA':
            # Create white background for transparent images
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            img = background

        # Try palette conversion
        try:
            img_p = img.convert('P', palette=Image.ADAPTIVE, colors=256)
            # Check if palette mode produces smaller file
            buffer = io.BytesIO()
            img_p.save(buffer, format='PNG', optimize=True)
            palette_size = buffer.tell()

            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            rgb_size = buffer.tell()

            if palette_size < rgb_size * 0.9:  # Use palette if at least 10% smaller
                img = img_p
        except:
            pass

    if target_size:
        # For PNG, we mainly control compression level
        # Try different strategies
        strategies = [
            {'optimize': True},
            {'optimize': True, 'compress_level': 9},
        ]

        if img.mode == 'P':
            strategies.append({'optimize': True, 'compress_level': 9})

        best_result = None
        best_size = float('inf')

        for strategy in strategies:
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', **strategy)
            size = buffer.tell()
            if size < best_size:
                best_size = size
                best_result = buffer.getvalue()

        # If still too large, try reducing colors
        if best_size > target_size and img.mode != 'P':
            for colors in [128, 64, 32]:
                try:
                    img_reduced = img.convert('P', palette=Image.ADAPTIVE, colors=colors)
                    buffer = io.BytesIO()
                    img_reduced.save(buffer, format='PNG', optimize=True, compress_level=9)
                    size = buffer.tell()
                    if size <= target_size:
                        best_result = buffer.getvalue()
                        best_size = size
                        break
                except:
                    continue

        if best_result:
            with open(output_path, 'wb') as f:
                f.write(best_result)
        else:
            img.save(output_path, format='PNG', optimize=True, compress_level=9)
    else:
        compress_level = min(9, max(1, optimization_level * 3))
        img.save(output_path, format='PNG', optimize=True, compress_level=compress_level)


def move_to_trash(file_path):
    """Move file to trash/recycle bin."""
    file_path = Path(file_path)
    system = platform.system()

    if system == 'Darwin':  # macOS
        trash_path = Path.home() / '.Trash' / file_path.name
        # If file with same name exists in trash, add number suffix
        counter = 1
        original_name = trash_path.name
        while trash_path.exists():
            stem = Path(original_name).stem
            suffix = Path(original_name).suffix
            trash_path = trash_path.parent / f"{stem}_{counter}{suffix}"
            counter += 1
        shutil.move(str(file_path), str(trash_path))
        return str(trash_path)

    elif system == 'Windows':
        # On Windows, use Send2Trash if available, otherwise move to Recycle Bin
        try:
            from send2trash import send2trash
            send2trash(str(file_path))
            return f"Recycle Bin"
        except ImportError:
            # Fallback: move to a trash folder
            trash_dir = Path.home() / '.trash'
            trash_dir.mkdir(exist_ok=True)
            trash_path = trash_dir / file_path.name
            counter = 1
            original_name = trash_path.name
            while trash_path.exists():
                stem = Path(original_name).stem
                suffix = Path(original_name).suffix
                trash_path = trash_path.parent / f"{stem}_{counter}{suffix}"
                counter += 1
            shutil.move(str(file_path), str(trash_path))
            return str(trash_path)

    else:  # Linux
        # Try to use gio trash, otherwise move to ~/.local/share/Trash
        trash_dir = Path.home() / '.local/share/Trash/files'
        if trash_dir.exists():
            trash_path = trash_dir / file_path.name
            counter = 1
            original_name = trash_path.name
            while trash_path.exists():
                stem = Path(original_name).stem
                suffix = Path(original_name).suffix
                trash_path = trash_path.parent / f"{stem}_{counter}{suffix}"
                counter += 1
            shutil.move(str(file_path), str(trash_path))
            return str(trash_path)
        else:
            # Fallback
            fallback_trash = Path.home() / '.trash'
            fallback_trash.mkdir(exist_ok=True)
            trash_path = fallback_trash / file_path.name
            shutil.move(str(file_path), str(trash_path))
            return str(trash_path)


def compress_image_inplace(input_path, quality=85, target_size=None, png_optimization=2, output_format=None):
    """
    Compress image in place - replaces original file and moves it to trash.
    Returns compression result with quality assessment.
    """
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Determine output format
    if output_format:
        ext = output_format.lower()
        if ext == 'jpeg':
            ext = 'jpg'
    else:
        ext = input_path.suffix[1:].lower()

    # Create temp file for compressed output
    temp_output = input_path.parent / f".temp_compressed_{input_path.stem}.{ext}"

    try:
        # Compress to temp file
        result = compress_image(input_path, temp_output, quality, target_size, png_optimization)

        # Assess quality
        quality_metrics = assess_quality(input_path, temp_output)
        result['quality_metrics'] = quality_metrics

        # Move original to trash
        trash_location = move_to_trash(input_path)
        result['original_moved_to'] = trash_location

        # Move temp file to original location with original name (but new extension if changed)
        final_path = input_path.parent / f"{input_path.stem}.{ext}"
        # If file exists (shouldn't happen since we moved original), add suffix
        counter = 1
        original_final = final_path
        while final_path.exists():
            final_path = original_final.parent / f"{original_final.stem}_{counter}.{ext}"
            counter += 1

        shutil.move(str(temp_output), str(final_path))
        result['final_path'] = str(final_path)

        return result

    except Exception as e:
        # Clean up temp file if it exists
        if temp_output.exists():
            temp_output.unlink()
        raise e


def process_batch(input_dir, output_dir, quality=85, target_size=None, png_optimization=2):
    """Process all images in a directory."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_extensions = {'.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG'}
    results = []

    for img_path in input_dir.iterdir():
        if img_path.is_file() and img_path.suffix in image_extensions:
            output_path = output_dir / img_path.name
            try:
                result = compress_image(img_path, output_path, quality, target_size, png_optimization)
                result['input'] = str(img_path)
                result['output'] = str(output_path)
                result['success'] = True
                results.append(result)
                print(f"✓ {img_path.name}: {format_size(result['original_size'])} → {format_size(result['compressed_size'])} ({result['reduction_percent']:.1f}% reduction)")
            except Exception as e:
                results.append({
                    'input': str(img_path),
                    'output': str(output_path),
                    'success': False,
                    'error': str(e)
                })
                print(f"✗ {img_path.name}: Error - {e}")

    return results


def main():
    parser = argparse.ArgumentParser(description='Compress PNG and JPEG images')
    parser.add_argument('input', help='Input image file or directory (with --batch)')
    parser.add_argument('output', nargs='?', help='Output image file or directory')
    parser.add_argument('--batch', action='store_true', help='Process all images in input directory')
    parser.add_argument('--quality', type=int, default=85, help='JPEG quality (1-100, default: 85)')
    parser.add_argument('--target-size', type=str, help='Target file size (e.g., "500kb", "1mb")')
    parser.add_argument('--png-optimization', type=int, default=2, choices=[1, 2, 3],
                        help='PNG optimization level (1-3, default: 2)')
    parser.add_argument('--format', choices=['png', 'jpeg', 'jpg'], help='Output format')
    parser.add_argument('--backup', action='store_true', help='Create backup of original files')

    args = parser.parse_args()

    target_size = parse_target_size(args.target_size) if args.target_size else None

    if args.batch:
        if not args.output:
            print("Error: --batch requires an output directory")
            sys.exit(1)
        results = process_batch(args.input, args.output, args.quality, target_size, args.png_optimization)
        successful = sum(1 for r in results if r.get('success'))
        print(f"\nBatch complete: {successful}/{len(results)} images processed successfully")
    else:
        if not args.output:
            # Generate output filename
            input_path = Path(args.input)
            ext = args.format if args.format else input_path.suffix[1:]
            if ext == 'jpeg':
                ext = 'jpg'
            args.output = str(input_path.parent / f"{input_path.stem}_compressed.{ext}")

        result = compress_image(args.input, args.output, args.quality, target_size, args.png_optimization)

        print(f"Original: {format_size(result['original_size'])}")
        print(f"Compressed: {format_size(result['compressed_size'])}")
        print(f"Reduction: {result['reduction_percent']:.1f}%")
        if result['quality']:
            print(f"JPEG Quality: {result['quality']}")
        print(f"Output: {args.output}")


if __name__ == '__main__':
    main()
