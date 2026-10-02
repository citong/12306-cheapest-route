# 12306 最便宜火车路线 · 新乡 → 昆明

一个纯静态网页（GitHub Pages），展示 **12306 实时余票**下从新乡到昆明**最便宜**的火车换乘方案。

高铁直达二等座约 **¥902**，而程序穷举多段普速（Z/T/K）换乘后可以找到 **¥276 起**的方案。

🔗 在线地址：https://citong.github.io/12306-cheapest-route/

## 页面能力

`index.html` 是**单文件静态页**：数据内嵌、零依赖、无构建，双击即可打开。

五个标签页（📊 总览 / 💰 最便宜方案 / 🗺 全部路线 / 🚄 直达对比 / ℹ️ 说明）：

- **总览**：省钱概览（最便宜 / 直达最低 / 可省金额与百分比）+ 最便宜的 12 条路线卡片网格，点卡片直接跳到该路线详情
- **最便宜方案**：逐段车次、时刻、历时、席别、票价、余票
- **全部路线**：27 条路线，可按**换乘次数 / 中转城市关键词 / 排序方式（票价·换乘·在途）/ 只看各段有票**筛选，点击展开每段候选车次
- **直达对比**：直达高铁车次表 + 费用差额结论
- **说明**：数据来源、票价口径、更新方式

## 它怎么工作

查询能力来自 [`12306-smart-query`](https://github.com/52Herts-ux/12306-smart-query)：
在无直达（或只有贵的高铁）时，按设定的换乘次数穷举枢纽站之间的所有可行组合，
并按「有票优先 → 总价升序」排序。

由于 GitHub Pages 只能托管静态文件，**无法在浏览器里直接调用 12306**（有跨域限制，且需要本地 MCP 服务），
因此采用「离线生成数据 + 静态页读取」的方式：

```
12306 ──> 12306-mcp（本地服务）──> scripts/train_query.py
        ──> scripts/export_data.py ──> data.json
        ──> scripts/render_site.py ──> index.html（数据内嵌的单文件页面）
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

默认查询 3 天后、新乡 → 昆明。生成 `data.json` 并自动渲染 `index.html`。

只改页面样式、不重新查数据时，可单独重渲染：

```bash
python scripts/render_site.py
```

### 4. 本地预览

数据已内嵌进 `index.html`，**直接双击打开即可**；也可以起服务：

```bash
python -m http.server 8000
# 打开 http://127.0.0.1:8000
```

## 更新线上数据

数据需要定期重新生成。两种方式：

**1. 本地生成后提交**

```bash
python scripts/export_data.py 2026-10-07
git add data.json index.html && git commit -m "data: 2026-10-07" && git push
```

**2. 用 GitHub Actions 自动生成**

本仓库附带了工作流模板 `workflows/refresh-data.yml.example`
（未直接放在 `.github/workflows/`，因为当前 GitHub token 没有 `workflow` scope，无法推送该目录）。
启用方法（任选其一）：

- GitHub 网页端：Actions → New workflow → set up a workflow yourself → 粘贴该文件内容，命名为 `refresh-data.yml`；
- 或本地：`cp workflows/refresh-data.yml.example .github/workflows/refresh-data.yml`，
  然后 `gh auth refresh -s workflow` 授权后再推送。

启用后即可手动触发：

```bash
gh workflow run refresh-data.yml -f date=2026-10-07
```

它会安装 `12306-mcp`、启动本地服务、跑 `export_data.py`，并自动提交新的 `data.json`。

## 目录结构

```
index.html                        # 单文件静态页面（数据内嵌、零依赖、无构建）
data.json                         # 生成的数据
scripts/train_query.py            # 12306 查询脚本（本仓库内置副本）
scripts/export_data.py            # 查数据 → data.json → 调 render_site
scripts/render_site.py            # data.json → index.html
workflows/refresh-data.yml.example# Actions 工作流模板（需手动启用）
```

## 说明

- 票价取该段**最低价席别**；「有票」指该席别当前有票。
- 12306 对无票额区间会返回 `0 元`，程序会过滤掉，避免被误判成最便宜。
- 换乘方案由程序自动拼接，**换乘时间是否充裕请自行确认**（建议预留 1 小时以上）。
- 余票与票价实时变动，实际购票请以 12306 官方为准。
