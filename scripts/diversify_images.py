#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""景点配图「去重」生成器（替代旧的同源三裁）。

问题背景
----------
旧版unify_cards.py 从城市横幅裁 3 张 16:9 图当 3 个景点的配图。但横幅多为
480x441（约 1.09:1），裁到 16:9 时**横向余量为 0**（nw == w），所以三种
fx 偏移全部被 clamp 成同一个窗口 —— 三张图只差一点点调色，肉眼完全一样，
等于拿同一张图糊弄三张卡片。

本脚本的做法
------------
每张派生图 = 独立的「变焦倍数 + 画幅比例 + 取景中心 + 镜像 + 调色」配方，
让 3 张图在构图尺度、比例、色调三个维度都不同，一眼能分辨：
  #1  16:9  全景 1.00x，取景偏上        → 交代城市整体面貌
  #2  3:2   中景 1.35x + 水平镜像 + 浓郁→ 有层次的局部
  #3  1:1   近景 1.30x + 冷暖反差        → 细节特写

不变式：不做上采样（输出宽高<= 裁切原始尺寸），保证放大到卡片里也不糊。
自检：任两张派生图的平均像素差必须 >= MIN_DIFF，否则报错。
"""
import glob
import itertools
import json
import os
import re
import sys

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TPL = os.path.join(HERE, "site_template.html")
IMG = os.path.join(ROOT, "images")
ATTR = os.path.join(ROOT, "attractions.json")
CITY_IMG_JSON = os.path.join(HERE, "city_img.json")

MIN_DIFF = 18.0# 两图平均像素差下限（0-255）
MAX_W = 520# 输出最大宽度


# 12 城用图片生成单独做过实景点图，绝不能被派生逻辑覆盖
REAL_CITIES = {"北京", "上海", "成都", "西安", "杭州", "重庆",
               "广州", "三亚", "昆明", "厦门", "桂林", "丽江"}


# 三种配方：ratio 画幅、zoom 变焦、cx/cy 取景中心、mirror 镜像、grade 调色
RECIPES = [
    dict(ratio=16 / 9, zoom=1.00, cx=0.50, cy=0.38, mirror=False,
         grade=dict(color=1.04, contrast=1.02)),
    dict(ratio=3 / 2, zoom=1.35, cx=0.42, cy=0.58, mirror=True,
         grade=dict(color=1.18, contrast=1.10, sharpness=1.4)),
    dict(ratio=1 / 1, zoom=1.30, cx=0.60, cy=0.60, mirror=False,
         grade=dict(color=0.94, contrast=1.16, brightness=1.04, warmth=-0.10)),
]


def load_city_img():
    """城市 -> images/pop-xxx.jpg。优先读缓存 city_img.json，其次解析模板。"""
    if os.path.exists(CITY_IMG_JSON):
        try:
            return json.load(open(CITY_IMG_JSON, encoding="utf-8"))
        except Exception:
            pass
    src = open(TPL, encoding="utf-8").read()
    m = re.search(r"const CITY_IMG\s*=\s*\{(.*?)\};", src, re.S)
    if not m:
        sys.exit("!! 未能在 site_template.html 中找到 CITY_IMG")
    out = {city: "images/pop-%s.jpg" % slug for city, slug in
           re.findall(r"'([^']+)'\s*:\s*'images/pop-([^']+)\.jpg'", m.group(1))}
    with open(CITY_IMG_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out


def crop_by_recipe(im, r):
    """按配方裁出画幅（不放大）。"""
    W, H = im.size
    cw = W / r["zoom"]
    ch = cw / r["ratio"]
    if ch > H:
        ch = H
        cw = ch * r["ratio"]
    x0 = (W - cw) * r["cx"]
    y0 = (H - ch) * r["cy"]
    box = (int(round(max(0, min(W - cw, x0)))),
           int(round(max(0, min(H - ch, y0)))),
           int(round(max(0, min(W - cw, x0)) + cw)),
           int(round(max(0, min(H - ch, y0)) + ch)))
    out = im.crop(box)
    if r["mirror"]:
        out = ImageOps.mirror(out)
    return out


def apply_grade(im, r, idx):
    g = r["grade"]
    if "warmth" in g:                      # 正=偏暖，负=偏冷
        w = g["warmth"]
        if w > 0:
            im = ImageEnhance.Brightness(im).enhance(1 + 0.05 * w)
            r_, g_, b_ = im.split()
            r_ = r_.point(lambda v: min(255, int(v * (1 + 0.10 * w))))
            b_ = b_.point(lambda v: max(0, int(v * (1 - 0.10 * w))))
            im = Image.merge("RGB", (r_, g_, b_))
        else:
            k = -w
            r_, g_, b_ = im.split()
            r_ = r_.point(lambda v: max(0, int(v * (1 - 0.09 * k))))
            b_ = b_.point(lambda v: min(255, int(v * (1 + 0.12 * k))))
            im = Image.merge("RGB", (r_, g_, b_))
    im = ImageEnhance.Color(im).enhance(g.get("color", 1.0))
    im = ImageEnhance.Contrast(im).enhance(g.get("contrast", 1.0))
    if "brightness" in g:
        im = ImageEnhance.Brightness(im).enhance(g["brightness"])
    if g.get("sharpness"):
        im = im.filter(ImageFilter.UnsharpMask(
            radius=1.4, percent=int(70 * g["sharpness"]), threshold=3))
    return im


def mean_diff(a, b):
    """缩放到同尺寸后算平均像素差，0-255。"""
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    small_a = a.resize((64, 64), Image.LANCZOS)
    small_b = b.resize((64, 64), Image.LANCZOS)
    tot = 0
    for pa, pb in zip(small_a.getdata(), small_b.getdata()):
        tot += abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2])
    return tot / (64 * 64 * 3)


def build_city_images(src_path, slug, n=3, force=True):
    """为一座城市生成 n 张差异化景点图，返回 [(path, size), ...]。"""
    im = Image.open(src_path).convert("RGB")
    outs = []
    for i in range(n):
        r = RECIPES[i % len(RECIPES)]
        pic = apply_grade(crop_by_recipe(im, r), r, i)
        if pic.width > MAX_W:
            pic = pic.resize((MAX_W, max(1, round(MAX_W * pic.height / pic.width))),
                             Image.LANCZOS)
        dst = os.path.join(IMG, "spot-%s-%d.jpg" % (slug, i + 1))
        pic.save(dst, "JPEG", quality=76, optimize=True, progressive=True)
        outs.append((dst, pic))
    return outs


def main():
    force = "--force" in sys.argv
    cityimg = load_city_img()
    attr = json.load(open(ATTR, encoding="utf-8"))
    n_city = n_diff = 0
    worst = []

    for city, v in attr.items():
        if city in REAL_CITIES:
            continue                       # 真实景点图受保护
        banner = cityimg.get(city)
        if not banner:
            print("!! %s 没有横幅图，跳过" % city)
            continue
        src = os.path.join(ROOT, banner)
        if not os.path.exists(src):
            print("!! %s 横幅缺失 %s" % (city, banner))
            continue
        slug = os.path.basename(banner)[4:-4]
        spots = v.get("spots") or []
        dsts = ["images/spot-%s-%d.jpg" % (slug, i + 1) for i in range(len(spots))]
        if not force and all(os.path.exists(os.path.join(ROOT, d)) for d in dsts):
            continue
        imgs = build_city_images(src, slug, len(spots), force=True)
        n_city += 1
        for sp, (path, _pic) in zip(spots, imgs):
            sp["img"] = "images/" + os.path.basename(path)
        # 自检：三张必须彼此可区分
        for (pa, _), (pb, _) in itertools.combinations(imgs, 2):
            d = mean_diff(Image.open(pa), Image.open(pb))
            worst.append((round(d, 1), city, os.path.basename(pa), os.path.basename(pb)))
            if d >= MIN_DIFF:
                n_diff += 1

    with open(ATTR, "w", encoding="utf-8") as f:
        json.dump(attr, f, ensure_ascii=False, indent=2)

    worst.sort()
    print("重新派生城市数: %d（%d 城保留实景点图）" % (n_city, len(REAL_CITIES)))
    print("两两差异达标对数: %d" % n_diff)
    if worst:
        print("差异最小的 5 对（越大越不像）：")
        for d, c, a, b in worst[:5]:
            print("   %5.1f  %s  %s vs %s" % (d, c, a, b))
    fail = [x for x in worst if x[0] < MIN_DIFF]
    if fail:
        print("!! 有 %d 对差异不足 %.0f，需换源图" % (len(fail), MIN_DIFF))
        sys.exit(1)
    print("✓ 全部派生图两两可区分")


if __name__ == "__main__":
    main()
