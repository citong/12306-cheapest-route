#!/usr/bin/env python3
"""从 12306 官方 station_name.js 生成 stations.json（供输入框自动补全）。

用法：
  python scripts/gen_stations.py
"""
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
OUT = os.path.join(ROOT, "stations.json")


def fetch():
    req = urllib.request.Request(SRC, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def main():
    print("→ 下载车站表…", flush=True)
    raw = fetch()
    m = re.search(r"var station_names\s*=\s*'?(.*?)'?;?\s*$", raw, re.S)
    body = m.group(1) if m else raw
    stations, seen = [], set()
    for chunk in body.split("@"):
        parts = chunk.split("|")
        if len(parts) < 4:
            continue
        short, name, code, pinyin = parts[0], parts[1], parts[2], parts[3]
        if not name or not code or code in seen:
            continue
        seen.add(code)
        stations.append({
            "n": name,
            "c": code,
            "p": pinyin,          # 全拼，如 beijingbei
            "i": short,           # 首字母缩写，如 bjb
        })
    stations.sort(key=lambda s: (len(s["n"]), s["n"]))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(stations, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ 已写入 {OUT}（{len(stations)} 个车站，"
          f"{os.path.getsize(OUT) / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
