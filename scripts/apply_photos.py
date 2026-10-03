#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 scripts/fetch_photos.py 抓到的照片回填到两份数据里：
  1) 主站 attractions.json      —— 每个景点 s.img 指向 images/ph-<slug>-<n>.jpg
  2) 行程 data/attractions/*.json —— 每个景点 s.img 指向同一批图

文件名由「该城景点顺序」决定（与 fetch_photos.targets() 一致）：
  第一张 ph-<slug>-1.jpg 是主站该城第 1 个景点，之后依次是主站第 2、3 个，
  再接行程页追加的景点。所以同一景点在主站与行程页看到的是同一张图。

抓取失败的景点保持原样（主站保留旧 img，行程页交给 render_trip 兜底）。

用法：
  python scripts/apply_photos.py            # 回填
  python scripts/apply_photos.py --dry      # 只看统计
"""
import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import fetch_photos as F  # noqa: E402


def build_mapping():
    slugs = F.slug_of_city()
    tgt = F.targets()
    mp, total, have = {}, 0, 0
    for city, names in tgt.items():
        slug = slugs.get(city)
        if not slug:
            continue
        mp[city] = {}
        for i, name in enumerate(names):
            total += 1
            rel = "images/ph-%s-%d.jpg" % (slug, i + 1)
            if os.path.exists(os.path.join(ROOT, rel)):
                mp[city][name] = rel
                have += 1
    return mp, total, have


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    mp, total, have = build_mapping()
    print("照片覆盖：%d / %d 个景点" % (have, total))

    # --- 1) 主站 ---
    p = os.path.join(ROOT, "attractions.json")
    a = json.load(open(p, encoding="utf-8"))
    n_main = 0
    for city, v in a.items():
        for s in v.get("spots") or []:
            f = mp.get(city, {}).get(s.get("n"))
            if f:
                s["img"] = f
                n_main += 1
    if not args.dry:
        json.dump(a, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("主站 attractions.json：更新 %d 张" % n_main)

    # --- 2) 行程 ---
    n_trip = 0
    miss = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "attractions", "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        key = os.path.splitext(os.path.basename(f))[0]
        for s in d.get("spots") or []:
            img = mp.get(key, {}).get(s.get("n"))
            if img:
                s["img"] = img
                n_trip += 1
            else:
                miss.append(key + "/" + str(s.get("n")))
        if not args.dry:
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("行程 data/attractions/*.json：更新 %d 张" % n_trip)
    if miss:
        print("行程页缺图（%d，将回退城市横幅）：" % len(miss), "、".join(miss[:20]))


if __name__ == "__main__":
    main()
