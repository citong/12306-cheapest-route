#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按「景点名」抓取该景点自己的真实照片，压缩后落盘，并生成 photo_map.json。

背景：
  之前 40 个城市的三张景点图是同一张城市横幅裁出来的（变焦/镜像/调色），
  本质仍是"同一张图用三次"；行程页更夸张，8~10 个景点共用 3 张图
  （第 4 张起 render_trip.py 直接回退到城市横幅）。用户要求每张卡片显示
  "该地区该景点"的图 —— 所以必须真正按景点去搜图。

数据源（按可靠性排序，实测）：
  1) 360 图片搜索 image.so.com/j  —— 中文查询命中率高、标题含景点名、
     缩略图在 p*.ssl.qhimgs1.com 上可达且清晰（~1080px），首选。
  2) Bing 图片搜索 cn.bing.com/images/search —— 部分查询会返回无关结果，
     作为兜底（用 Bing 缩略图 CDN，800x500）。

质量控制：
  - 相关性：标题含景点名/核心词/城市名者优先；
  - 来源：优先非图库站（图库站多有半透明水印），图库图为次选并裁掉底部水印带；
  - 校验：尺寸 / 长宽比 / 非纯色 / 同城两两可区分（md5 + dHash）。

输出：images/ph-<slug>-<i>.jpg 与 photo_map.json（城市 -> {景点名: 相对路径}）。

用法：
  python scripts/fetch_photos.py --cities 烟台 --force   # 单城试跑
  python scripts/fetch_photos.py --limit-cities 5        # 只跑前 5 城
  python scripts/fetch_photos.py                         # 全量
  python scripts/fetch_photos.py --dry                   # 只搜不下，打印选图标题
"""
import argparse
import glob
import hashlib
import html as htmlmod
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import quote, urlparse

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "images")
SITE_TPL = os.path.join(ROOT, "scripts", "site_template.html")
CACHE = os.path.join(ROOT, ".cache", "ph")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

OUT_W = 640            # 输出最大宽度
QUALITY = 78
MIN_W, MIN_H = 380, 220
MAX_TRY = 8
SLEEP = 0.5
DHASH_MIN = 8
STOCK_CROP = 0.09      # 图库图裁掉底部比例（去水印带）

# 图库 / 素材站（多半带水印），优先级最低
STOCK = ("tuchong", "nipic", "699pic", "veer", "51yuansu", "zcool", "huitu",
         "sccnn", "photophoto", "gaoding", "aigei", "tupian114", "58pic",
         "16pic", "bigstock", "shutterstock", "gettyimages", "dreamstime",
         "alamy", "istock", "huaban", "duitang", "zcool", "vcg", "zhitu",
         "qiantucdn", "ooopic", "51yuansu", "thpic")


# ---------------------------------------------------------------- 基础工具
def curl(url, out=None, referer=None, timeout=25):
    cmd = ["curl", "-sL", "-m", str(timeout), "-A", UA]
    if referer:
        cmd += ["-e", referer]
    cmd += ["-H", "Accept-Language: zh-CN,zh;q=0.9"]
    if out:
        cmd += ["-o", out, "-w", "%{http_code}"]
        r = subprocess.run(cmd + [url], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip()
    r = subprocess.run(cmd + [url], capture_output=True)
    return r.stdout


def cache_path(key):
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, hashlib.md5(key.encode("utf-8")).hexdigest()[:16] + ".txt")


def cached(key, force, producer):
    fp = cache_path(key)
    if os.path.exists(fp) and not force and os.path.getsize(fp) > 10:
        try:
            return json.load(open(fp, encoding="utf-8"))
        except Exception:
            pass
    data = producer()
    try:
        json.dump(data, open(fp, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass
    return data


def slug_of_city():
    src = open(SITE_TPL, encoding="utf-8").read()
    m = re.search(r"const CITY_IMG\s*=\s*\{(.*?)\};", src, re.S)
    if not m:
        return {}
    return {c: s for c, s in re.findall(r"'([^']+)'\s*:\s*'images/pop-([^']+)\.jpg'", m.group(1))}


def targets():
    """需要配图的 (城市 -> [景点名...])，顺序：主站 3 个 -> 行程追加去重。"""
    out = {}
    a = json.load(open(os.path.join(ROOT, "attractions.json"), encoding="utf-8"))
    for city, v in a.items():
        out.setdefault(city, [])
        for s in v.get("spots") or []:
            if s.get("n") and s["n"] not in out[city]:
                out[city].append(s["n"])
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "attractions", "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        key = os.path.splitext(os.path.basename(f))[0]
        out.setdefault(key, [])
        for s in d.get("spots") or []:
            if s.get("n") and s["n"] not in out[key]:
                out[key].append(s["n"])
    return out


def domain(u):
    try:
        return urlparse(u).netloc.lower()
    except Exception:
        return ""


def is_stock(site):
    s = (site or "").lower()
    return any(k in s for k in STOCK)


# ---------------------------------------------------------------- 360 图片搜索
def so_search(query, force=False):
    def page(pn):
        u = "https://image.so.com/j?q=%s&pn=%d&rn=30&src=srp" % (quote(query, safe=""), pn)
        raw = curl(u, referer="https://image.so.com/")
        try:
            d = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            return []
        out = []
        for it in (d.get("list") or []):
            urls = []
            for k in ("thumb", "thumb_bak", "_thumb", "img", "https"):
                v = it.get(k)
                if v and v.startswith("http"):
                    urls.append(v)
            if not urls:
                continue
            try:
                w, h = int(it.get("width") or 0), int(it.get("height") or 0)
            except Exception:
                w = h = 0
            out.append({"t": (it.get("title") or ""), "urls": urls,
                        "w": w, "h": h, "site": (it.get("site") or "")})
        return out

    def pro():
        out = page(0)
        if len(out) < 6:
            out += page(30)
        return out

    return cached("so:" + query, force, pro)


# ---------------------------------------------------------------- Bing 兜底
def bing_search(query, force=False):
    def pro():
        u = ("https://cn.bing.com/images/search?q=" + quote(query, safe="") +
             "&form=HDRSC2&first=1&count=35")
        text = curl(u).decode("utf-8", "replace")
        out = []
        for m in re.finditer(r'm="(\{[^"<>]*\})"', text):
            try:
                d = json.loads(htmlmod.unescape(m.group(1)))
            except Exception:
                continue
            urls = []
            if d.get("turl"):
                urls.append(d["turl"].replace("&amp;", "&") + "&w=800&h=500&c=7")
            if d.get("murl"):
                urls.append(d["murl"].replace("&amp;", "&"))
            if urls:
                purl = d.get("purl", "")
                out.append({"t": (d.get("t") or "") + " " + purl, "urls": urls,
                            "w": 0, "h": 0, "site": domain(purl) or domain(urls[-1])})
        return out

    return cached("bing:" + query, force, pro)


def relevance(cand, name, city):
    t = (cand.get("t") or "")
    s = 0
    if name and name in t:
        s += 4
    core = re.sub(r"(风景区|旅游区|自然保护|博物馆|博物院|纪念馆|遗址|古镇|古城|"
                  r"步行街|广场|公园|大教堂|文化区|大学|基地|大坝|大桥|国家公园)$", "", name)
    if len(core) >= 2 and core != name and core in t:
        s += 2
    if city and city in t:
        s += 1
    return s


def gather(name, city, force):
    q = "%s %s" % (city, name)
    cs = so_search(q, force)
    if len([c for c in cs if relevance(c, name, city) > 0]) < 3:
        cs = cs + bing_search(q, force)
    # 排序：非图库优先 -> 相关性高优先
    cs.sort(key=lambda c: (is_stock(c.get("site")), -relevance(c, name, city)))
    return cs


# ---------------------------------------------------------------- 下载 / 校验
def fetch_image(cand, dst):
    for u in cand["urls"]:
        ref = "https://image.so.com/" if "qhimg" in u else "https://cn.bing.com/"
        code = curl(u, out=dst, referer=ref)
        if code == "200" and os.path.exists(dst) and os.path.getsize(dst) > 6000:
            return True
        if os.path.exists(dst):
            os.remove(dst)
    return False


def valid_image(path):
    try:
        im = Image.open(path)
        im.load()
    except Exception:
        return False, None
    w, h = im.size
    if w < MIN_W or h < MIN_H:
        return False, None
    if not (0.55 <= w / h <= 3.0):
        return False, None
    px = im.convert("L").resize((32, 32)).tobytes()
    mean = sum(px) / len(px)
    var = sum((p - mean) ** 2 for p in px) / len(px)
    if var < 120:                        # 近乎纯色（图标 / 占位图）
        return False, None
    return True, im


def save_jpeg(im, dst, crop_bottom=0.0):
    if crop_bottom > 0:
        n = int(im.height * (1 - crop_bottom))
        im = im.crop((0, 0, im.width, max(1, n)))
    if im.width > OUT_W:
        im = im.resize((OUT_W, max(1, round(im.height * OUT_W / im.width))), Image.LANCZOS)
    im.convert("RGB").save(dst, "JPEG", quality=QUALITY, optimize=True, progressive=True)


def dhash(im, n=8):
    px = im.convert("L").resize((n + 1, n), Image.NEAREST).tobytes()
    bits = 0
    for r in range(n):
        for c in range(n):
            bits = (bits << 1) | (1 if px[r * (n + 1) + c] < px[r * (n + 1) + c + 1] else 0)
    return bits


def ham(a, b):
    return bin(a ^ b).count("1")


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cities", nargs="*")
    ap.add_argument("--limit-cities", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    slugs = slug_of_city()
    tgt = targets()
    cities = args.cities or list(tgt.keys())
    if args.limit_cities:
        cities = cities[:args.limit_cities]

    pm_path = os.path.join(ROOT, "photo_map.json")
    photo_map = json.load(open(pm_path, encoding="utf-8")) if os.path.exists(pm_path) else {}

    # 清理上次遗留的临时文件
    for t in glob.glob(os.path.join(IMG, "ph-*.tmp")):
        try:
            os.remove(t)
        except Exception:
            pass

    ok = fail = 0
    fail_list = []

    def save_map():
        try:
            json.dump(photo_map, open(pm_path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        except Exception:
            pass

    for city in cities:
        try:
            if city not in tgt:
                print("!! 跳过未知城市", city)
                continue
            slug = slugs.get(city)
            if not slug:
                print("!! 无 slug，跳过", city)
                continue
            names = tgt[city]
            photo_map.setdefault(city, {})
            seen_hash, seen_md5 = [], set()
            print("\n== %s（%s）%d 个景点 ==" % (city, slug, len(names)))
            for i, name in enumerate(names):
                try:
                    dst = os.path.join(IMG, "ph-%s-%d.jpg" % (slug, i + 1))
                    rel = "images/ph-%s-%d.jpg" % (slug, i + 1)
                    if os.path.exists(dst) and not args.force:
                        try:
                            im = Image.open(dst)
                            seen_md5.add(hashlib.md5(open(dst, "rb").read()).hexdigest())
                            seen_hash.append(dhash(im))
                            photo_map[city][name] = rel
                            print("  [缓存] %-16s %s" % (name, rel))
                            ok += 1
                            continue
                        except Exception:
                            pass
                    cands = gather(name, city, args.force)
                    if args.dry:
                        print("  [dry] %-16s 候选=%d 前3=%s" %
                              (name, len(cands),
                               [(c["site"][:14], c["t"][:18]) for c in cands[:3]]))
                        continue
                    picked = None
                    for cand in cands[:MAX_TRY]:
                        tmp = dst + ".tmp"
                        try:
                            if not fetch_image(cand, tmp):
                                continue
                            good, im = valid_image(tmp)
                            if not good:
                                try:
                                    os.remove(tmp)
                                except Exception:
                                    pass
                                continue
                            md5 = hashlib.md5(open(tmp, "rb").read()).hexdigest()
                            dh = dhash(im)
                            if md5 in seen_md5 or any(ham(dh, h) < DHASH_MIN for h in seen_hash):
                                try:
                                    os.remove(tmp)
                                except Exception:
                                    pass
                                continue
                            crop = STOCK_CROP if is_stock(cand.get("site")) else 0.0
                            save_jpeg(im, dst, crop)
                            try:
                                os.remove(tmp)
                            except Exception:
                                pass
                            picked = cand
                            seen_md5.add(hashlib.md5(open(dst, "rb").read()).hexdigest())
                            seen_hash.append(dhash(Image.open(dst)))
                            break
                        except Exception as e:
                            print("    [异常] %s: %s" % (name, e))
                            try:
                                if os.path.exists(tmp):
                                    os.remove(tmp)
                            except Exception:
                                pass
                            continue
                    if picked:
                        photo_map[city][name] = rel
                        print("  [ok]   %-16s %s  %-18s %r" %
                              (name, rel, picked["site"][:18], picked["t"][:28]))
                        ok += 1
                    else:
                        print("  [FAIL] %-16s 未取到合格图" % name)
                        fail += 1
                        fail_list.append(city + "/" + name)
                    time.sleep(SLEEP)
                except Exception as e:
                    print("    [景点异常] %s/%s: %s" % (city, name, e))
                    fail += 1
                    fail_list.append(city + "/" + name)
            # 每城结束即落盘，避免中途崩溃丢进度
            save_map()
            print("  (已保存 %s 到 photo_map)" % city)
        except Exception as e:
            print("!! 城市处理异常 %s: %s" % (city, e))

    save_map()
    print("\n完成：成功 %d / 失败 %d" % (ok, fail))
    if fail_list:
        print("失败清单：", "、".join(fail_list))
    return 0


if __name__ == "__main__":
    sys.exit(main())
