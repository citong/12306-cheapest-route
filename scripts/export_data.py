#!/usr/bin/env python3
"""
生成网页用的 data.json。

前置条件：本地 12306-mcp 服务已启动（默认 http://127.0.0.1:8080/sse）。
  npx -y 12306-mcp --host localhost --port 8080
  # 或离线：npm install 12306-mcp --registry=https://registry.npmmirror.com
  #         node node_modules/12306-mcp/build/index.js --host localhost --port 8080

用法：
  python scripts/export_data.py                 # 默认查 3 天后的 新乡→昆明
  python scripts/export_data.py 2026-10-05 --from 新乡 --to 昆明
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUERY = os.path.join(ROOT, "scripts", "train_query.py")
PYTHON = sys.executable

TRAIN_LINE = re.compile(
    r'([GDCZTK]\d+)\s+.*?(\d{2}:\d{2})\s*->\s*(\d{2}:\d{2})\s+历时：(\d{2}:\d{2})'
)
SEAT_LINE = re.compile(r'-\s*([^:：]+)[:：]\s*(.*?)(\d+(?:\.\d+)?)\s*元')


def run_query(args):
    """调用 train_query.py，返回解析后的 JSON。"""
    env = dict(os.environ)
    env.setdefault("NO_PROXY", "localhost,127.0.0.1")
    env.setdefault("no_proxy", "localhost,127.0.0.1")
    proc = subprocess.run(
        [PYTHON, QUERY] + args,
        capture_output=True, text=True, encoding="utf-8",
        env=env, cwd=ROOT, timeout=1800,
    )
    out = (proc.stdout or "").strip()
    if not out:
        raise RuntimeError("查询无输出: " + (proc.stderr or "")[-800:])
    return json.loads(out)


def parse_seats(text):
    seats = []
    for line in (text or "").split("\n"):
        m = SEAT_LINE.search(line)
        if not m:
            continue
        price = float(m.group(3))
        if price <= 0:
            continue  # 12306 对无票额区间返回 0 元，视为票价未知
        status = m.group(2).strip()
        seats.append({
            "seat": m.group(1).strip(),
            "status": status,
            "price": price,
            "available": ("有票" in status) or ("剩余" in status),
        })
    return seats


def parse_trains(block):
    """把一段文本块切成若干车次（直达块 1 个，官方中转块 2 个）。"""
    if not block:
        return []
    matches = list(TRAIN_LINE.finditer(block))
    if not matches:
        return []
    trains = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        body = block[m.start():end]
        seats = parse_seats(body)
        if not seats:
            trains.append({
                "code": m.group(1), "depart": m.group(2), "arrive": m.group(3),
                "duration": m.group(4), "price": None, "seat": None, "available": None,
                "seats": [],
            })
            continue
        avail = [s for s in seats if s["available"]]
        best = min(avail or seats, key=lambda s: s["price"])
        trains.append({
            "code": m.group(1), "depart": m.group(2), "arrive": m.group(3),
            "duration": m.group(4), "price": best["price"], "seat": best["seat"],
            "available": bool(avail), "seats": seats,
        })
    return trains


def build_leg(leg):
    """把 auto_plan 的一段转换成网页所需结构。"""
    details = leg.get("details") or []
    trains = []
    for blk in details:
        trains.extend(parse_trains(blk))
    # 同一车次可能重复出现，去重保留第一个
    seen, uniq = set(), []
    for t in trains:
        key = (t["code"], t["depart"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(t)
    if leg.get("type") != "interline":
        uniq.sort(key=lambda t: (t["price"] is None, t["price"] or 0))
    return {
        "from": leg.get("from"),
        "to": leg.get("to"),
        "type": leg.get("type"),
        "price": leg.get("price"),
        "available": leg.get("available"),
        "trains": uniq[:6],
    }


def build_route(route, idx):
    legs = [build_leg(l) for l in route.get("legs", [])]
    path = [legs[0]["from"]] + [l["to"] for l in legs] if legs else []
    ride_min = 0
    for l in legs:
        for t in l["trains"]:
            m = re.match(r"^(\d+):(\d+)$", t.get("duration") or "")
            if m:
                ride_min += int(m.group(1)) * 60 + int(m.group(2))
                break
    return {
        "id": idx,
        "path": path,
        "via": path[1:-1],
        "transfers": route.get("transfers", max(len(legs) - 1, 0)),
        "total_price": route.get("total_price"),
        "all_available": bool(route.get("all_available")),
        "ride_minutes": ride_min,
        "legs": legs,
    }


def main():
    today = dt.date.today()
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", default=(today + dt.timedelta(days=3)).isoformat())
    ap.add_argument("--from", dest="frm", default="新乡")
    ap.add_argument("--to", dest="to", default="昆明")
    ap.add_argument("--max-hops", dest="hops", type=int, default=4)
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()

    # 直达查询放在最前面：多跳规划会打上千次 12306 接口，容易被限流，
    # 之后再查直达往往只剩空结果，导致价格基准丢失。
    print("→ 查询直达车次（含高铁，用于对比）…", flush=True)
    direct = {}
    for attempt in range(3):
        try:
            d = run_query([args.frm, args.to, "--date", args.date])
        except Exception as e:
            print("   直达查询失败:", e, flush=True)
            d = {}
        if (d.get("trains") or []):
            direct = d
            break
        print(f"   直达无结果，{attempt + 1}/3 重试…", flush=True)
    if not direct:
        print("   警告：直达查询始终为空，价格基准将缺失", flush=True)

    print(f"→ 多跳规划 {args.frm} → {args.to} ({args.date}) …", flush=True)
    plan = run_query([args.frm, args.to, "--auto-plan", "--train-type", "ZTK",
                      "--max-hops", str(args.hops), "--top", str(args.top),
                      "--date", args.date, "--refresh"])
    if "error" in plan:
        raise RuntimeError("规划失败: " + str(plan["error"]))

    direct_trains = []
    for blk in (direct.get("trains") or [])[:10]:
        direct_trains.extend(parse_trains(blk))

    routes = [build_route(r, i) for i, r in enumerate(plan.get("routes", []), 1)]
    priced = [r for r in routes if r["total_price"] is not None]
    best = priced[0] if priced else (routes[0] if routes else None)

    hs_prices = [t["price"] for t in direct_trains if t.get("price")]
    data = {
        "meta": {
            "from": args.frm,
            "to": args.to,
            "date": args.date,
            "train_types": plan.get("train_types"),
            "max_hops": args.hops,
            "total_routes": plan.get("total_routes", len(routes)),
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        },
        "best": best,
        "routes": routes,
        "direct": {
            "trains": direct_trains,
            "min_price": min(hs_prices) if hs_prices else None,
        },
    }

    if (direct.get("trains") is None) or data["direct"]["min_price"] is None:
        print("   提示：直达基准缺失，保留 data.json 中已有的直达数据", flush=True)
        try:
            with open(os.path.join(ROOT, "data.json"), encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = {}
        if prev.get("direct", {}).get("min_price") is not None:
            data["direct"] = prev["direct"]

    out = os.path.join(ROOT, "data.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✓ 已写入 {out}")
    print(f"  路线 {len(routes)} 条；最便宜 "
          f"{best['total_price'] if best else '?'} 元；"
          f"直达最低 {data['direct']['min_price']} 元")

    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import render_site
    render_site.main()


if __name__ == "__main__":
    main()
