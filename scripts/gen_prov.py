#!/usr/bin/env python3
"""
生成「车站名 -> 省份」映射 stations_prov.json。

数据源：npm 包 china-division 的省/市/区县三级行政区划（从 npmmirror 下载，
只取 provinces/cities/areas 三个小文件，不用下 villages）。

用法：
  python scripts/gen_prov.py
"""
import io
import json
import os
import re
import tarfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = "https://registry.npmmirror.com/china-division/-/china-division-2.7.0.tgz"

# 省级全称 -> 页面显示用的简称
SHORT = {
    "北京市": "北京", "天津市": "天津", "上海市": "上海", "重庆市": "重庆",
    "河北省": "河北", "山西省": "山西", "辽宁省": "辽宁", "吉林省": "吉林",
    "黑龙江省": "黑龙江", "江苏省": "江苏", "浙江省": "浙江", "安徽省": "安徽",
    "福建省": "福建", "江西省": "江西", "山东省": "山东", "河南省": "河南",
    "湖北省": "湖北", "湖南省": "湖南", "广东省": "广东", "海南省": "海南",
    "四川省": "四川", "贵州省": "贵州", "云南省": "云南", "陕西省": "陕西",
    "甘肃省": "甘肃", "青海省": "青海", "台湾省": "台湾",
    "内蒙古自治区": "内蒙古", "广西壮族自治区": "广西", "西藏自治区": "西藏",
    "宁夏回族自治区": "宁夏", "新疆维吾尔自治区": "新疆",
    "香港特别行政区": "香港", "澳门特别行政区": "澳门",
}

CITY_SUFFIX = re.compile(r"(市|地区|自治州|盟|特别行政区)$")
AREA_SUFFIX = re.compile(r"(自治县|自治旗|市|县|区|旗|特区|林区)$")


def fetch():
    print("→ 下载行政区划数据…", flush=True)
    raw = urllib.request.urlopen(PKG, timeout=120).read()
    tf = tarfile.open(fileobj=io.BytesIO(raw))
    out = {}
    for name in ("provinces.json", "cities.json", "areas.json"):
        out[name] = json.loads(tf.extractfile("package/dist/" + name).read().decode("utf-8"))
    return out


def build():
    data = fetch()
    prov = {p["code"]: SHORT.get(p["name"], p["name"]) for p in data["provinces.json"]}

    city_map = {}
    for c in data["cities.json"]:
        if c["name"] in ("市辖区", "县", "省直辖县级行政区划", "自治区直辖县级行政区划"):
            continue
        key = CITY_SUFFIX.sub("", c["name"])
        if len(key) >= 2:
            city_map[key] = prov.get(c["provinceCode"], "")
    # 直辖市在 cities.json 里叫「市辖区」，会被上面过滤掉，单独补回来，
    # 否则「北京西」「上海南」这类站名匹配不到。
    for name in prov.values():
        if name in ("北京", "天津", "上海", "重庆"):
            city_map[name] = name

    area_map = {}
    for a in data["areas.json"]:
        key = AREA_SUFFIX.sub("", a["name"])
        if len(key) >= 2:
            area_map.setdefault(key, prov.get(a["provinceCode"], ""))

    stations = []
    p = os.path.join(ROOT, "stations.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            stations = [s["n"] for s in json.load(f) if s.get("n")]

    city_keys = [k for k in city_map if len(k) >= 2]
    result = {}
    for s in stations:
        name = s[:-1] if s.endswith("站") else s
        if name in city_map:
            result[s] = city_map[name]
            continue
        if name in area_map:
            result[s] = area_map[name]
            continue
        # 站名是城市名 + 方位词（北京西 / 昆明南 / 武汉东）时按最长前缀兜底
        if len(name) > 2:
            best = ""
            for k in city_keys:
                if name.startswith(k) and len(k) > len(best):
                    best = k
            if best and len(name) - len(best) <= 3:
                result[s] = city_map[best]

    out = os.path.join(ROOT, "stations_prov.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ 已生成 {out}（{len(result)}/{len(stations)} 个车站匹配到省份）")
    for k in list(result)[:8]:
        print(f"   {k} -> {result[k]}")


if __name__ == "__main__":
    build()
