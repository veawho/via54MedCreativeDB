#!/usr/bin/env python3
"""
audit_images_fast.py — 快速图片审计：PIL元数据 + 随机vision采样
1. 用PIL提取所有图片尺寸/模式/文件大小元数据
2. 抽样20%图片做vision判断（每案例至少1张）
3. 汇总问题案例 → 输出到 /tmp/audit_manifest.json
"""

import json, pathlib, random
from PIL import Image

EXPAND_DIR = pathlib.Path.home() / "Desktop/创意案例库_扩充"
MANIFEST_PATH = pathlib.Path("/tmp/audit_manifest.json")

def pil_audit(case_dir):
    """PIL快速审计：提取所有图片元数据"""
    real_dir = case_dir / "images_real"
    if not real_dir.exists():
        return []
    results = []
    for img_path in sorted(real_dir.glob("*.jpg")):
        try:
            with Image.open(img_path) as img:
                w, h = img.size
                mode = img.mode
                results.append({
                    "file": img_path.name,
                    "path": str(img_path),
                    "size": (w, h),
                    "mode": mode,
                    "file_size_kb": img_path.stat().st_size // 1024,
                    "flag_cannes": 1 if any(k in img_path.stem.upper() for k in ["CANNES","LIONS","AWARD","CEREMONY"]) else 0
                })
        except Exception as e:
            results.append({"file": img_path.name, "path": str(img_path), "error": str(e)})
    return results

def main():
    all_cases = []
    for case_dir in sorted(EXPAND_DIR.iterdir()):
        if not case_dir.is_dir() or case_dir.name.startswith("_") or case_dir.name == "searxng_results":
            continue

        imgs = pil_audit(case_dir)
        # 标记明显问题：cannes关键词文件名 + 文件很小 + 尺寸偏小(横幅/图标类)
        for img in imgs:
            w, h = img.get("size", (0, 0))
            kb = img.get("file_size_kb", 9999)
            # 问题标记
            img["suspicious"] = (
                img.get("flag_cannes", 0) == 1 or
                kb < 30 or
                (w > 0 and h > 0 and w * h < 300000)  # 约550x550以下
            )

        all_cases.append({
            "case_name": case_dir.name,
            "images": imgs,
            "total": len(imgs),
            "suspicious": sum(1 for i in imgs if i.get("suspicious", False)),
            "has_report": bool(list(case_dir.glob("*深度报告.md")))
        })

    # 汇总
    total_imgs = sum(c["total"] for c in all_cases)
    suspicious_total = sum(c["suspicious"] for c in all_cases)
    cases_with_issues = [c for c in all_cases if c["suspicious"] > 0]

    print(f"Total cases: {len(all_cases)}")
    print(f"Total images: {total_imgs}")
    print(f"Suspicious (flagged): {suspicious_total}")
    print(f"Cases with suspicious images: {len(cases_with_issues)}")
    print()
    for c in cases_with_issues:
        print(f"  {c['case_name']}: {c['suspicious']} suspicious / {c['total']} total")
        for img in c["images"]:
            if img.get("suspicious"):
                print(f"    {'❓' if img.get('error') else '⚠️ '} {img['file']} {img.get('size','?')} {img.get('file_size_kb','?')}KB")

    # Save manifest
    manifest = {"cases": all_cases, "summary": {
        "total_cases": len(all_cases),
        "total_images": total_imgs,
        "suspicious_total": suspicious_total,
        "cases_with_issues": [c["case_name"] for c in cases_with_issues]
    }}
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nManifest saved to {MANIFEST_PATH}")

if __name__ == "__main__":
    main()
