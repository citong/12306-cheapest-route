#!/usr/bin/env python3
"""
健康自检：确认 12306 这条链路还活着，没被改版搞挂。

  python scripts/health_check.py

查三件事：
  1) 本地 12306-mcp 服务在不在（start.bat 有没有启动）
  2) 一个固定区间能不能查到车次（查不到 = 接口多半改版了）
  3) 最低价相对上次有没有突变（>30% 提示复核，可能是调图或浮动票价）

退出码 0=正常 / 1=警告 / 2=不可用
"""
import datetime as dt
import json
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
HIST = os.path.join(ROOT, "scripts", "health_history.json")
MCP_HOST, MCP_PORT = "127.0.0.1", 8080
PROBE_FROM, PROBE_TO = "新乡", "郑州"     # 短途、车次密集，适合当探针


def port_open(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def query_once():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import export_data as ed
    date = (dt.date.today() + dt.timedelta(days=3)).isoformat()
    cmd = [PY, os.path.join(ROOT, "scripts", "train_query.py"),
           PROBE_FROM, PROBE_TO, "--date", date]
    env = dict(os.environ)
    env.setdefault("NO_PROXY", "localhost,127.0.0.1")
    env.setdefault("no_proxy", "localhost,127.0.0.1")
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=180)
    out = (p.stdout or "").strip()
    if not out:
        raise RuntimeError((p.stderr or "无输出")[-400:])
    res = json.loads(out)
    trains = []
    for blk in (res.get("trains") or []):
        trains.extend(ed.parse_trains(blk))
    prices = [t["price"] for t in trains if t.get("price")]
    return {
        "date": date,
        "trains": len(trains),
        "min_price": min(prices) if prices else None,
        "query_type": res.get("query_type"),   # 有值就说明接口还在正常应答
    }


def query(retries=3):
    """12306 偶尔会限流导致单次查询空手而归，重试几次再下结论，
    否则会把一次限流误判成「接口改版」。"""
    last = None
    for i in range(retries):
        try:
            r = query_once()
            if r["trains"]:
                return r
            last = r
        except Exception as e:
            last = e
        if i < retries - 1:
            print(f"   第 {i + 1} 次没拿到车次，等 8 秒重试…", flush=True)
            time.sleep(8)
    if isinstance(last, Exception):
        raise last
    return last or {"date": "", "trains": 0, "min_price": None, "query_type": None}


def load_hist():
    if os.path.isfile(HIST):
        try:
            with open(HIST, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def main():
    print("=" * 56)
    print(f"12306 链路自检 · {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 56)

    code = 0
    if not port_open(MCP_HOST, MCP_PORT):
        print(f"\n✗ 本地 12306 服务未启动（{MCP_HOST}:{MCP_PORT} 连不上）")
        print("  请在项目目录双击 start.bat，等它提示「已启动」再重试。")
        return 2
    print(f"\n✓ 本地 12306 服务在跑（{MCP_HOST}:{MCP_PORT}）")

    try:
        r = query()
    except Exception as e:
        print(f"\n✗ 查询 {PROBE_FROM} → {PROBE_TO} 失败：{e}")
        print("  多半是 12306 接口改版或本地 mcp 版本过旧。")
        print("  试试更新：npm install -g 12306-mcp@latest")
        return 2

    print(f"✓ 查询 {PROBE_FROM} → {PROBE_TO}（{r['date']}）："
          f"{r['trains']} 个车次，最低 {r['min_price']} 元")
    if not r["trains"]:
        # 接口还能正常应答（有 query_type），只是没给车次 —— 这不是改版，
        # 通常是限流 / 维护时段 / 未放票。别当成故障吓人，但要说清楚。
        print(f"\n⚠ 连查 3 次没拿到 {PROBE_FROM} → {PROBE_TO} 的车次"
              f"（接口应答类型：{r.get('query_type')}）。")
        print("  接口本身还在正常应答，多半是：")
        print("   · 12306 限流（刚查过很多次就会这样），隔几分钟再试")
        print("   · 系统维护时段（每天 23:00-06:00 查询经常受限）")
        print("   · 该日期尚未放票，换近一点的日期确认")
        print("  如果换时间、换日期都查不到，再考虑接口改版：npm install -g 12306-mcp@latest")
        return 1

    hist = load_hist()
    prev = hist.get("min_price")
    if prev and r["min_price"]:
        delta = abs(r["min_price"] - prev) / prev
        if delta > 0.3:
            print(f"\n⚠ 最低价较上次（{prev} 元）变动 {delta * 100:.0f}%，超过 30%")
            print("  可能是调图或浮动票价，也可能解析出了错。建议打开页面核对一趟车次。")
            code = 1
        else:
            print(f"✓ 价格与上次（{prev} 元）基本一致")
    else:
        print("（首次运行，没有历史价格可比）")

    hist.update({"min_price": r["min_price"], "trains": r["trains"],
                 "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds")})
    with open(HIST, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

    print("\n✓ 链路正常" if code == 0 else "\n⚠ 链路可用，但有上述告警")
    return code


if __name__ == "__main__":
    sys.exit(main())
