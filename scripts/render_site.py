#!/usr/bin/env python3
"""
把 data.json + stations.json 注入 site_template.html，生成单文件 index.html。

页面本身零依赖：数据内嵌，双击即可打开；若本机跑着查询服务（默认 127.0.0.1:8787），
页面会自动切换成实时模式，支持任意起终点。

用法：
  python scripts/render_site.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "scripts", "site_template.html")
DEFAULT_API = "http://127.0.0.1:8787"


def js(obj):
    """对象 -> 可安全内嵌进 <script> 的 JSON。"""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def enrich(data):
    """给离线数据补上「具体车次衔接编排」，与实时模式输出保持一致。"""
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import api_server as apis
    except Exception as e:
        print(f"（跳过车次编排：{e}）")
        return data
    routes = [apis.enrich_route(r, i) for i, r in enumerate(data.get("routes", []), 1)]
    routes.sort(key=lambda r: (
        0 if r.get("plan_available") else (1 if r.get("time_feasible") else 2),
        r.get("plan_price") or r.get("total_price") or float("inf"),
        r.get("transfers", 0),
    ))
    for i, r in enumerate(routes, 1):
        r["id"] = i
    data["routes"] = routes
    data["best"] = routes[0] if routes else data.get("best")
    return data


def main():
    with open(os.path.join(ROOT, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    stations = []
    st_path = os.path.join(ROOT, "stations.json")
    if os.path.isfile(st_path):
        with open(st_path, encoding="utf-8") as f:
            stations = json.load(f)

    data = enrich(data)

    with open(TPL, encoding="utf-8") as f:
        html = f.read()
    html = (html
            .replace("__DATA__", js(data))
            .replace("__STATIONS__", js(stations))
            .replace('"__API__"', '"%s"' % os.environ.get("SITE_API", DEFAULT_API)))

    out = os.path.join(ROOT, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ 已生成 {out}（{len(html) / 1024:.0f} KB · "
          f"{len(data.get('routes', []))} 条路线 · {len(stations)} 个车站）")


if __name__ == "__main__":
    main()
