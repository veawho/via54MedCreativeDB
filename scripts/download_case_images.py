#!C:/Users/via54/AppData/Local/hermes/venv/Scripts/python.exe
"""
download_case_images.py — 通过 SearXNG 为缺图案例下载真实图片（>=500px）
"""

import json
import os
import time
import urllib.request
import urllib.parse
from pathlib import Path
from PIL import Image
import re
import socket

socket.setdefaulttimeout(20)

SEARXNG_URL = "http://127.0.0.1:8888"
EXPAND_DIR = Path.home() / "Desktop/创意案例库_扩充"
OUT_SUMMARY = EXPAND_DIR / "searxng_results" / "_image_download_summary.json"
OUT_SUMMARY.parent.mkdir(exist_ok=True)

# ─── SearXNG 图片搜索 ───────────────────────────────────
def search_images(query, limit=8):
    """通过 SearXNG Bing Images 搜索图片 URL"""
    data = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "engines": "bing images"
    }).encode()
    req = urllib.request.Request(
        f"{SEARXNG_URL}/search",
        data=data,
        headers={"User-Agent": "via54-img-download/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {}


def extract_image_urls(raw_results):
    """从 SearXNG 结果提取可能的图片 URL"""
    urls = []
    for r in raw_results.get("results", []):
        url = r.get("url", "")
        img_src = r.get("img_src", "")
        if img_src and img_src not in urls:
            urls.append(img_src)
        elif url and any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
            if url not in urls:
                urls.append(url)
    return urls


# ─── 图片下载 + 尺寸验证 ─────────────────────────────────
def download_and_verify(img_url, dest_path, min_size=500):
    """下载图片并验证尺寸，返回 True/False"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.google.com/",
    }
    try:
        req = urllib.request.Request(img_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
    except Exception as e:
        return (False, 0, 0)

    # 跳过太大（>15MB）或太小（<5KB）的文件
    if len(data) > 15 * 1024 * 1024 or len(data) < 5000:
        return False

    try:
        import io
        img = Image.open(io.BytesIO(data))
        w, h = img.size

        # 任一边 >= min_size
        if w >= min_size or h >= min_size:
            # 转换为 RGB 保存
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            img.save(dest_path, "JPEG", quality=88)
            return (True, w, h)
        return (False, w, h)
    except Exception:
        return (False, 0, 0)


def get_case_search_queries(case_dir_name):
    """为案例构建图片搜索查询词"""
    # 从目录名提取品牌
    parts = re.split(r'[_：]', case_dir_name)
    brand = parts[0] if parts else case_dir_name
    campaign = parts[1] if len(parts) > 1 else ""
    
    queries = [
        f'{brand} {campaign} Cannes Lions 2024 2025 campaign official',
        f'{brand} {campaign} healthcare advertising award winner',
        f'{brand} {campaign} pharma marketing case study image',
    ]
    return [q for q in queries if len(q) > 8][:2]


def process_case(case_dir):
    """为单个案例下载图片"""
    name = case_dir.name
    real_dir = case_dir / "images_real"
    real_dir.mkdir(exist_ok=True)
    
    # 检查已有哪些图（跳过已有）
    existing = list(real_dir.glob("*.jpg"))
    if len(existing) >= 3:
        return {"case": name, "status": "skip", "downloaded": 0, "note": "already has images"}
    
    queries = get_case_search_queries(name)
    downloaded = []
    
    for query in queries:
        if len(downloaded) >= 3:
            break
        
        print(f"    🔍 [{name}] {query[:60]}")
        results = search_images(query)
        img_urls = extract_image_urls(results)
        
        for url in img_urls:
            if len(downloaded) >= 3:
                break
            
            idx = len(downloaded) + 1
            dest = real_dir / f"{name}_{idx:03d}.jpg"
            
            ok, w, h = download_and_verify(url, dest)
            if isinstance(ok, bool) and not ok:
                # download failed (returned False, not a tuple)
                print(f"      ❌ download failed {url[:80]}")
            elif ok:
                downloaded.append({"url": url, "w": w, "h": h, "dest": str(dest)})
                print(f"      ✅ {w}x{h} → {dest.name}")
            else:
                print(f"      ❌ size reject {w}x{h} {url[:80]}")
            
            time.sleep(0.8)
    
    return {
        "case": name,
        "status": "ok" if downloaded else "failed",
        "downloaded": len(downloaded),
        "images": downloaded,
        "queries_used": queries,
    }


def main():
    print("=" * 60)
    print("SearXNG 图片下载（验证 >=500px）")
    print("=" * 60)
    
    expand_dir = Path.home() / "Desktop/创意案例库_扩充"
    
    # 找出缺图案例
    need_images = []
    for case_dir in sorted(expand_dir.iterdir()):
        if not case_dir.is_dir() or case_dir.name.startswith("_") or case_dir.name == "searxng_results":
            continue
        real_imgs = [p for p in (case_dir / "images_real").glob("*.jpg")
                     if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]]
        # 验证尺寸
        good = 0
        for p in real_imgs:
            try:
                with Image.open(p) as img:
                    if img.width >= 500 or img.height >= 500:
                        good += 1
            except:
                pass
        if good < 3:
            need_images.append(case_dir)
    
    print(f"\n缺图案例: {len(need_images)}\n")
    
    all_results = []
    for i, case_dir in enumerate(need_images, 1):
        print(f"\n[{i}/{len(need_images)}] {case_dir.name}")
        try:
            result = process_case(case_dir)
            all_results.append(result)
            print(f"  → {result['status']} ({result['downloaded']} new images)")
        except Exception as e:
            print(f"  → ERROR: {e}")
            all_results.append({"case": case_dir.name, "status": "error", "downloaded": 0})
        time.sleep(1)
    
    # 汇总
    total_dl = sum(r["downloaded"] for r in all_results)
    with_images = sum(1 for r in all_results if r["downloaded"] > 0)
    
    print("\n" + "=" * 60)
    print(f"完成: {len(all_results)} 个案例处理")
    print(f"新增图片: {total_dl} 张")
    print(f"有图案例: {with_images}/{len(all_results)}")
    print("=" * 60)
    
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
