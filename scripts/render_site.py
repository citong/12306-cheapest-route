#!/usr/bin/env python3
"""
把 data.json 渲染成单文件静态站 index.html（数据内嵌，无外部依赖、无构建）。

用法：
  python scripts/render_site.py [data.json] [index.html]
"""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS = """
body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f4f5f7;margin:0;padding:20px 16px 40px;color:#1f2329}
.wrap{max-width:980px;margin:0 auto}
h1{font-size:24px;margin:0 0 4px}
.sub{color:#57606a;font-size:14px;margin-bottom:12px}
.nav{position:sticky;top:0;background:#f4f5f7;padding:10px 0;z-index:10;display:flex;gap:8px;flex-wrap:wrap}
.tab-btn{border:1px solid #d0d3d8;background:#fff;color:#1f2329;padding:7px 16px;border-radius:18px;font-size:14px;cursor:pointer;font-family:inherit}
.tab-btn:hover{border-color:#2ea44f}
.tab-btn.active{background:#2ea44f;border-color:#2ea44f;color:#fff;font-weight:bold}
.card{background:#fff;border-radius:10px;padding:20px 24px;margin:14px 0;box-shadow:0 1px 3px rgba(0,0,0,.08)}
h2{margin:0 0 6px;font-size:19px}
.meta{color:#57606a;font-size:13px;margin-bottom:10px}
.stats{display:flex;gap:22px;flex-wrap:wrap;font-size:13.5px;margin-bottom:8px}
.bar{height:8px;background:#e5e6eb;border-radius:4px;overflow:hidden;margin-bottom:14px}
.bar>div{height:100%;background:#2ea44f}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{background:#eef0f3;text-align:left;padding:8px 10px;border-bottom:2px solid #d0d3d8;font-size:13px;white-space:nowrap}
td{padding:7px 10px;border-bottom:1px solid #eceef1}
tr.done td{background:#c6efce}
tr.done td.avail{color:#006100;font-weight:bold}
tr.sec td{background:#f8f9fa;font-weight:bold;color:#57606a;border-bottom:1px solid #d0d3d8;font-size:12.5px}
td.num{color:#8b949e;width:38px;white-space:nowrap;font-size:12.5px}
td.dur{white-space:nowrap;width:78px;text-align:right;color:#57606a;font-variant-numeric:tabular-nums}
td.money{white-space:nowrap;width:82px;text-align:right;font-variant-numeric:tabular-nums}
.ov-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px;margin-top:6px}
.ov-card{background:#fff;border:1px solid #e5e6eb;border-radius:10px;padding:14px 16px;cursor:pointer;transition:box-shadow .15s}
.ov-card:hover{box-shadow:0 3px 10px rgba(0,0,0,.12);border-color:#2ea44f}
.ov-card.best{border-color:#2ea44f;box-shadow:0 0 0 2px rgba(46,164,79,.18)}
.ov-head{display:flex;justify-content:space-between;font-size:15px;margin-bottom:2px;gap:8px}
.ov-pct{color:#2ea44f;font-weight:bold;white-space:nowrap}
.ov-meta{color:#57606a;font-size:12.5px;margin-bottom:8px}
.ov-card .bar{margin-bottom:6px}
.ov-stats{color:#8b949e;font-size:12.5px}
.legend{font-size:13px;color:#57606a;margin:6px 0 4px}
.sw{display:inline-block;width:14px;height:14px;background:#c6efce;border:1px solid #86c086;vertical-align:-2px;margin-right:5px}
a{color:#0969da;text-decoration:none}
.foot{color:#8b949e;font-size:12.5px;margin:22px 0 8px}
.green{color:#2ea44f}
.big{font-size:20px;font-weight:bold}
.filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:10px 0 4px;font-size:13.5px}
.filters input[type=text],.filters select{border:1px solid #d0d3d8;border-radius:8px;padding:6px 10px;font-size:13.5px;font-family:inherit;background:#fff;color:#1f2329}
.filters input[type=text]{min-width:170px}
.filters label{color:#57606a;cursor:pointer}
.route{border:1px solid #e5e6eb;border-radius:10px;margin-bottom:10px;overflow:hidden;background:#fff}
.route.best{border-color:#2ea44f}
.route-head{display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;flex-wrap:wrap}
.route-head:hover{background:#f8f9fa}
.rank{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:#eef0f3;color:#57606a;font-size:12px;flex:none}
.route.best .rank{background:#2ea44f;color:#fff}
.rpath{font-weight:bold;font-size:14.5px;flex:1;min-width:190px}
.tag{border:1px solid #d0d3d8;border-radius:12px;padding:2px 9px;font-size:12px;color:#57606a;white-space:nowrap}
.tag.ok{border-color:#86c086;background:#c6efce;color:#006100}
.tag.no{border-color:#e0b4b4;background:#ffc7ce;color:#9c0006}
.rprice{font-size:16px;font-weight:bold;color:#2ea44f;font-variant-numeric:tabular-nums;white-space:nowrap}
.route-body{display:none;border-top:1px solid #eceef1;padding:4px 14px 12px}
.route-body.open{display:block}
.empty{color:#8b949e;font-size:13.5px;padding:14px 0}
.note{font-size:13.5px;line-height:1.75;color:#1f2329}
.note li{margin:4px 0}
code{background:#eef0f3;border-radius:4px;padding:1px 5px;font-size:12.5px}
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>12306 最便宜路线 · __FRM__ → __TO__</title>
<style>__CSS__</style>
</head>
<body><div class="wrap">
<h1>🚂 12306 最便宜路线 · __FRM__ → __TO__</h1>
<div class="sub">__SUBTITLE__</div>
<div class="nav">
<button class="tab-btn active" data-tab="tab-overview" onclick="showTab('tab-overview')">📊 总览</button>
<button class="tab-btn" data-tab="tab-best" onclick="showTab('tab-best')">💰 最便宜方案</button>
<button class="tab-btn" data-tab="tab-routes" onclick="showTab('tab-routes')">🗺 全部路线</button>
<button class="tab-btn" data-tab="tab-direct" onclick="showTab('tab-direct')">🚄 直达对比</button>
<button class="tab-btn" data-tab="tab-about" onclick="showTab('tab-about')">ℹ️ 说明</button>
</div>

<section class="tab-page" id="tab-overview">
__OVERVIEW__
</section>

<section class="tab-page" id="tab-best" style="display:none">
__BEST_PAGE__
</section>

<section class="tab-page" id="tab-routes" style="display:none">
<div class="card">
<h2>🗺 全部 __N_ROUTES__ 条可行路线</h2>
<div class="meta">点击任一条展开，查看每一段的候选车次与余票</div>
<div class="filters">
<input type="text" id="f-q" placeholder="搜中转城市，如 郑州" oninput="render()">
<select id="f-trans" onchange="render()">
<option value="">全部换乘次数</option>
__HOP_OPTIONS__
</select>
<select id="f-sort" onchange="render()">
<option value="price">按票价排序</option>
<option value="trans">按换乘次数排序</option>
<option value="ride">按在途时长排序</option>
</select>
<label><input type="checkbox" id="f-avail" onchange="render()"> 只看各段均有票</label>
</div>
<div id="route-list"></div>
</div>
</section>

<section class="tab-page" id="tab-direct" style="display:none">
__DIRECT_PAGE__
</section>

<section class="tab-page" id="tab-about" style="display:none">
__ABOUT_PAGE__
</section>

<div class="foot">__FOOT__</div>
</div>
<script>
const DATA = __DATA_JSON__;
const BEST = DATA.best;
const ROUTES = DATA.routes || [];

function money(v){ return v==null ? '—' : '¥' + (Math.round(v*100)/100); }
function dur(min){
  if(min==null) return '—';
  const h = Math.floor(min/60), m = min%60;
  return h>0 ? (h + '小时' + (m? m+'分':'')) : (m + '分');
}
function showTab(id){
  document.querySelectorAll('.tab-btn').forEach(function(b){b.classList.toggle('active',b.dataset.tab===id);});
  document.querySelectorAll('.tab-page').forEach(function(p){p.style.display=p.id===id?'':'none';});
  window.scrollTo(0,0);
}
function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function seatRows(t){
  if(!t.seats || !t.seats.length) return '';
  return t.seats.map(function(s){
    return '<tr><td></td><td></td><td>' + esc(s.seat) + '</td><td>' + esc(s.status) +
           '</td><td class="money">' + money(s.price) + '</td></tr>';
  }).join('');
}

function legTable(leg, idx){
  const rows = (leg.trains||[]).map(function(t){
    const cls = t.available ? ' class="done"' : '';
    return '<tr' + cls + '><td class="num">' + esc(t.code) + '</td><td>' + esc(t.depart) + ' → ' + esc(t.arrive) +
      '</td><td class="dur">' + esc(t.duration) + '</td><td>' + esc(t.seat||'—') +
      '</td><td class="dur">' + money(t.price) + '</td><td class="avail">' +
      (t.available ? '有票' : (t.available===false ? '无票' : '—')) + '</td></tr>';
  }).join('');
  return '<tr class="sec"><td colspan="6">第 ' + idx + ' 段 · ' + esc(leg.from) + ' → ' + esc(leg.to) +
    ' &nbsp;<span style="font-weight:normal">' + (leg.price!=null? money(leg.price) : '票价未知') + '</span></td></tr>' + rows;
}

function routeCard(r){
  const tags = [];
  tags.push('<span class="tag">换乘 ' + r.transfers + ' 次</span>');
  tags.push(r.all_available ? '<span class="tag ok">各段有票</span>' : '<span class="tag no">部分无票</span>');
  tags.push('<span class="tag">在途 ' + dur(r.ride_minutes) + '</span>');
  const body = (r.legs||[]).map(function(l,i){ return legTable(l, i+1); }).join('');
  return '<div class="route' + (r.id===BEST.id?' best':'') + '" id="rt-' + r.id + '">' +
    '<div class="route-head" onclick="toggle(' + r.id + ')">' +
      '<span class="rank">' + r.id + '</span>' +
      '<span class="rpath">' + esc(r.path.join(' → ')) + '</span>' +
      tags.join('') +
      '<span class="rprice">' + money(r.total_price) + '</span>' +
    '</div>' +
    '<div class="route-body" id="rb-' + r.id + '"><table>' +
      '<tr><th>车次</th><th>时刻</th><th>历时</th><th>席别</th><th>票价</th><th>余票</th></tr>' +
      body + '</table></div>' +
  '</div>';
}

function toggle(id){
  const b = document.getElementById('rb-' + id);
  if(b) b.classList.toggle('open');
}
function openRoute(id){
  showTab('tab-routes');
  const b = document.getElementById('rb-' + id);
  if(b) b.classList.add('open');
  const el = document.getElementById('rt-' + id);
  if(el) setTimeout(function(){ el.scrollIntoView({block:'center'}); }, 30);
}

function render(){
  const q = (document.getElementById('f-q').value||'').trim();
  const trans = document.getElementById('f-trans').value;
  const sort = document.getElementById('f-sort').value;
  const availOnly = document.getElementById('f-avail').checked;
  let list = ROUTES.filter(function(r){
    if(availOnly && !r.all_available) return false;
    if(trans !== ''){
      const t = r.transfers;
      if(trans === '0' && t !== 0) return false;
      if(trans === '1' && t !== 1) return false;
      if(trans === '2' && t !== 2) return false;
      if(trans === '3' && t < 3) return false;
    }
    if(q && !(r.via||[]).some(function(c){ return c.indexOf(q) >= 0; }) && r.path.join('').indexOf(q) < 0) return false;
    return true;
  });
  const key = {
    price: function(r){ return [r.total_price==null?1e9:r.total_price, r.transfers, r.ride_minutes]; },
    trans: function(r){ return [r.transfers, r.total_price==null?1e9:r.total_price]; },
    ride:  function(r){ return [r.ride_minutes==null?1e9:r.ride_minutes, r.total_price==null?1e9:r.total_price]; }
  }[sort];
  list = list.slice().sort(function(a,b){
    const ka = key(a), kb = key(b);
    for(let i=0;i<ka.length;i++){ if(ka[i]!==kb[i]) return ka[i]-kb[i]; }
    return a.id-b.id;
  });
  const el = document.getElementById('route-list');
  el.innerHTML = list.length ? list.map(routeCard).join('') : '<div class="empty">没有符合条件的路线</div>';
}
render();
</script>
</body></html>
"""


def fmt_duration(minutes):
    if minutes is None:
        return "—"
    h, m = minutes // 60, minutes % 60
    return f"{h}小时{m}分" if m else f"{h}小时"


def money(v):
    return "—" if v is None else f"¥{v:g}"


def build_overview(data):
    m, best, routes = data["meta"], data.get("best"), data.get("routes", [])
    direct_min = (data.get("direct") or {}).get("min_price")
    prices = [r["total_price"] for r in routes if r.get("total_price") is not None]
    mx = max(prices) if prices else 0
    mn = min(prices) if prices else 0

    save = ""
    pct = 0.0
    if best and direct_min and best.get("total_price"):
        save_v = direct_min - best["total_price"]
        pct = round(save_v / direct_min * 100, 1)
        save = f'<span>最多可省 <b class="green big">¥{save_v:g}</b>（{pct}%）</span>'

    cards = []
    for r in routes[:12]:
        p = r.get("total_price")
        width = 0
        if p is not None and mx > mn:
            width = round((mx - p) / (mx - mn) * 100, 1)
        elif p is not None:
            width = 100
        via = "、".join(r.get("via") or []) or "无中转"
        avail = "各段有票" if r.get("all_available") else "部分无票"
        cls = "ov-card best" if best and r.get("id") == best.get("id") else "ov-card"
        cards.append(
            f'<div class="{cls}" onclick="openRoute({r["id"]})">'
            f'<div class="ov-head"><b>{" → ".join(r["path"])}</b>'
            f'<span class="ov-pct">{money(p)}</span></div>'
            f'<div class="ov-meta">换乘 {r.get("transfers", 0)} 次 · 中转：{via}</div>'
            f'<div class="bar"><div style="width:{width}%"></div></div>'
            f'<div class="ov-stats">在途 {fmt_duration(r.get("ride_minutes"))} · {avail}</div>'
            f"</div>"
        )

    return (
        '<div class="card">'
        "<h2>💰 省钱概览</h2>"
        f'<div class="meta">{m["from"]} → {m["to"]} · {m["date"]} · 共 {len(routes)} 条可行路线</div>'
        '<div class="stats">'
        f'<span>最便宜 <b class="green big">{money(best.get("total_price") if best else None)}</b></span>'
        f'<span>直达最低 <b>{money(direct_min)}</b></span>'
        f"{save}"
        f'<span>换乘 <b>{best.get("transfers", 0) if best else 0} 次</b></span>'
        f'<span>在途 <b>{fmt_duration(best.get("ride_minutes") if best else None)}</b></span>'
        "</div>"
        f'<div class="bar"><div style="width:{max(pct, 0)}%"></div></div>'
        '<div class="legend">进度条 = 相对直达高铁的省钱幅度</div>'
        "</div>"
        '<div class="card">'
        "<h2>🏅 最便宜的 12 条路线</h2>"
        '<div class="meta">点击卡片查看该路线每一段的候选车次</div>'
        f'<div class="ov-grid">{"".join(cards)}</div>'
        "</div>"
    )


def build_best_page(data):
    best = data.get("best")
    if not best:
        return '<div class="card"><h2>💰 最便宜方案</h2><div class="empty">暂无数据</div></div>'
    m = data["meta"]
    direct_min = (data.get("direct") or {}).get("min_price")
    rows = []
    for i, leg in enumerate(best.get("legs", []), 1):
        rows.append(
            f'<tr class="sec"><td colspan="7">第 {i} 段 · {leg.get("from")} → {leg.get("to")}'
            f' &nbsp;<span style="font-weight:normal">{money(leg.get("price"))}</span></td></tr>'
        )
        for t in leg.get("trains", []):
            cls = ' class="done"' if t.get("available") else ""
            rows.append(
                f'<tr{cls}><td class="num">{t.get("code","")}</td>'
                f'<td>{leg.get("from")} → {leg.get("to")}</td>'
                f'<td>{t.get("depart","")} → {t.get("arrive","")}</td>'
                f'<td class="dur">{t.get("duration","")}</td>'
                f'<td>{t.get("seat") or "—"}</td>'
                f'<td class="money">{money(t.get("price"))}</td>'
                f'<td class="avail">{"有票" if t.get("available") else "无票"}</td></tr>'
            )
    save_txt = ""
    if direct_min and best.get("total_price"):
        save_txt = (
            f'<div class="meta">相比直达高铁最低价 {money(direct_min)}，'
            f'可省 <b class="green">¥{direct_min - best["total_price"]:g}</b>，'
            f'代价是在途 {fmt_duration(best.get("ride_minutes"))}、换乘 {best.get("transfers",0)} 次。</div>'
        )
    return (
        '<div class="card">'
        f'<h2>💰 {" → ".join(best["path"])}</h2>'
        f'<div class="meta">{m["date"]} 出发 · 总价 <b class="green big">{money(best.get("total_price"))}</b></div>'
        f"{save_txt}"
        '<div class="stats">'
        f'<span>换乘 <b>{best.get("transfers",0)} 次</b></span>'
        f'<span>在途 <b>{fmt_duration(best.get("ride_minutes"))}</b></span>'
        f'<span>各段均有票 <b>{"是" if best.get("all_available") else "否"}</b></span>'
        "</div>"
        "<table><tr><th>车次</th><th>区间</th><th>时刻</th><th>历时</th>"
        f"<th>席别</th><th>票价</th><th>余票</th></tr>{''.join(rows)}</table>"
        "</div>"
    )


def build_direct_page(data):
    d = data.get("direct") or {}
    trains = d.get("trains") or []
    rows = []
    for t in trains:
        cls = ' class="done"' if t.get("available") else ""
        rows.append(
            f'<tr{cls}><td class="num">{t.get("code","")}</td>'
            f'<td>{data["meta"]["from"]} → {data["meta"]["to"]}</td>'
            f'<td>{t.get("depart","")} → {t.get("arrive","")}</td>'
            f'<td class="dur">{t.get("duration","")}</td>'
            f'<td>{t.get("seat") or "—"}</td>'
            f'<td class="money">{money(t.get("price"))}</td>'
            f'<td class="avail">{"有票" if t.get("available") else "无票"}</td></tr>'
        )
    if not rows:
        rows.append('<tr><td colspan="7" class="empty">本次查询未取到直达车次（12306 可能限流）</td></tr>')

    best = data.get("best")
    cmp_rows = ""
    if best and d.get("min_price") and best.get("total_price"):
        gap = d["min_price"] - best["total_price"]
        cmp_rows = (
            f'<tr class="sec"><td colspan="2">结论</td></tr>'
            f'<tr><td>直达高铁二等座（最低）</td><td class="money">{money(d["min_price"])}</td></tr>'
            f'<tr class="done"><td>普速多段换乘（最便宜）</td><td class="money">{money(best["total_price"])}</td></tr>'
            f'<tr><td>差额</td><td class="money">{money(gap)}</td></tr>'
            f'<tr><td>换乘代价</td><td class="money">换乘 {best.get("transfers",0)} 次 · 在途 {fmt_duration(best.get("ride_minutes"))}</td></tr>'
        )
    return (
        '<div class="card">'
        "<h2>🚄 直达车次（含高铁）</h2>"
        f'<div class="meta">{data["meta"]["date"]} · 新乡 → 昆明 · 绿色行表示有票</div>'
        '<div class="legend"><span class="sw"></span>绿色 = 有票 · 无色 = 无票</div>'
        "<table><tr><th>车次</th><th>区间</th><th>时刻</th><th>历时</th>"
        f"<th>席别</th><th>票价</th><th>余票</th></tr>{''.join(rows)}</table>"
        "</div>"
        '<div class="card">'
        "<h2>⚖️ 对比结论</h2>"
        f'<table><tr><th>方案</th><th>费用</th></tr>{cmp_rows}</table>'
        '<div class="meta" style="margin-top:10px">普速方案用时间换金钱：'
        "适合预算优先、时间充裕的行程；赶时间建议直达高铁。</div>"
        "</div>"
    )


ABOUT = """
<div class="card">
<h2>ℹ️ 数据来源与方法</h2>
<div class="note">
<ul>
<li><b>数据来源</b>：12306 官方余票接口，经本地 <code>12306-mcp</code> 服务转发查询，未使用任何第三方票代数据。</li>
<li><b>车型范围</b>：默认只搜普速 <code>Z/T/K</code>（最便宜的主力）；直达对比表含高铁 <code>G/D/C</code>。</li>
<li><b>穷举方式</b>：以 30+ 个枢纽城市为图节点做 BFS，最多 __MAXHOPS__ 次换乘，逐段查询实时余票，
再按「各段均有票优先 → 总价升序」排序，取第一条为最便宜方案。</li>
<li><b>票价口径</b>：每段取「有票席别中的最低价」；若无有票席别，则取全部席别最低价并标记为无票。
12306 对无票额区间会返回 0 元，这类票价已剔除，不参与排序。</li>
<li><b>在途时长</b>：各段运行时间之和，<b>不含</b>换乘等待时间。</li>
<li><b>刷新时间</b>：__GEN__</li>
</ul>
</div>
</div>
<div class="card">
<h2>🔄 如何更新数据</h2>
<div class="note">
<p>本页是静态页，数据在生成时内嵌，不会自动变化。重新生成：</p>
<ul>
<li>本地：<code>python scripts/export_data.py 2026-10-07</code>（需先启动 <code>12306-mcp</code>）</li>
<li>线上：启用仓库里的 <code>workflows/refresh-data.yml.example</code> 为 Actions 工作流后，
<code>gh workflow run refresh-data.yml -f date=2026-10-07</code></li>
</ul>
<p style="color:#57606a">余票实时变动，购票请以 12306 官方 App 为准。</p>
</div>
</div>
"""


def render(data):
    m = data["meta"]
    n = len(data.get("routes", []))
    hops = sorted({r.get("transfers", 0) for r in data.get("routes", [])})
    hop_options = "".join(
        f'<option value="{h}">换乘 {h} 次</option>' for h in hops
    )
    gen = m.get("generated_at", "")[:19].replace("T", " ")
    subtitle = (
        f'出行日期 {m["date"]} · 车型 {m.get("train_types") or "ZTK"} 普速 · '
        f'最多换乘 {m.get("max_hops")} 次 · 更新于 '
        + m.get("generated_at", "")[:19].replace("T", " ")
    )
    foot = (
        f'数据由 <a href="https://github.com/citong/12306-cheapest-route">citong/12306-cheapest-route</a> '
        f'自动生成 · 余票实时变动，请以 12306 官方为准'
    )
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    html = HTML
    for k, v in {
        "__CSS__": CSS,
        "__FRM__": m["from"],
        "__TO__": m["to"],
        "__SUBTITLE__": subtitle,
        "__OVERVIEW__": build_overview(data),
        "__BEST_PAGE__": build_best_page(data),
        "__HOP_OPTIONS__": hop_options,
        "__N_ROUTES__": n,
        "__DIRECT_PAGE__": build_direct_page(data),
        "__ABOUT_PAGE__": ABOUT.replace("__MAXHOPS__", str(m.get("max_hops")))
                               .replace("__GEN__", gen),
        "__FOOT__": foot,
        "__DATA_JSON__": payload,
    }.items():
        html = html.replace(k, v if isinstance(v, str) else str(v))
    return html


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data.json")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "index.html")
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    html = render(data)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ 已生成 {dst}（{len(html) / 1024:.0f} KB，{len(data.get('routes', []))} 条路线）")


if __name__ == "__main__":
    main()
