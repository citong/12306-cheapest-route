# 12306 最便宜火车路线 · 新乡 → 昆明

一个纯静态网页（GitHub Pages），展示 **12306 实时余票**下从新乡到昆明**最便宜**的火车换乘方案。

高铁直达二等座约 **¥902**，而程序穷举多段普速（Z/T/K）换乘后可以找到 **¥276 起**的方案。

🔗 在线地址：https://citong.github.io/12306-cheapest-route/

## 页面能力

- 最优方案卡片：完整车次、时刻、席别、票价
- Top 10 票价横向对比条
- 全部可行路线列表，支持按**换乘次数 / 中转城市 / 排序方式 / 是否全程有票**筛选，点击展开看每一段的候选车次
- 直达车次（含高铁）作为价格基准对照

## 它怎么工作

查询能力来自 [`12306-smart-query`](https://github.com/52Herts-ux/12306-smart-query)：
在无直达（或只有贵的高铁）时，按设定的换乘次数穷举枢纽站之间的所有可行组合，
并按「有票优先 → 总价升序」排序。

由于 GitHub Pages 只能托管静态文件，**无法在浏览器里直接调用 12306**（有跨域限制，且需要本地 MCP 服务），
因此采用「离线生成数据 + 静态页读取」的方式：

```
12306 ──> 12306-mcp（本地服务）──> scripts/train_query.py ──> scripts/export_data.py ──> data.json ──> index.html
```

## 本地运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 12306 数据服务

```bash
npx -y 12306-mcp --host localhost --port 8080
```

若 npm 官方源不可达（会被静默卡住），改用镜像：

```bash
npm install 12306-mcp --registry=https://registry.npmmirror.com
node node_modules/12306-mcp/build/index.js --host localhost --port 8080
```

验证服务已就绪：

```bash
curl http://127.0.0.1:8080/sse   # 应返回 event: endpoint
```

> 本机若有 HTTP 代理，运行前请设置 `NO_PROXY=localhost,127.0.0.1`，
> 否则连本地服务也会被发给代理。

### 3. 生成数据

```bash
python scripts/export_data.py 2026-10-05            # 指定日期
python scripts/export_data.py --from 新乡 --to 昆明   # 自定义起终点
```

默认查询 3 天后、新乡 → 昆明。生成 `data.json`。

### 4. 本地预览

```bash
python -m http.server 8000
# 打开 http://127.0.0.1:8000
```

> 直接双击 `index.html` 会因为浏览器的 `file://` 跨域策略读不到 `data.json`，必须走 HTTP。

## 更新线上数据

仓库里配了 GitHub Actions：进 Actions → **Refresh 12306 data** → Run workflow，
可填查询日期。跑完会自动提交新的 `data.json`，Pages 稍后自动生效。

```bash
gh workflow run refresh-data.yml -f date=2026-10-07
```

## 目录结构

```
index.html                        # 静态页面（无构建、无外部依赖）
data.json                         # 生成的数据
scripts/train_query.py            # 12306 查询脚本（本仓库内置副本）
scripts/export_data.py            # 生成 data.json
.github/workflows/refresh-data.yml
```

## 说明

- 票价取该段**最低价席别**；「有票」指该席别当前有票。
- 12306 对无票额区间会返回 `0 元`，程序会过滤掉，避免被误判成最便宜。
- 换乘方案由程序自动拼接，**换乘时间是否充裕请自行确认**（建议预留 1 小时以上）。
- 余票与票价实时变动，实际购票请以 12306 官方为准。
