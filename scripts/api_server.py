#!/usr/bin/env python3
"""
本地查询服务：给网页提供 12306 实时查询 API（CORS + SSE 进度），并顺带托管静态页面。

依赖：本地 12306-mcp 服务已在 127.0.0.1:8080 运行（start.bat 会自动拉起）。

用法：
  python scripts/api_server.py [--port 8787]
然后打开 http://127.0.0.1:8787/
"""
import argparse
import asyncio
import collections
import json
import mimetypes
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import train_query as tq          # noqa: E402
import export_data as ed          # noqa: E402
from mcp import ClientSession     # noqa: E402
from mcp.client.sse import sse_client  # noqa: E402

MCP_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8080/sse")
MIN_TRANSFER_GAP = 30             # 换乘最少预留分钟
CONCURRENCY = 2                   # 并发探测区间数（实测 3~4 会被 12306 限流掉结果）
PROBE_TIMEOUT = 8                 # 单个区间查询超时（秒），12306 限流时会挂起
TOTAL_BUDGET = 240                # 整个查询的总时间预算（秒），到点就收尾
BEAM = 8                          # 每层保留的候选枢纽数（分层 beam 搜索，控制请求量）
MAX_CONSEC_FAIL = 24              # 连续多少个区间无响应就判定被限流，提前收尾

# 全国性主要枢纽。请求数与枢纽数的平方成正比，且容易触发 12306 限流，
# 因此默认只用这批核心枢纽（约 20 个），而不是 ZTK_HUBS 的全部 34 个。
CORE_HUBS = {
    "郑州": "ZZF", "武汉": "WHN", "长沙": "CSQ", "怀化": "HHQ",
    "贵阳": "GIW", "昆明": "KMM", "成都": "CDW", "重庆": "CQW",
    "西安": "XAY", "北京西": "BXP", "石家庄": "SJP", "广州": "GZQ",
    "南宁": "NNZ", "南昌": "NCG", "合肥": "HFH", "襄阳": "XFN",
    "株洲": "ZZQ", "六盘水": "UMW", "曲靖": "QJM", "柳州": "LZZ",
    "洛阳": "LYF", "信阳": "XUN",
}


def hm(s):
    """'HH:MM' -> 分钟；失败返回 None。"""
    try:
        h, m = str(s).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def plan_trains(legs, gap=MIN_TRANSFER_GAP):
    """
    为一条路线挑出「实际能坐上」的具体车次组合。

    逐段贪心：在不早于上一段到达 + gap 的前提下，选到达最早的一班车。
    返回 (chosen, feasible)；chosen 为每段选中的车次（含绝对分钟），
    feasible=False 表示某一段接不上（只能按票价估算，不能照着买）。
    """
    # 官方中转段（interline）的文本块里是「多段车次拼起来的方案」
    # （第一段票价只覆盖其中一小截），不能当成直达车次来编排，否则会把总价算成几十块。
    if any(leg.get("type") == "interline" for leg in legs):
        return [], False

    prev_arr = None
    chosen = []
    for leg in legs:
        best = None
        for tr in leg.get("trains", []):
            d, a = hm(tr.get("depart")), hm(tr.get("arrive"))
            if d is None or a is None:
                continue
            # 到达时间必须以「运行时长」推算，不能用 arrive 的钟点。
            # 像 31:19 这种超过 24 小时的车次，按钟点算会少算一整天。
            run = hm(tr.get("duration"))
            if run is None:
                run = (a - d) % 1440
            if prev_arr is None:
                cand = (d + run, d, tr)
            else:
                cand = None
                for k in range(0, 3):          # 允许最多等 2 天
                    dd = d + k * 1440
                    if dd >= prev_arr + gap:
                        cand = (dd + run, dd, tr)
                        break
                if cand is None:
                    continue
            if best is None or cand[0] < best[0]:
                best = cand
        if best is None:
            return chosen, False
        arr, dep, tr = best
        item = dict(tr)
        item["_dep"] = dep
        item["_arr"] = arr
        chosen.append(item)
        prev_arr = arr
    return chosen, len(chosen) == len(legs)


def enrich_route(route, idx):
    """给路线补上：具体车次编排、总在途、行程跨度、是否可衔接。"""
    legs = route.get("legs", [])
    chosen, feasible = plan_trains(legs)
    ride = 0
    for i, item in enumerate(chosen):
        leg_tr = legs[i]
        dur = hm(item.get("duration"))
        if dur is None:
            d, a = hm(item.get("depart")), hm(item.get("arrive"))
            if d is not None and a is not None:
                dur = (a - d) % 1440
        ride += dur or 0
        item["leg_from"] = leg_tr.get("from")
        item["leg_to"] = leg_tr.get("to")
    span = (chosen[-1]["_arr"] - chosen[0]["_dep"]) if chosen else None
    wait = (span - ride) if (span is not None and chosen) else None
    out = dict(route)
    out["id"] = idx
    out["chosen"] = chosen
    out["time_feasible"] = feasible
    out["ride_minutes"] = ride or None
    out["span_minutes"] = span if feasible else None
    out["wait_minutes"] = wait if feasible else None
    out["plan_price"] = (
        round(sum(c.get("price") or 0 for c in chosen), 2)
        if feasible and all(c.get("price") for c in chosen) else None
    )
    out["plan_available"] = feasible and all(c.get("available") for c in chosen)
    return out


async def run_query(frm, to, date, types, hops, top, emit):
    async with sse_client(url=MCP_URL) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            emit("progress", {"phase": "init", "msg": "已连接 12306 服务"})

            from_code = await tq.get_station_code(s, frm)
            to_code = await tq.get_station_code(s, to)
            if not from_code or not to_code:
                emit("error", {"msg": f"无法识别车站：{frm} / {to}"})
                return
            emit("progress", {"phase": "init", "msg": f"{frm}({from_code}) → {to}({to_code})",
                              "from_code": from_code, "to_code": to_code})

            # 1) 直达（不限车型）作为价格基准
            emit("progress", {"phase": "direct", "msg": "查询直达车次…"})
            direct_trains = []
            try:
                raw = await tq.query_direct(s, from_code, to_code, date, None)
                for blk in tq.parse_direct_blocks(raw)[:12]:
                    direct_trains.extend(ed.parse_trains(blk))
            except Exception as e:
                emit("progress", {"phase": "direct", "msg": f"直达查询失败：{e}"})
            d_prices = [t["price"] for t in direct_trains if t.get("price")]
            direct = {"trains": direct_trains,
                      "min_price": min(d_prices) if d_prices else None}
            emit("direct", {"trains": direct_trains, "min_price": direct["min_price"],
                            "from": frm, "to": to})

            # 2) 分层 beam 搜索：段内只查直达，换乘由搜索组合。
            #    每层只保留累计票价最低的 BEAM 个枢纽继续展开，
            #    把请求量从 O(hubs²) 压到可控范围，同时不容易触发 12306 限流。
            hubs = dict(CORE_HUBS)
            hubs[frm] = from_code
            hubs[to] = to_code
            code_to_name = {v: k for k, v in hubs.items()}
            visited = {from_code}
            found = []
            scanned = 0
            total_work = len(hubs) * (1 + BEAM * hops)
            sem = asyncio.Semaphore(CONCURRENCY)
            deadline = time.time() + min(TOTAL_BUDGET, 60 + 45 * hops)
            stopped = False

            def build_legs(steps):
                return [ed.build_leg({
                    "from": st["from"], "to": st["to"], "type": st["type"],
                    "price": st["price"], "available": st["available"],
                    "details": st["details"]}) for st in steps]

            def mk_step(cur_code, hub_name, hub_code, kind, details):
                price, avail = tq.summarise_leg_price(details, kind)
                return {
                    "from": code_to_name.get(cur_code, cur_code),
                    "to": hub_name,
                    "from_code": cur_code,
                    "to_code": hub_code,
                    "type": kind,
                    "details": details,
                    "price": price,
                    "available": avail,
                }

            async def probe(cur_code, hub_name, hub_code):
                """
                探测 cur -> hub 是否走得通：
                  1) 先查本地缓存图（0 请求，命中就不打扰 12306）
                  2) 再查直达
                  3) 最后查 12306 官方中转换乘方案
                每一步都带超时，12306 限流时不会把整个查询拖死。
                """
                if hub_code == cur_code:
                    return None
                async with sem:
                    # 1) 缓存
                    try:
                        edges = tq.cache_graph.get_edges(cur_code, hub_code, date, types)
                    except Exception:
                        edges = None
                    if edges:
                        blk = tq.format_cached_edge(edges[0], cur_code, hub_code)
                        return mk_step(cur_code, hub_name, hub_code, "direct", [blk])

                    # 2) 直达
                    try:
                        raw = await asyncio.wait_for(
                            tq.query_direct(s, cur_code, hub_code, date, types),
                            timeout=PROBE_TIMEOUT)
                    except Exception:
                        raw = None
                    blocks = [b for b in tq.parse_direct_blocks(raw)
                              if tq.filter_by_train_types(b, types)] if raw else []
                    if blocks:
                        for b in blocks[:3]:
                            tq.extract_and_cache_edges(b, cur_code, hub_code, date, types)
                        return mk_step(cur_code, hub_name, hub_code, "direct", blocks[:5])

                    # 3) 官方中转换乘
                    try:
                        raw2 = await asyncio.wait_for(
                            tq.query_interline(s, cur_code, hub_code, date, types),
                            timeout=PROBE_TIMEOUT)
                    except Exception:
                        raw2 = None
                    if raw2 and "Error:" not in raw2:
                        sblocks = [b for b in tq.parse_transfer_blocks(raw2)
                                   if not tq.is_same_train_transfer(b)
                                   and tq.filter_by_train_types(b, types)]
                        if sblocks:
                            return mk_step(cur_code, hub_name, hub_code,
                                           "interline", sblocks[:3])
                return None

            layer = [(from_code, [], 0.0)]
            consec_fail = 0
            throttled = False
            for depth in range(hops):
                if not layer or time.time() > deadline or throttled:
                    if time.time() > deadline:
                        stopped = True
                    break
                cands = []
                for cur_code, path, cost in layer:
                    tasks = [(hn, hc, asyncio.create_task(probe(cur_code, hn, hc)))
                             for hn, hc in hubs.items() if hc != cur_code]
                    for hn, hc, tk in tasks:
                        remain = deadline - time.time()
                        if remain <= 0:
                            stopped = True
                            tk.cancel()
                            continue
                        # 每个探测都受「剩余预算」约束，否则会卡在一批慢请求里出不来
                        try:
                            step = await asyncio.wait_for(tk, timeout=min(remain, PROBE_TIMEOUT))
                        except Exception:
                            step = None
                        scanned += 1
                        if scanned % 10 == 0:
                            emit("progress", {
                                "phase": "bfs", "scanned": scanned, "total": total_work,
                                "routes": len(found), "depth": depth + 1,
                                "msg": f"第 {depth + 1} 层：已探测 {scanned} 个区间，"
                                       f"找到 {len(found)} 条路线",
                            })
                        if not step:
                            consec_fail += 1
                            if consec_fail >= MAX_CONSEC_FAIL:
                                throttled = True
                                emit("progress", {
                                    "phase": "bfs", "scanned": scanned, "total": total_work,
                                    "routes": len(found),
                                    "msg": f"12306 连续 {consec_fail} 个区间无响应"
                                           f"（多半是限流），提前收尾"})
                                break
                            continue
                        consec_fail = 0
                        if hc == to_code:
                            found.append(path + [step])
                            legs = build_legs(path + [step])
                            prices = [l.get("price") for l in legs if l.get("price") is not None]
                            emit("route", {
                                "path": [legs[0]["from"]] + [l["to"] for l in legs],
                                "transfers": len(legs) - 1,
                                "total_price": round(sum(prices), 2) if len(prices) == len(legs) else None,
                                "all_available": all(l.get("available") for l in legs),
                                "legs": legs,
                            })
                        elif hc not in visited:
                            cands.append((hc, path + [step], cost + (step["price"] or 0)))
                # 下一层：去重后按累计票价取最便宜的 BEAM 个
                cands.sort(key=lambda x: x[2])
                nxt, seen = [], set()
                for hc, path, cost in cands:
                    if hc in seen or hc in visited:
                        continue
                    seen.add(hc)
                    visited.add(hc)
                    nxt.append((hc, path, cost))
                    if len(nxt) >= BEAM:
                        break
                layer = nxt

            # 3) 排序整理
            routes = []
            for i, legs_raw in enumerate(found, 1):
                legs = [ed.build_leg({
                    "from": st["from"], "to": st["to"], "type": st["type"],
                    "price": st["price"], "available": st["available"],
                    "details": st["details"]}) for st in legs_raw]
                prices = [l.get("price") for l in legs if l.get("price") is not None]
                routes.append({
                    "legs": legs,
                    "path": [legs[0]["from"]] + [l["to"] for l in legs],
                    "transfers": len(legs) - 1,
                    "total_price": round(sum(prices), 2) if len(prices) == len(legs) else None,
                    "all_available": all(l.get("available") for l in legs),
                })
            routes = [enrich_route(r, i) for i, r in enumerate(routes, 1)]
            routes.sort(key=lambda r: (
                0 if r.get("plan_available") else (1 if r.get("time_feasible") else 2),
                r.get("plan_price") or r.get("total_price") or float("inf"),
                r.get("transfers", 0),
            ))
            routes = routes[:top]
            for i, r in enumerate(routes, 1):
                r["id"] = i
            emit("result", {
                "meta": {
                    "from": frm, "to": to, "date": date,
                    "train_types": types, "max_hops": hops,
                    "total_routes": len(found),
                    "generated_at": __import__("datetime").datetime.now().astimezone()
                                    .isoformat(timespec="seconds"),
                    "scanned": scanned,
                    "truncated": stopped,
                    "throttled": throttled,
                    "live": True,
                },
                "direct": direct,
                "best": routes[0] if routes else None,
                "routes": routes,
            })


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, rel):
        path = os.path.normpath(os.path.join(ROOT, rel.lstrip("/")))
        if not path.startswith(ROOT) or not os.path.isfile(path):
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if path.endswith((".html", ".json", ".js", ".css")):
            ctype += "; charset=utf-8"
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        path = u.path

        if path == "/api/health":
            return self._json({"ok": True, "mcp": MCP_URL})

        if path == "/api/stations":
            kw = (q.get("q") or [""])[0].strip().lower()
            try:
                with open(os.path.join(ROOT, "stations.json"), encoding="utf-8") as f:
                    all_st = json.load(f)
            except Exception:
                return self._json([])
            if not kw:
                return self._json(all_st[:20])
            out = []
            for s in all_st:
                if kw in s["n"] or s["i"].startswith(kw) or s["p"].startswith(kw):
                    out.append(s)
                if len(out) >= 20:
                    break
            return self._json(out)

        if path == "/api/query":
            frm = (q.get("from") or [""])[0].strip()
            to = (q.get("to") or [""])[0].strip()
            date = (q.get("date") or [""])[0].strip()
            types = (q.get("types") or ["ZTK"])[0].strip() or None
            hops = int((q.get("hops") or ["4"])[0])
            top = int((q.get("top") or ["40"])[0])
            if not frm or not to or not date:
                return self._json({"error": "缺少 from/to/date"}, 400)

            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            def emit(event, data):
                try:
                    payload = ("event: %s\ndata: %s\n\n"
                               % (event, json.dumps(data, ensure_ascii=False)))
                    self.wfile.write(payload.encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass

            try:
                asyncio.run(run_query(frm, to, date, types, hops, top, emit))
            except Exception as e:
                emit("error", {"msg": f"{type(e).__name__}: {e}"})
            finally:
                try:
                    self.wfile.write(b"event: end\ndata: {}\n\n")
                    self.wfile.flush()
                except Exception:
                    pass
            return

        return self._file("/index.html" if path == "/" else path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"✓ 查询服务已启动： http://{args.host}:{args.port}/")
    print(f"  依赖 12306 服务： {MCP_URL}")
    print("  按 Ctrl+C 停止", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
