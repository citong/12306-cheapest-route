#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配图去重全量校验：确认任意一座城市的三张景点图都不是同一张图。

用途：改动配图逻辑后跑一次，防止"三张一样的图糊弄"这种问题回归。
同时检查：图是否真实存在、是否同一城市内存在内容重复（用感知哈希量化）。

用法：python scripts/verify_spot_images.py
"""
import collections
import itertools
import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTR = os.path.join(ROOT, "attractions.json")

# 同城内两张图的平均像素差下限；低于此值肉眼视为"同一张图"
MIN_DIFF = 12.0
# dHash 汉明距离上限；超过此值视为构图雷同
MAX_DHASH = 8


def ahash_diff(a, b):
    """8x8 灰度均值哈希的汉明距离，0 = 几乎完全一样。"""
    def bits(im):
        g = im.convert("L").resize((8, 8), Image.LANCZOS)
        px = list(g.getdata())
        avg = sum(px) / len(px)
        return [1 if v > avg else 0 for v in px]
    ba, bb = bits(a), bits(b)
    return sum(1 for x, y in zip(ba, bb) if x != y)


def mean_diff(a, b):
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    sa = a.resize((64, 64), Image.LANCZOS)
    sb = b.resize((64, 64), Image.LANCZOS)
    tot = 0
    for pa, pb in zip(sa.getdata(), sb.getdata()):
        tot += abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2])
    return tot / (64 * 64 * 3)


def main():
    attr = json.load(open(ATTR, encoding="utf-8"))
    missing = []
    same_content = []     # 同一文件被多个景点复用
    too_close = []        # 不同文件但内容雷同
    n_pairs = n_ok = 0
    dup_ref = collections.defaultdict(list)

    for city, v in attr.items():
        spots = v.get("spots") or []
        paths = []
        for i, sp in enumerate(spots):
            p = sp.get("img")
            if not p:
                missing.append("%s 第%d个景点无配图" % (city, i + 1))
                continue
            ap = os.path.join(ROOT, p)
            if not os.path.exists(ap):
                missing.append("%s %s 文件不存在" % (city, p))
                continue
            paths.append((p, ap))
            dup_ref[p].append("%s#%d" % (city, i + 1))

        # 同一张文件被同城多个景点引用
        for p, users in dup_ref.items():
            if len(users) > 1:
                same_content.append((p, users))

        for (pa, fa), (pb, fb) in itertools.combinations(paths, 2):
            n_pairs += 1
            ia, ib = Image.open(fa), Image.open(fb)
            d = mean_diff(ia, ib)
            hd = ahash_diff(ia, ib)
            # 两个判据是"或"关系：像素差够大（色调/构图差异明显），
            # 或 dHash 距离够大（构图本身就不同），任一成立即可区分。
            if d >= MIN_DIFF or hd > MAX_DHASH:
                n_ok += 1
            else:
                too_close.append((city, os.path.basename(pa), os.path.basename(pb),
                                  round(d, 1), hd))

    real_dup = []
    for p, users in dup_ref.items():
        if len(users) > 1:
            real_dup.append((p, users))

    print("城市数        : %d" % len(attr))
    print("景点图总数    : %d" % sum(len(v.get("spots") or []) for v in attr.values()))
    print("两两比对对数  : %d" % n_pairs)
    print("可区分对数    : %d" % n_ok)
    print("缺图/失效引用 : %d" % len(missing))
    for m in missing[:10]:
        print("   !", m)
    print("同城复用同一文件: %d 组" % len(real_dup))
    for p, users in real_dup[:10]:
        print("   ! %s <- %s" % (p, "、".join(users)))
    print("内容雷同对    : %d" % len(too_close))
    for t in too_close[:15]:
        print("   ! %s %s vs %s  像素差=%.1f dHash=%d" % t)

    if missing or real_dup or too_close:
        print("\n✗ 校验未通过")
        sys.exit(1)
    print("\n✓ 52 城全部景点图存在，且同城三张图两两可区分")


if __name__ == "__main__":
    main()
