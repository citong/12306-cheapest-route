#!/usr/bin/env python3
"""
生成车站地图页 map.html（单文件，内嵌车站名，坐标由腾讯地图实时检索）。

地图的地点检索需要密钥代理，只有本地服务能代理，静态托管的 GitHub Pages 上没有。
因此：
  - 有代理时（本地/预览环境）正常生成地图页；
  - 没有代理时（发布版）占位符保留，页面会明确提示「线上版用不了，请用本地服务打开」，
    而不是给一个白屏让人猜。

若自己有腾讯地图密钥，可用环境变量注入，让发布版也能用：
  WB_HTTP_PORT=8787 WB_TMAP_SECRET=xxx python scripts/render_map.py

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

    with open(TPL, encoding="utf-8") as f:
        html = f.read()
    # 密钥代理：有环境变量就注入真实地址，否则保留占位符（页面会提示线上版不可用）
    port = os.environ.get("WB_HTTP_PORT", "").strip()
    secret = os.environ.get("WB_TMAP_SECRET", "").strip()
    host = ("http://127.0.0.1:%s/_TMapService/_wbt/%s" % (port, secret)
            if port and secret else "__TMAP_PLACEHOLDER__")
    if host == "__TMAP_PLACEHOLDER__":
        host = "http://127.0.0.1:__WB_HTTP_PORT__/_TMapService/_wbt/__WB_TMAP_SECRET__"

    html = (html
            .replace("__STOPS__", js(stops))
            .replace("__ALL__", js(names))
            .replace("__CITY__", js(city))
            .replace("__PCITY__", js(pcity))
            .replace("__PROV__", js(prov))
            .replace("'__TMAP_HOST__'", "'%s'" % host)
            .replace("'__TMAP_HOST__'.indexOf", "'%s'.indexOf" % host))

    out = os.path.join(ROOT, "map.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ 已生成 {out}（{len(html) / 1024:.0f} KB · "
          f"{len(stops)} 个线路车站 · {len(names)} 个补全站名 · "
          f"{len(city)} 个城市）")


if __name__ == "__main__":
    main()
