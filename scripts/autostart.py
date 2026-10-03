#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无窗口常驻守护：随 Windows 开机自启，持续保障 12306 查询服务在线。

- 若 12306 数据源(8080) 或 查询网关(8787) 没在跑，就拉起；
- 任一进程退出，自动重启（除非 exe 不存在，避免死循环）；
- 不打开浏览器、不弹控制台窗口（用 pythonw 启动本脚本即可）。

本脚本是「内置 start」的落地实现：用户无需再手动双击 start.bat，
只要本机登录，查询服务就在后台常驻。
"""
import os
import socket
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PY = os.path.join(HOME, ".workbuddy/binaries/python/envs/default/Scripts/pythonw.exe")
if not os.path.isfile(PY):
    PY = os.path.join(HOME, ".workbuddy/binaries/python/envs/default/Scripts/python.exe")

NODE = os.path.join(HOME, ".workbuddy/binaries/node/versions/22.22.2-3/node.exe")
NODE_WORKSPACE = os.path.join(HOME, ".workbuddy/binaries/node/workspace")
MCP_ENTRY = os.path.join(NODE_WORKSPACE, "node_modules/12306-mcp/build/index.js")

MCP_PORT = 8080
API_PORT = 8787
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def port_open(port, host="127.0.0.1"):
    s = socket.socket()
    s.settimeout(0.6)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def start(cmd, cwd, env):
    try:
        return subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as e:  # noqa: BLE001
        sys.stderr.write("启动失败 %s -> %s\n" % (cmd, e))
        return None


def main():
    env = dict(os.environ)
    env.setdefault("NO_PROXY", "localhost,127.0.0.1")
    env.setdefault("no_proxy", "localhost,127.0.0.1")

    procs = {"mcp": None, "api": None}
    sys.stderr.write("[autostart] 守护启动，监控 %d / %d\n" % (MCP_PORT, API_PORT))

    while True:
        # 1) 12306 数据源
        if not port_open(MCP_PORT):
            if os.path.isfile(MCP_ENTRY):
                procs["mcp"] = start(
                    [NODE, MCP_ENTRY, "--host", "localhost", "--port", str(MCP_PORT)],
                    NODE_WORKSPACE, env)
                sys.stderr.write("[autostart] 拉起 12306 数据源\n")
            else:
                sys.stderr.write("[autostart] 未找到 12306-mcp，跳过\n")
        # 2) 查询网关
        if not port_open(API_PORT):
            procs["api"] = start(
                [PY, os.path.join(ROOT, "scripts", "api_server.py"), "--port", str(API_PORT)],
                ROOT, env)
            sys.stderr.write("[autostart] 拉起查询网关\n")

        # 清理已退出的进程对象，便于下次重启
        for k in ("mcp", "api"):
            p = procs.get(k)
            if p is not None and p.poll() is not None:
                procs[k] = None

        time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
