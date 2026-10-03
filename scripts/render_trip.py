#!/usr/bin/env python3
"""
读取 data/attractions/*.json，聚合成 {城市: 数据}，注入 trip_template.html → trip.html。
页面零依赖、数据内嵌，双击即可打开；规划算法在浏览器端运行（scripts/trip_template.html 内）。

用法：
  python scripts/render_trip.py
"""
import json
import os
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "scripts", "trip_template.html")
SRC = os.path.join(ROOT, "data", "attractions")
OUT = os.path.join(ROOT, "trip.html")


def js(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def main():
    cities = {}
    for f in sorted(glob.glob(os.path.join(SRC, "*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        cities[d["city"]] = d
    if not cities:
        print("（没有找到 data/attractions/*.json，未生成）")
        return

    with open(TPL, encoding="utf-8") as fh:
        html = fh.read()
    html = html.replace("__CITIES__", js(cities))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"✓ 已生成 {OUT}（{len(html)/1024:.0f} KB · {len(cities)} 个城市："
          + "、".join(cities.keys()) + "）")


if __name__ == "__main__":
    main()
