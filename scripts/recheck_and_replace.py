#!/usr/bin/env python3
"""
recheck_and_replace.py — 基于审计结果，删除不相关图片并重新下载

读取 /tmp/image_audit_results.json，
对每个 is_related=False 的图片删除，
然后用更精准的搜索词重新下载相关图片。
"""

import json, pathlib, os, time, urllib.request, urllib.parse, socket
from PIL import Image
import io

socket.setdefaulttimeout(20)
HERMES_VENV_PY = "/Users/david/.hermes/hermes-agent/venv/bin/python3"
SEARXNG_URL = "http://127.0.0.1:8888"
EXPAND_DIR = pathlib.Path.home() / "Desktop/创意案例库_扩充"

# ── SearXNG ─────────────────────────────────────────────
def search_images(query, engines="bing images", limit=12):
    data = urllib.parse.urlencode({"q": query, "format": "json", "engines": engines}).encode()
    req = urllib.request.Request(f"{SEARXNG_URL}/search", data=data,
        headers={"User-Agent": "via54/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("results", [])
    except:
        return []

def extract_img_urls(results):
    urls = []
    for r in results:
        u = r.get("img_src") or r.get("url", "")
        if u and any(ext in u.lower() for ext in [".jpg",".jpeg",".png",".webp"]):
            urls.append(u)
    return urls

def download_img(url, dest_path, min_size=500):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        if len(data) > 15*1024*1024 or len(data) < 5000:
            return False, 0, 0
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        if w >= min_size or h >= min_size:
            if img.mode in ("RGBA","P","LA"):
                img = img.convert("RGB")
            img.save(dest_path, "JPEG", quality=88)
            return True, w, h
        return False, w, h
    except Exception as e:
        return False, 0, 0

# ── 主逻辑 ──────────────────────────────────────────────
def main():
    audit_path = pathlib.Path("/tmp/image_audit_results.json")
    if not audit_path.exists():
        print("No audit results found.")
        return

    with open(audit_path) as f:
        audit_data = json.load(f)

    # 加载所有案例的搜索词
    cases_queries = {}
    for case_dir in sorted(EXPAND_DIR.iterdir()):
        if not case_dir.is_dir() or case_dir.name.startswith("_") or case_dir.name == "searxng_results":
            continue
        reports = list(case_dir.glob("*深度报告.md"))
        if not reports:
            continue
        content = reports[0].read_text(encoding="utf-8")[:800]
        # 提取标题中的品牌+活动名
        lines = [l for l in content.split("\n") if l.strip()]
        title = lines[0] if lines else case_dir.name
        cases_queries[case_dir.name] = {
            "title": title.replace("#","").replace(">","").strip(),
            "content_snippet": content[:300]
        }

    # Step 1: 删除不相关图片
    print("=" * 60)
    print("Step 1: 删除不相关图片")
    print("=" * 60)
    deleted_total = 0
    for item in audit_data:
        case_name = item["case_name"]
        case_dir = EXPAND_DIR / case_name
        real_dir = case_dir / "images_real"
        if not real_dir.exists():
            continue

        for img_info in item["images"]:
            if not img_info.get("is_related", True):
                fp = pathlib.Path(img_info["path"])
                if fp.exists():
                    os.remove(fp)
                    deleted_total += 1
                    print(f"  🗑 {case_name}/{fp.name}")

    print(f"\nDeleted {deleted_total} irrelevant images.\n")

    # Step 2: 对删除过图片的案例重新下载
    print("=" * 60)
    print("Step 2: 重新下载相关图片")
    print("=" * 60)

    # 需要重新下载的案例（有不相关图片被删除的）
    cases_needing_redl = {item["case_name"] for item in audit_data
                           if any(not i.get("is_related", True) for i in item["images"])}

    for case_name in sorted(cases_needing_redl):
        case_dir = EXPAND_DIR / case_name
        real_dir = case_dir / "images_real"
        real_dir.mkdir(exist_ok=True)

        case_info = cases_queries.get(case_name, {"title": case_name, "content_snippet": ""})
        title = case_info["title"]

        # 提取品牌名
        brand = case_name.split("_")[0] if "_" in case_name else case_name[:6]

        # 构建精准搜索词
        queries = [
            f"{title} campaign official advertising Cannes Lions health",
            f"{title} healthcare brand marketing case study",
            f"{brand} {title} award winning creative campaign visual",
        ]

        print(f"\n{case_name}")
        print(f"  Title: {title}")

        all_urls = []
        for q in queries:
            print(f"  🔍 {q[:70]}")
            results = search_images(q)
            urls = extract_img_urls(results)
            print(f"     → {len(urls)} image URLs")
            all_urls.extend(urls)
            time.sleep(0.5)

        # 去重
        all_urls = list(dict.fromkeys(all_urls))
        print(f"  Total unique URLs: {len(all_urls)}")

        downloaded = 0
        for i, url in enumerate(all_urls):
            if downloaded >= 3:
                break
            dest = real_dir / f"{case_name}_{i+1:03d}.jpg"
            if dest.exists():
                continue
            ok, w, h = download_img(url, dest)
            if ok:
                downloaded += 1
                print(f"  ✅ {w}x{h} → {dest.name}")
            else:
                print(f"  ❌ {url[:70]}")
            time.sleep(0.5)

        print(f"  → {downloaded} images redownloaded")

    print("\n" + "=" * 60)
    print("完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
