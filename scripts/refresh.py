#!/usr/bin/env python3
"""
一键刷新：把数据拉到最新并重建页面。

  python scripts/refresh.py              # 全量：车站表 + 省份 + 路线数据 + 页面
  python scripts/refresh.py --light      # 轻量：只更新车站表 + 省份 + 重建页面（几秒）

全量模式需要本地 12306 服务在跑（双击 start.bat），轻量模式不需要。
建议：每月跑一次全量，12306 调图后（1/4/7/10 月）跑一次。
"""
import argparse
import datetime as dt
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def run(rel, args=(), label="", must=False):
    cmd = [PY, os.path.join(ROOT, "scripts", rel)] + list(args)
    print(f"\n▶ {label or rel}", flush=True)
    t = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    out = (p.stdout or "").strip()
    if out:
        print("   " + out.replace("\n", "\n   "))
    if p.returncode != 0:
        err = (p.stderr or "").strip()[-400:]
        print(f"   ✗ 失败（退出码 {p.returncode}）")
        if err:
            print("   " + err.replace("\n", "\n   "))
        if must:
            print("\n中断：后续步骤依赖它。")
            sys.exit(1)
        return False
    print(f"   ✓ 完成（{time.time() - t:.1f}s）")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--light", action="store_true",
                    help="只更新车站表与省份映射，不查 12306（不需要本地服务）")
    ap.add_argument("--date", default=None, help="出发日期，默认 3 天后")
    ap.add_argument("--from", dest="frm", default="新乡")
    ap.add_argument("--to", dest="to", default="昆明")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 56)
    print(f"开始刷新 · {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 56)

    ok = True
    # 车站表来自 12306 官方 station_name.js，新线开通后这里最先体现
    ok &= run("gen_stations.py", label="更新车站表（12306 官方）")
    # 省份映射依赖 npm 镜像，拿不到就沿用旧文件，不影响其它步骤
    ok &= run("gen_prov.py", label="更新省份映射（行政区划数据）")

    if not args.light:
        date = args.date or (dt.date.today() + dt.timedelta(days=3)).isoformat()
        ok &= run("export_data.py", [date, "--from", args.frm, "--to", args.to],
                  label=f"重新查询 {args.frm} → {args.to}（{date} 出发）")
    else:
        print("\n（轻量模式：跳过 12306 路线查询，data.json 保持原样）")

    run("render_site.py", label="重建 index.html")
    run("render_map.py", label="重建 map.html")

    print("\n" + "=" * 56)
    print(f"{'✓ 全部完成' if ok else '⚠ 完成，但有步骤失败'} · 耗时 {time.time() - t0:.0f}s")
    print("=" * 56)
    if not ok:
        print("提示：全量模式需要先双击 start.bat 启动本地 12306 服务。")


if __name__ == "__main__":
    main()
