#!/usr/bin/env python3
"""
一键启动：拉起 12306 数据服务 + 本地查询服务，并打开网页。

双击 start.bat（Windows）或 ./start.sh（macOS/Linux）即可，
也可以直接 python scripts/launcher.py
"""
import os
import socket
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")

MCP_PORT = 8080
API_PORT = 8787

# 优先用已装好依赖的托管 venv / node
PY_CANDIDATES = [
    os.path.join(HOME, ".workbuddy/binaries/python/envs/default/Scripts/python.exe"),
    os.path.join(HOME, ".workbuddy/binaries/python/envs/default/bin/python"),
    sys.executable,
]
NODE_CANDIDATES = [
    os.path.join(HOME, ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"),
    os.path.join(HOME, ".workbuddy/binaries/node/versions/22.22.2-3/bin/node"),
    "node",
]
NODE_WORKSPACE = os.path.join(HOME, ".workbuddy/binaries/node/workspace")
MCP_ENTRY = "node_modules/12306-mcp/build/index.js"


def port_open(port, host="127.0.0.1"):
    s = socket.socket()
    s.settimeout(0.6)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def first_existing(cands):
    for c in cands:
        if os.path.isabs(c):
            if os.path.isfile(c):
                return c
        else:
            from shutil import which
            if which(c):
                return c
    return None


def main():
    # 双击 bat 运行时 stdout 是管道，不设行缓冲就看不到任何进度输出
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    py = first_existing(PY_CANDIDATES)
    node = first_existing(NODE_CANDIDATES)
    if not py:
        print("× 找不到 Python，请先安装 Python 3.10+")
        return 1
    print(f"· Python: {py}")

    procs = []

    # 1) 12306 数据服务
    if port_open(MCP_PORT):
        print(f"· 12306 数据服务已在 {MCP_PORT} 运行，复用")
    else:
        if not node:
            print("× 找不到 Node.js，无法启动 12306 数据服务（npm i -g 需要先装 Node）")
            print("  也可以手动：npx -y 12306-mcp --host localhost --port 8080")
        else:
            cwd = NODE_WORKSPACE if os.path.isfile(
                os.path.join(NODE_WORKSPACE, MCP_ENTRY)) else ROOT
            if not os.path.isfile(os.path.join(cwd, MCP_ENTRY)):
                print("× 未找到 12306-mcp，先安装：")
                print("  npm install 12306-mcp --registry=https://registry.npmmirror.com")
                return 1
            print(f"· 启动 12306 数据服务（{MCP_PORT}）…")
            env = dict(os.environ)
            env.setdefault("NO_PROXY", "localhost,127.0.0.1")
            procs.append(subprocess.Popen(
                [node, MCP_ENTRY, "--host", "localhost", "--port", str(MCP_PORT)],
                cwd=cwd, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            for _ in range(40):
                time.sleep(0.5)
                if port_open(MCP_PORT):
                    break
            if not port_open(MCP_PORT):
                print("× 12306 数据服务启动失败，请检查 Node 与网络")
                return 1
            print(f"· 12306 数据服务就绪（{MCP_PORT}）")

    # 2) 查询服务
    env = dict(os.environ)
    env.setdefault("NO_PROXY", "localhost,127.0.0.1")
    env.setdefault("no_proxy", "localhost,127.0.0.1")
    if port_open(API_PORT):
        print(f"· 查询服务已在 {API_PORT} 运行，复用")
    else:
        print(f"· 启动查询服务（{API_PORT}）…")
        procs.append(subprocess.Popen(
            [py, os.path.join(ROOT, "scripts", "api_server.py"),
             "--port", str(API_PORT)],
            cwd=ROOT, env=env))
        for _ in range(30):
            time.sleep(0.4)
            if port_open(API_PORT):
                break

    url = f"http://127.0.0.1:{API_PORT}/"
    print(f"\n✓ 就绪：{url}")
    print("  保持本窗口开启；关闭即停止服务。\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止…")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
