#!/usr/bin/env python3
"""
生成车站地图页 map.html（单文件，内嵌车站名 + 内置坐标，使用 Leaflet + 国内可达底图）。

坐标来源：
  - 内置 stations_geo.json（站名 -> 城市级坐标，覆盖约 85% 车站，离线即可用）；
  - 其余冷门城市在用户浏览器端用 Photon 地理编码补全（带 localStorage 缓存）。

底图用 Geoq（智图，国内确定可达）/ OpenStreetMap，Leaflet 库由用户浏览器从 CDN 加载
（多源兜底），因此线上 GitHub Pages 直接可用，不再依赖本地密钥代理。

用法：
  python scripts/render_map.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "scripts", "map_template.html")


def js(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def collect_stops(data):
    """从 data.json 收集车站：起点 / 终点 / 中转。"""
    meta = data.get("meta", {})
    frm, to = meta.get("from"), meta.get("to")
    stops = []
    if frm:
        stops.append({"n": frm, "k": "start"})
    if to:
        stops.append({"n": to, "k": "end"})
    seen = {frm, to}
    for r in data.get("routes", []):
        for p in r.get("path", []):
            if p and p not in seen:
                seen.add(p)
                stops.append({"n": p, "k": "via"})
    return stops


def main():
    with open(os.path.join(ROOT, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    stops = collect_stops(data)

    names = []
    p = os.path.join(ROOT, "stations.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            names = [s["n"] for s in json.load(f) if s.get("n")]

    def load(name):
        fp = os.path.join(ROOT, name)
        if os.path.isfile(fp):
            with open(fp, encoding="utf-8") as f:
                return json.load(f)
        return {}

    city = load("city_stations.json")
    pcity = load("province_cities.json")
    prov = load("stations_prov.json")

    geo = load("stations_geo.json")

    with open(TPL, encoding="utf-8") as f:
        html = f.read()

    html = (html
            .replace("__STOPS__", js(stops))
            .replace("__ALL__", js(names))
            .replace("__CITY__", js(city))
            .replace("__PCITY__", js(pcity))
            .replace("__PROV__", js(prov))
            .replace("__GEO__", js(geo)))

    out = os.path.join(ROOT, "map.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ 已生成 {out}（{len(html) / 1024:.0f} KB · "
          f"{len(stops)} 个线路车站 · {len(names)} 个补全站名 · "
          f"{len(city)} 个城市）")


if __name__ == "__main__":
    main()
