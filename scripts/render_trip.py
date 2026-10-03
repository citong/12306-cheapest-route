#!/usr/bin/env python3
"""
读取 data/attractions/*.json，聚合成 {城市: 数据}，注入 trip_template.html → trip.html。
页面零依赖、数据内嵌，双击即可打开；规划算法在浏览器端运行（scripts/trip_template.html 内）。

注入内容：
  __CITIES__    行程数据（含每个景点的 s.img 配图路径）
  __CITY_IMG__  城市 -> 横幅图路径（与主站景点抽屉共用同一批实景图，键需匹配）

景点配图规则（与 scripts/unify_cards.py 保持一致）：
  1) 优先用景点自己的实景图 spot-<slug>-<n>.jpg
  2) 其次用该城横幅 pop-<slug>.jpg 兜底
键名以 data/attractions/<key>.json 的文件名（去扩展名）为准，与主站 ATTR 的键一致。

用法：
  python scripts/render_trip.py
"""
import json
import os
import re
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "scripts", "trip_template.html")
SITE_TPL = os.path.join(ROOT, "scripts", "site_template.html")
SRC = os.path.join(ROOT, "data", "attractions")
OUT = os.path.join(ROOT, "trip.html")


def js(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def city_img_map():
    """从主站模板的 CITY_IMG 解析 城市 -> images/pop-xxx.jpg，保证两页同源。"""
    src = open(SITE_TPL, encoding="utf-8").read()
    m = re.search(r"const CITY_IMG\s*=\s*\{(.*?)\};", src, re.S)
    if not m:
        return {}
    return {city: "images/pop-%s.jpg" % slug
            for city, slug in re.findall(r"'([^']+)'\s*:\s*'images/pop-([^']+)\.jpg'", m.group(1))}


def main():
    cityimg = city_img_map()
    cities = {}
    for f in sorted(glob.glob(os.path.join(SRC, "*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        key = os.path.splitext(os.path.basename(f))[0]     # 文件名即 ATTR 键
        # 为每个景点补配图：优先独立景点图，否则用城市横幅
        banner = cityimg.get(key)
        slug = os.path.basename(banner)[4:-4] if banner else None
        for i, s in enumerate(d.get("spots") or []):
            if not s.get("img") and slug:
                cand = "images/spot-%s-%d.jpg" % (slug, i + 1)
                s["img"] = cand if os.path.exists(os.path.join(ROOT, cand)) else banner
        cities[key] = d

    if not cities:
        print("（没有找到 data/attractions/*.json，未生成）")
        return

    with open(TPL, encoding="utf-8") as fh:
        html = fh.read()
    html = html.replace("__CITIES__", js(cities))
    html = html.replace("__CITY_IMG__", js(cityimg))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    n_img = sum(1 for c in cities.values() for s in (c.get("spots") or []) if s.get("img"))
    n_all = sum(len(c.get("spots") or []) for c in cities.values())
    print(f"✓ 已生成 {OUT}（{len(html)/1024:.0f} KB · {len(cities)} 个城市"
          f" · 景点配图 {n_img}/{n_all}）：" + "、".join(cities.keys()) + "）")


if __name__ == "__main__":
    main()
