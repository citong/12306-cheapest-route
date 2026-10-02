# 12306 最便宜火车路线

输入任意**起点 / 终点 / 日期**，穷举多段换乘，找出**最便宜**的火车方案。

高铁直达新乡→昆明二等座约 **¥902**，程序穷举普速（Z/T/K）换乘后可以找到 **¥276 起**的方案。

🔗 在线地址：https://citong.github.io/12306-cheapest-route/

---

## 两种模式，页面自动切换

网页右上角会显示当前状态：

| 状态 | 说明 |
|---|---|
| 🟢 **实时查询服务已连接** | 本机跑着查询服务，可查**任意**起终点 / 日期，逐段请求 12306 官方余票 |
| ⚪ **离线** | 只能看内置的那条已生成线路（新乡 → 昆明 2026-10-05） |

> GitHub Pages 是纯静态托管，浏览器不能直连 12306（跨域 + 需要本地数据服务），
> 所以"任意线路实时查询"由本机服务提供；页面会自动探测，没有也能用。

## 启动本地服务（推荐）

在项目目录双击 **`start.bat`**（macOS/Linux：`./start.sh`），它会自动：

1. 拉起 12306 数据服务（`12306-mcp`，127.0.0.1:8080）
2. 拉起查询服务（`api_server.py`，127.0.0.1:8787）
3. 打开 http://127.0.0.1:8787/

保持窗口开着即可，关掉就停止。之后刷新 GitHub Pages 上那个页面，也会自动变成实时模式。

> 若浏览器拦截了 https 页面访问 `http://127.0.0.1`，直接用本地服务地址
> `http://127.0.0.1:8787/` 打开（页面同源，最稳）。

## 页面能力

- **起终点自动补全**：3404 个车站，支持中文 / 拼音 / 首字母（`xx` → 新乡）
- **实时进度**：逐段探测，边查边出结果，不用干等
- **车次衔接编排**：不只是票价估算——会为每条路线挑出**实际能坐上**的具体车次
  （换乘预留 ≥30 分钟），并算出在途时长、换乘等待、全程跨度
- **KPI 概览**：最便宜 / 直达最低 / 最多可省 / 可行路线数
- **筛选排序**：按换乘次数、中转城市、票价、在途时长、只看可衔接
- 查询参数写在 URL hash 里，可直接分享链接

## 它怎么工作

```
12306 官方 ──> 12306-mcp（本地 8080）──> scripts/api_server.py（本地 8787，SSE 流式）
                                              │
                                              ├─ 逐段查直达车次（并发 4，段内只查直达，换乘交给 BFS）
                                              ├─ 以 30+ 枢纽城市为节点做 BFS，最多 4 次换乘
                                              ├─ 贪心编排具体车次（换乘间隔 ≥30 分钟）
                                              └─ 排序：可衔接且有票 → 总价升序
                                                        │
                                              index.html（数据内嵌的静态页）
```

查询能力源自 [`12306-smart-query`](https://github.com/52Herts-ux/12306-smart-query)，
本仓库内置副本并修复了若干缺陷（见下）。

## 手动运行

```bash
pip install -r requirements.txt
python scripts/gen_stations.py                 # 生成车站表（3404 站）
npm install 12306-mcp --registry=https://registry.npmmirror.com
node node_modules/12306-mcp/build/index.js --host localhost --port 8080
python scripts/api_server.py --port 8787       # 然后打开 http://127.0.0.1:8787/
```

> 本机若有 HTTP 代理，连本地服务前请设 `NO_PROXY=localhost,127.0.0.1`。
> npm 官方源若被代理拦住（会静默卡死），改用上面的淘宝镜像。

## 更新内置数据（离线展示用）

```bash
python scripts/export_data.py 2026-10-07            # 查数据 → data.json → 自动渲染 index.html
python scripts/export_data.py 2026-10-07 --from 新乡 --to 大理
git add data.json index.html && git commit -m "data: 2026-10-07" && git push
```

只改页面样式不重查数据：`python scripts/render_site.py`

## 目录结构

```
index.html                        # 单文件页面（数据+车站表内嵌，零依赖无构建）
data.json                         # 内置线路数据（离线模式展示）
stations.json                     # 3404 个车站，供输入框补全
start.bat / start.sh              # 一键启动（数据服务 + 查询服务 + 开浏览器）
scripts/launcher.py               # 启动器：拉起两个服务并打开页面
scripts/api_server.py             # 查询服务：SSE 流式查询 + 车次编排 + 静态托管
scripts/train_query.py            # 12306 查询脚本（内置副本，已修复多处缺陷）
scripts/export_data.py            # 生成 data.json
scripts/render_site.py            # data.json + stations.json → index.html
scripts/site_template.html        # 页面模板
workflows/refresh-data.yml.example# Actions 工作流模板（需手动启用）
```

## 已修复的原始缺陷

上游 `12306-smart-query` 号称找"最便宜路线"，但代码里并**没有票价解析与排序**。本仓库补上：

- 新增票价解析与「有票优先 → 总价升序」排序
- `--multi` 文档里有、代码里没实现 → 已补全
- `format_cached_edge` 读缓存边时必崩（缓存不存 `from_code`）→ 已修
- 12306 对无票额区间返回 `0 元`，会被误判成"最便宜" → 已过滤
- BFS 把终点站也放进 `visited`，导致**只有第一条**到达终点的路径被记录 → 已修
- 官方中转文本块含多个车次，取最小值会严重低估总价 → 改为求和
- 补齐枢纽站（原版没有南宁等）

## 说明

- 票价取该段**有票席别中的最低价**；全无票时取最低标价并标记无票。
- 换乘建议预留 1 小时以上，页面默认按 30 分钟判定能否衔接。
- 「衔接不上」表示该路线在当前车次时刻下无法连起来，票价仅供参考。
- 余票与票价实时变动，购票请以 12306 官方为准。
