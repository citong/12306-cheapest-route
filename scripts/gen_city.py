#!/usr/bin/env python3
"""
生成城市级索引：站名->城市、城市->车站列表、省份->城市列表。

数据源同 gen_prov.py（npm china-division，走 npmmirror）。

产出：
  stations_city.json   车站名 -> 城市名，如 {"北京西": "北京", "昆明南": "昆明"}
  city_stations.json   城市名 -> 该市所有车站，如 {"北京": ["北京","北京西",...]}
  province_cities.json 省份 -> 该省城市列表，如 {"云南": ["昆明","大理",...]}

用法：
  python scripts/gen_city.py
"""
import io
import json
import os
import re
import tarfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = "https://registry.npmmirror.com/china-division/-/china-division-2.7.0.tgz"

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
# 车站名的方位/专线后缀，匹配城市时要先剥掉：北京西 -> 北京
STN_SUFFIX = re.compile(r"(东西南北|东南|东北|西南|西北|新塘|机场|港|站)+$")

# 明显不是客运主站的站名（支线、景区、货运、机场），排在主站后面
MINOR_KW = ("机场", "大学城", "长隆", "莲花山", "新塘", "物流", "货运",
            "工业园", "开发区", "港", "南站", "东站", "西站", "北站")
# 省会 / 大城市：省份展开成城市列表时排前面
BIG_CITY = {"北京", "上海", "天津", "重庆", "广州", "深圳", "成都", "杭州",
            "武汉", "西安", "南京", "苏州", "青岛", "大连", "宁波", "厦门",
            "沈阳", "长沙", "郑州", "济南", "合肥", "福州", "昆明", "南昌",
            "贵阳", "南宁", "太原", "石家庄", "哈尔滨", "长春", "兰州",
            "海口", "乌鲁木齐", "呼和浩特", "银川", "西宁", "拉萨"}
PROV_CAPITAL = {
    "河北": "石家庄", "山西": "太原", "辽宁": "沈阳", "吉林": "长春",
    "黑龙江": "哈尔滨", "江苏": "南京", "浙江": "杭州", "安徽": "合肥",
    "福建": "福州", "江西": "南昌", "山东": "济南", "河南": "郑州",
    "湖北": "武汉", "湖南": "长沙", "广东": "广州", "海南": "海口",
    "四川": "成都", "贵州": "贵阳", "云南": "昆明", "陕西": "西安",
    "甘肃": "兰州", "青海": "西宁", "台湾": "台北",
    "内蒙古": "呼和浩特", "广西": "南宁", "西藏": "拉萨",
    "宁夏": "银川", "新疆": "乌鲁木齐",
    "北京": "北京", "天津": "天津", "上海": "上海", "重庆": "重庆",
    "香港": "香港", "澳门": "澳门",
}


def stn_score(city, stn):
    """
    车站重要度打分（越大越靠前）。城市可能有很多站，全查会把 12306 打限流，
    所以默认只取前几个主站。
    """
    base = stn[:-1] if stn.endswith("站") else stn
    s = 0
    if base == city:
        s += 100                                  # 北京 / 郑州 / 昆明
    elif base == city + "站":
        s += 90
    elif re.fullmatch(re.escape(city) + r"[东南西北]", base):
        s += 70                                   # 北京西 / 上海南
    elif base.startswith(city):
        s += 40                                   # 北京丰台 / 昆明南
    if any(k in stn for k in MINOR_KW):
        s -= 60
    if stn in ("北京西", "北京南", "上海虹桥", "广州南", "广州东", "深圳北",
               "成都东", "杭州东", "武汉", "西安北", "南京南", "郑州东"):
        s += 30
    s -= min(len(base) - len(city), 6)            # 后缀越长越可能是支线
    return s


def fetch():
    print("→ 下载行政区划数据…", flush=True)
    raw = urllib.request.urlopen(PKG, timeout=120).read()
    tf = tarfile.open(fileobj=io.BytesIO(raw))
    return {n: json.loads(tf.extractfile("package/dist/" + n).read().decode("utf-8"))
            for n in ("provinces.json", "cities.json", "areas.json")}


def build():
    data = fetch()
    prov = {p["code"]: SHORT.get(p["name"], p["name"]) for p in data["provinces.json"]}

    # 市名(去后缀) -> (市名全称, 省简称)
    city_map, province_cities = {}, {}
    for c in data["cities.json"]:
        pn = prov.get(c["provinceCode"], "")
        if not pn:
            continue
        if c["name"] in ("市辖区", "县", "省直辖县级行政区划", "自治区直辖县级行政区划"):
            continue
        full = c["name"]
        key = CITY_SUFFIX.sub("", full)
        if len(key) >= 2:
            city_map[key] = (key, pn)
            province_cities.setdefault(pn, [])
            if key not in province_cities[pn]:
                province_cities[pn].append(key)
    # 直辖市在 cities.json 里叫「市辖区」，单独补回来
    for pn in prov.values():
        if pn in ("北京", "天津", "上海", "重庆"):
            city_map[pn] = (pn, pn)
            province_cities.setdefault(pn, [])
            if pn not in province_cities[pn]:
                province_cities[pn].append(pn)

    # 区县名(去后缀) -> 所属市
    area_map = {}
    city_of_code = {c["code"]: CITY_SUFFIX.sub("", c["name"])
                    for c in data["cities.json"]}
    for a in data["areas.json"]:
        key = AREA_SUFFIX.sub("", a["name"])
        cn = city_of_code.get(a.get("cityCode"), "")
        if len(key) >= 2 and cn:
            area_map.setdefault(key, (cn, prov.get(a["provinceCode"], "")))

    stations = []
    p = os.path.join(ROOT, "stations.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            stations = [s["n"] for s in json.load(f) if s.get("n")]

    city_keys = [k for k in city_map if len(k) >= 2]
    stations_city = {}
    for s in stations:
        name = s[:-1] if s.endswith("站") else s
        hit = city_map.get(name) or area_map.get(name)
        if not hit:
            # 剥掉方位/专线后缀再试：北京西 -> 北京，郑州航空港 -> 郑州
            stripped = STN_SUFFIX.sub("", name)
            if stripped and stripped != name:
                hit = city_map.get(stripped) or area_map.get(stripped)
        if not hit and len(name) > 2:
            best = ""
            for k in city_keys:
                if name.startswith(k) and len(k) > len(best):
                    best = k
            if best and len(name) - len(best) <= 3:
                hit = city_map[best]
        if hit:
            stations_city[s] = hit[0]

    city_stations = {}
    for s, c in stations_city.items():
        city_stations.setdefault(c, []).append(s)
    # 主站排前面：城市级搜索默认只取前几个，避免把 12306 打限流
    for c in city_stations:
        city_stations[c].sort(key=lambda x: (-stn_score(c, x), len(x), x))
    # 省会 / 大城市排前面：省份展开成城市列表时优先推荐这些
    for pn in province_cities:
        cap = PROV_CAPITAL.get(pn, "")
        province_cities[pn].sort(
            key=lambda x: (0 if x == cap else (1 if x in BIG_CITY else 2), len(x), x))

    for fn, obj in (("stations_city.json", stations_city),
                    ("city_stations.json", city_stations),
                    ("province_cities.json", province_cities)):
        with open(os.path.join(ROOT, fn), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))

    print(f"✓ stations_city.json   {len(stations_city)}/{len(stations)} 个站归属到城市")
    print(f"✓ city_stations.json  {len(city_stations)} 个城市")
    print(f"✓ province_cities.json {len(province_cities)} 个省份")
    for c in ("北京", "上海", "广州", "郑州", "昆明"):
        print(f"   {c}: {city_stations.get(c, [])}")


if __name__ == "__main__":
    build()
