#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓图完成后的自检：
  1) 覆盖率：230 个景点里有多少拿到了 ph- 实景图；
  2) 同城去重：同一城市的 ph-<slug>-<n>.jpg 是否两两可区分
     （dHash 汉明距 < 8 视为疑似同一张，正是用户吐槽的"同一种图用三次"）。
  3) 列出疑似重复的 (城市, 文件) 对，方便人工复核。

用法：
  python scripts/verify_photos.py
"""
import glob
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "images")
DHASH_MIN = 8


def dhash(im, n=8):
    px = im.convert("L").resize((n + 1, n), Image.NEAREST).tobytes()
    bits = 0
    for r in range(n):
        for c in range(n):
            bits = (bits << 1) | (1 if px[r * (n + 1) + c] < px[r * (n + 1) + c + 1] else 0)
    return bits


def ham(a, b):
    return bin(a ^ b).count("1")


def main():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import fetch_photos as F
    tgt = F.targets()
    total = sum(len(v) for v in tgt.values())

    # 覆盖率
    have, missing = 0, []
    for city, names in tgt.items():
        slug = F.slug_of_city().get(city)
        if not slug:
            continue
        for i, name in enumerate(names):
            p = os.path.join(ROOT, "images/ph-%s-%d.jpg" % (slug, i + 1))
            if os.path.exists(p):
                have += 1
            else:
                missing.append(city + "/" + name)
    print("覆盖率：%d / %d 个景点有实景图（缺 %d）" % (have, total, len(missing)))
    if missing:
        print("  缺图样例:", "、".join(missing[:15]))

    # 同城去重检查
    bad = 0
    for fp in sorted(glob.glob(os.path.join(IMG, "ph-*.jpg"))):
        # 按城市 slug 分组
        pass
    # 按城市 slug 聚合
    by_city = {}
    for fp in sorted(glob.glob(os.path.join(IMG, "ph-*.jpg"))):
        slug = os.path.basename(fp)[3:-6]  # ph-<slug>-<n>.jpg -> slug
        by_city.setdefault(slug, []).append(fp)
    print("\n同城去重检查（dHash 汉明距 < %d 视为疑似重复）：" % DHASH_MIN)
    dup_pairs = []
    for slug, files in sorted(by_city.items()):
        if len(files) < 2:
            continue
        hashes = []
        for f in files:
            try:
                h = dhash(Image.open(f))
            except Exception:
                continue
            hashes.append((os.path.basename(f), h))
        for a in range(len(hashes)):
            for b in range(a + 1, len(hashes)):
                d = ham(hashes[a][1], hashes[b][1])
                if d < DHASH_MIN:
                    dup_pairs.append((slug, hashes[a][0], hashes[b][0], d))
    if dup_pairs:
        bad = len(dup_pairs)
        print("  ⚠ 发现 %d 对疑似重复：" % bad)
        for slug, f1, f2, d in dup_pairs[:30]:
            print("    %s: %s ⇔ %s  (汉明距 %d)" % (slug, f1, f2, d))
    else:
        print("  ✓ 所有同城 ph- 图两两可区分，无重复。")
    print("\n结论：", "存在疑似重复，需复核" if bad else "OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
