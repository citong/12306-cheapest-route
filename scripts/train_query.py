import asyncio
import json
import re
import sys
import os
import time
import itertools
import hashlib
from collections import deque, defaultdict
from datetime import datetime, timedelta
from mcp import ClientSession
from mcp.client.sse import sse_client

MCP_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8080/sse")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "train_cache_graph.json")
CACHE_EXPIRE_DAYS = 2

# -------------------- MCP 核心交互 --------------------
async def call_mcp_tool(session, tool_name, arguments):
    result = await session.call_tool(tool_name, arguments)
    for c in result.content:
        if c.type == "text":
            return c.text
    return None

async def get_current_date(session):
    text = await call_mcp_tool(session, "get-current-date", {})
    return text.strip() if text else None

def clean_station_name(name):
    suffixes = ["火车站", "高铁站", "站", "车站"]
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return name

async def get_station_code(session, location_name):
    city_text = await call_mcp_tool(session, "get-station-code-of-citys", {"citys": location_name})
    if city_text:
        try:
            data = json.loads(city_text)
            if location_name in data:
                return data[location_name]["station_code"]
        except:
            pass
    cleaned = clean_station_name(location_name)
    if cleaned != location_name:
        station_text = await call_mcp_tool(session, "get-station-code-by-names", {"stationNames": cleaned})
        if station_text:
            try:
                data = json.loads(station_text)
                if isinstance(data, dict) and cleaned in data:
                    return data[cleaned]["station_code"]
                if isinstance(data, str):
                    return data.strip()
            except:
                pass
    station_text = await call_mcp_tool(session, "get-station-code-by-names", {"stationNames": location_name})
    if station_text:
        try:
            data = json.loads(station_text)
            if isinstance(data, dict) and location_name in data:
                return data[location_name]["station_code"]
            if isinstance(data, str):
                return data.strip()
        except:
            pass
    return None

async def query_direct(session, from_code, to_code, date, train_types=None):
    arguments = {"fromStation": from_code, "toStation": to_code, "date": date, "purpose_codes": "ADULT"}
    if train_types:
        arguments["trainFilterFlags"] = train_types
    return await call_mcp_tool(session, "get-tickets", arguments)

async def query_interline(session, from_code, to_code, date, train_types=None):
    arguments = {"fromStation": from_code, "toStation": to_code, "date": date, "purpose_codes": "ADULT"}
    if train_types:
        arguments["trainFilterFlags"] = train_types
    return await call_mcp_tool(session, "get-interline-tickets", arguments)

# -------------------- 文本解析 --------------------
def parse_direct_blocks(raw_text):
    lines = raw_text.splitlines()
    blocks, current_block = [], []
    train_pattern = re.compile(r'^[GDCZTK]\d+')
    for line in lines:
        if train_pattern.match(line.strip()):
            if current_block: blocks.append('\n'.join(current_block))
            current_block = [line]
        else:
            if current_block: current_block.append(line)
    if current_block: blocks.append('\n'.join(current_block))
    return blocks

def parse_transfer_blocks(raw_text):
    lines = raw_text.splitlines()
    blocks, current_block = [], []
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2} ->')
    for line in lines:
        if date_pattern.match(line):
            if current_block: blocks.append('\n'.join(current_block))
            current_block = [line]
        else:
            if current_block: current_block.append(line)
    if current_block: blocks.append('\n'.join(current_block))
    return blocks

def extract_train_codes(block):
    lines = block.split('\n')
    codes = []
    train_pattern = re.compile(r'^([GDCZTK]\d+)\s+')
    for line in lines:
        match = train_pattern.match(line.strip())
        if match: codes.append(match.group(1))
    return codes

def is_same_train_transfer(block):
    codes = extract_train_codes(block)
    return len(codes) >= 2 and len(set(codes)) == 1

def filter_by_train_types(block, allowed_types):
    if not allowed_types: return True
    for code in extract_train_codes(block):
        if code[0] not in allowed_types: return False
    return True

def filter_by_via(blocks, via_city, exclude_same_train=False, allowed_train_types=None):
    matched = []
    clean_via = via_city.strip()
    for block in blocks:
        if exclude_same_train and is_same_train_transfer(block):
            continue
        if not filter_by_train_types(block, allowed_train_types):
            continue
        first_line = block.split('\n')[0]
        match = re.search(r'\|\s*([^|]+)\s*->\s*([^|]+)\s*->\s*([^|]+)\s*\|', first_line)
        if match:
            transfer_st = match.group(2).strip()
            if clean_via in transfer_st or transfer_st in clean_via:
                matched.append(block)
    return matched

# -------------------- 图缓存管理 (保持不变) --------------------
class TrainCacheGraph:
    def __init__(self, filepath=CACHE_FILE):
        self.filepath = filepath
        self.graph = defaultdict(lambda: defaultdict(list))
        self.station_names = {}
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for from_code, to_dict in data.get('graph', {}).items():
                        for to_code, edges in to_dict.items():
                            self.graph[from_code][to_code] = edges
                    self.station_names = data.get('station_names', {})
            except:
                pass

    def save(self):
        data = {
            'graph': {from_code: dict(to_dict) for from_code, to_dict in self.graph.items()},
            'station_names': self.station_names
        }
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_edge(self, from_code, to_code, train_info, date, train_type):
        edge = {
            'train_code': train_info.get('train_code', ''),
            'depart_time': train_info.get('depart_time', ''),
            'arrive_time': train_info.get('arrive_time', ''),
            'duration': train_info.get('duration', ''),
            'seats': train_info.get('seats', {}),
            'cached_date': date,
            'cached_timestamp': time.time(),
            'train_type': train_type
        }
        existing = self.graph[from_code][to_code]
        for i, e in enumerate(existing):
            if e['train_code'] == edge['train_code']:
                existing[i] = edge
                self.save()
                return
        existing.append(edge)
        self.save()

    def get_edges(self, from_code, to_code, date=None, train_types=None, max_age_days=CACHE_EXPIRE_DAYS):
        edges = self.graph.get(from_code, {}).get(to_code, [])
        valid = []
        now = time.time()
        for e in edges:
            if now - e['cached_timestamp'] > max_age_days * 86400:
                continue
            if date and e['cached_date'] != date:
                continue
            if train_types and e['train_type'][0] not in train_types:
                continue
            valid.append(e)
        return valid

    def find_paths(self, start_code, end_code, date, train_types, max_hops=4):
        queue = deque()
        queue.append((start_code, []))
        visited = set()
        found = []
        while queue:
            cur, path = queue.popleft()
            if len(path) >= max_hops:
                continue
            for nxt, edges in self.graph[cur].items():
                if nxt in visited:
                    continue
                valid_edges = [e for e in edges if (not date or e['cached_date'] == date) and
                               (not train_types or e['train_type'][0] in train_types)]
                if not valid_edges:
                    continue
                edge = valid_edges[0]
                step = {
                    'from_code': cur,
                    'to_code': nxt,
                    'train_code': edge['train_code'],
                    'depart_time': edge['depart_time'],
                    'arrive_time': edge['arrive_time'],
                    'duration': edge['duration'],
                    'seats': edge['seats']
                }
                new_path = path + [step]
                if nxt == end_code:
                    found.append(new_path)
                else:
                    visited.add(nxt)
                    queue.append((nxt, new_path))
        return found

    def update_station_name(self, code, name):
        self.station_names[code] = name
        self.save()

cache_graph = TrainCacheGraph()

# -------------------- 票务获取（带缓存）--------------------
async def get_tickets_between(session, from_code, to_code, date, train_types, use_cache=True):
    if use_cache:
        cached_edges = cache_graph.get_edges(from_code, to_code, date, train_types)
        if cached_edges:
            edge = cached_edges[0]
            print(f"  使用缓存边: {from_code}->{to_code} {edge['train_code']}", file=sys.stderr)
            return {
                'type': 'direct',
                'trains': [format_cached_edge(edge, from_code, to_code)],
                'from_cache': True
            }
    direct_raw = await query_direct(session, from_code, to_code, date, train_types)
    if direct_raw and "Error:" not in direct_raw:
        blocks = parse_direct_blocks(direct_raw)
        blocks = [b for b in blocks if filter_by_train_types(b, train_types)]
        if blocks:
            for block in blocks[:3]:
                extract_and_cache_edges(block, from_code, to_code, date, train_types)
            return {"type": "direct", "trains": blocks[:5]}
    inter_raw = await query_interline(session, from_code, to_code, date, train_types)
    if inter_raw and "Error:" not in inter_raw:
        blocks = parse_transfer_blocks(inter_raw)
        blocks = [b for b in blocks if not is_same_train_transfer(b) and filter_by_train_types(b, train_types)]
        if blocks:
            return {"type": "interline", "schemes": blocks[:3]}
    return None

def format_cached_edge(edge, from_code=None, to_code=None):
    """缓存边 -> 车次文本块。缓存中不一定存有 from/to 代码，需回退到参数。"""
    fc = edge.get('from_code') or from_code or ''
    tc = edge.get('to_code') or to_code or ''
    fn = cache_graph.station_names.get(fc, fc)
    tn = cache_graph.station_names.get(tc, tc)
    lines = [
        f"{edge.get('train_code','')} {fn}(telecode:{fc}) -> {tn}(telecode:{tc}) "
        f"{edge.get('depart_time','')} -> {edge.get('arrive_time','')} 历时：{edge.get('duration','')}",
    ]
    for seat, info in edge['seats'].items():
        lines.append(f"- {seat}: {info}")
    return '\n'.join(lines)

def extract_and_cache_edges(block, from_code, to_code, date, train_types):
    lines = block.split('\n')
    first_line = lines[0]
    match = re.match(r'^([GDCZTK]\d+)\s+.*?(\d{2}:\d{2})\s*->\s*(\d{2}:\d{2})\s+历时：(\d{2}:\d{2})', first_line)
    if not match:
        return
    train_code = match.group(1)
    depart_time = match.group(2)
    arrive_time = match.group(3)
    duration = match.group(4)
    seats = {}
    for line in lines[1:]:
        seat_match = re.match(r'-\s*(\S+):\s*(.*)', line)
        if seat_match:
            seats[seat_match.group(1)] = seat_match.group(2)
    edge_info = {
        'train_code': train_code,
        'depart_time': depart_time,
        'arrive_time': arrive_time,
        'duration': duration,
        'seats': seats
    }
    cache_graph.add_edge(from_code, to_code, edge_info, date, train_types[0] if train_types else '')

# -------------------- 票价解析（"最便宜路线"排序用）--------------------
PRICE_RE = re.compile(r'-\s*([^:：]+)[:：]\s*(.*?)(\d+(?:\.\d+)?)\s*元')

def parse_prices(block):
    """
    从车次文本块解析座席与票价。
    返回 {'min_price': 最低票价, 'seat': 席别, 'available': 是否有票, 'seats': 全部席别}
    优先在「有票」的席别中取最低价；全无票时返回最低标价且 available=False。
    """
    if not block:
        return None
    seats = []
    for line in block.split('\n'):
        m = PRICE_RE.search(line)
        if not m:
            continue
        status = m.group(2).strip()
        price = float(m.group(3))
        if price <= 0:
            # 12306 对无票额 / 不可发售的区间会返回 0 元，视为票价未知，避免被误判为"最便宜"
            continue
        seats.append({
            'seat': m.group(1).strip(),
            'status': status,
            'price': price,
            'available': ('有票' in status) or ('剩余' in status)
        })
    if not seats:
        return None
    avail = [s for s in seats if s['available']]
    best = min(avail or seats, key=lambda s: s['price'])
    return {
        'min_price': best['price'],
        'seat': best['seat'],
        'available': bool(avail),
        'seats': seats
    }

def block_min_price(block):
    """车次块最低票价；解析不到返回 None。"""
    info = parse_prices(block)
    return info['min_price'] if info else None

TRAIN_LINE_RE = re.compile(r'^\s*[GDCZTK]\d+\s')

def block_total_price(block):
    """
    官方中转方案块里包含多个车次，最低价必须按车次**求和**，否则会严重低估总价。
    返回 (总价, 是否有票)；解析不到返回 (None, None)。
    """
    if not block:
        return None, None
    sections, cur = [], None
    for line in block.split('\n'):
        if TRAIN_LINE_RE.match(line):
            if cur is not None:
                sections.append('\n'.join(cur))
            cur = [line]
        elif cur is not None:
            cur.append(line)
    if cur is not None:
        sections.append('\n'.join(cur))
    if not sections:
        sections = [block]
    total, avail, known = 0.0, False, False
    for s in sections:
        p = parse_prices(s)
        if p:
            known = True
            total += p['min_price']
            avail = avail or p['available']
    if not known:
        return None, None
    return round(total, 2), avail

def summarise_leg_price(details, leg_type='direct'):
    """
    一段的最低价：
      - direct   ：候选项是多个车次块，取其中最便宜的一班
      - interline：候选项是多个中转方案，每个方案内部多车次求和后再取最便宜
    返回 (价格, 是否有票)。
    """
    prices, avail = [], False
    for blk in (details or []):
        if leg_type == 'interline':
            price, av = block_total_price(blk)
        else:
            p = parse_prices(blk)
            price, av = (p['min_price'], p['available']) if p else (None, False)
        if price is not None:
            prices.append(price)
            avail = avail or av
    if not prices:
        return None, None
    return round(min(prices), 2), avail

# -------------------- 新增：分段拼接中转方案 --------------------
def parse_time(time_str):
    """将 'HH:MM' 转换为分钟数"""
    h, m = map(int, time_str.split(':'))
    return h * 60 + m

def extract_train_info(block):
    """从直达车次块中提取车次、出发时间、到达时间等关键信息"""
    lines = block.split('\n')
    first_line = lines[0]
    # 格式：Z326 武昌(telecode:WCN) -> 新乡(telecode:XXF) 21:17 -> 03:23 历时：06:06
    match = re.match(r'^([GDCZTK]\d+)\s+.*?(\d{2}:\d{2})\s*->\s*(\d{2}:\d{2})\s+历时：(\d{2}:\d{2})', first_line)
    if not match:
        return None
    return {
        'train_code': match.group(1),
        'depart_time': match.group(2),
        'arrive_time': match.group(3),
        'duration': match.group(4),
        'raw_block': block
    }

async def segment_combine_via(session, from_code, via_code, to_code, date, train_types):
    """
    分段查询并组合中转方案：出发站->途经站 + 途经站->目的站
    """
    # 查询第一段
    direct1_raw = await query_direct(session, from_code, via_code, date, train_types)
    if not direct1_raw or "Error:" in direct1_raw:
        return []
    blocks1 = parse_direct_blocks(direct1_raw)
    blocks1 = [b for b in blocks1 if filter_by_train_types(b, train_types)]
    if not blocks1:
        return []

    # 查询第二段
    direct2_raw = await query_direct(session, via_code, to_code, date, train_types)
    if not direct2_raw or "Error:" in direct2_raw:
        return []
    blocks2 = parse_direct_blocks(direct2_raw)
    blocks2 = [b for b in blocks2 if filter_by_train_types(b, train_types)]
    if not blocks2:
        return []

    # 提取车次信息
    trains1 = []
    for b in blocks1:
        info = extract_train_info(b)
        if info:
            info['arrive_minutes'] = parse_time(info['arrive_time'])
            trains1.append(info)
    trains2 = []
    for b in blocks2:
        info = extract_train_info(b)
        if info:
            info['depart_minutes'] = parse_time(info['depart_time'])
            trains2.append(info)

    # 组合：要求第一程到达时间早于第二程出发时间，且换乘时间 ≥ 30 分钟
    MIN_TRANSFER = 30  # 最小换乘时间（分钟）
    combined = []
    for t1 in trains1:
        for t2 in trains2:
            # 考虑跨天情况：如果到达时间小于出发时间，可能跨天了，这里简单处理为当天到达早于出发则跳过
            # 对于过夜车次，可能需要更复杂处理，但普速列车通常不会出现负间隔
            if t1['arrive_minutes'] + MIN_TRANSFER <= t2['depart_minutes']:
                transfer_wait = t2['depart_minutes'] - t1['arrive_minutes']
                wait_h = transfer_wait // 60
                wait_m = transfer_wait % 60
                wait_str = f"{wait_h}小时{wait_m}分钟" if wait_h > 0 else f"{wait_m}分钟"
                # 构造模拟的中转方案块
                scheme_lines = [
                    f"{date} {t1['depart_time']} -> {date} {t2['arrive_time']} | {from_code} -> {via_code} -> {to_code} | 同站换乘 | {wait_str} | 总历时待计算",
                    "",
                    f"        车次|出发站 -> 到达站|出发时间 -> 到达时间|历时",
                    t1['raw_block'],
                    t2['raw_block']
                ]
                combined.append('\n'.join(scheme_lines))
    return combined

# -------------------- 多站顺序换乘 (--multi) --------------------
async def segment_trains(session, from_code, to_code, date, train_types, limit=8):
    """查询一段的直达车次并解析为结构化信息（带缓存）。"""
    cached = cache_graph.get_edges(from_code, to_code, date, train_types)
    if cached:
        print(f"  使用缓存边: {from_code}->{to_code} {cached[0]['train_code']}", file=sys.stderr)
        return [{
            'train_code': e['train_code'],
            'depart_time': e['depart_time'],
            'arrive_time': e['arrive_time'],
            'duration': e['duration'],
            'raw_block': format_cached_edge(e, from_code, to_code)
        } for e in cached[:limit]]
    raw = await query_direct(session, from_code, to_code, date, train_types)
    if not raw or "Error:" in raw:
        return []
    blocks = [b for b in parse_direct_blocks(raw) if filter_by_train_types(b, train_types)]
    for b in blocks[:3]:
        extract_and_cache_edges(b, from_code, to_code, date, train_types)
    out = []
    for b in blocks[:limit]:
        info = extract_train_info(b)
        if info:
            out.append(info)
    return out


async def multi_hop_via(session, from_code, to_code, via_codes, date, train_types,
                        min_transfer=30, max_results=10):
    """
    多站顺序换乘：对 via 站点做全排列，逐段查询直达车次并拼接，
    要求相邻两段的换乘间隔 >= min_transfer 分钟。
    """
    results = []
    for perm in itertools.permutations(via_codes):
        chain = [from_code] + list(perm) + [to_code]
        seg_trains = []
        ok = True
        for a, b in zip(chain[:-1], chain[1:]):
            trains = await segment_trains(session, a, b, date, train_types)
            if not trains:
                ok = False
                break
            for t in trains:
                t['depart_minutes'] = parse_time(t['depart_time'])
                t['arrive_minutes'] = parse_time(t['arrive_time'])
            seg_trains.append(trains)
        if not ok:
            continue
        # 逐段组合，校验换乘间隔
        combos = [[t] for t in seg_trains[0]]
        for idx in range(1, len(seg_trains)):
            nxt = []
            for combo in combos:
                prev_arrive = combo[-1]['arrive_minutes']
                for t in seg_trains[idx]:
                    if prev_arrive + min_transfer <= t['depart_minutes']:
                        nxt.append(combo + [t])
            combos = nxt[:200]
            if not combos:
                break
        if not combos:
            continue
        chain_names = [cache_graph.station_names.get(c, c) for c in chain]
        for combo in combos:
            legs = []
            total_price = 0.0
            leg_available = []
            price_known = True
            for i, t in enumerate(combo):
                block = t.get('raw_block', '')
                pinfo = parse_prices(block)
                price = pinfo['min_price'] if pinfo else None
                if price is None:
                    price_known = False
                else:
                    total_price += price
                    leg_available.append(pinfo['available'])
                legs.append({
                    "from": chain_names[i],
                    "to": chain_names[i + 1],
                    "from_code": chain[i],
                    "to_code": chain[i + 1],
                    "train_code": t['train_code'],
                    "depart_time": t['depart_time'],
                    "arrive_time": t['arrive_time'],
                    "duration": t['duration'],
                    "price": price,
                    "seat": pinfo['seat'] if pinfo else None,
                    "available": pinfo['available'] if pinfo else None,
                    "raw_block": block
                })
            # 跨天车次无法从文本推断到达日期，改为累加各段历时（不含换乘等待），避免给出错误的总时长
            ride_min = 0
            for t in combo:
                d = t.get('duration', '')
                m = re.match(r'^(\d+):(\d+)$', str(d))
                if m:
                    ride_min += int(m.group(1)) * 60 + int(m.group(2))
            results.append({
                "via_order": chain_names[1:-1],
                "legs": legs,
                "total_price": round(total_price, 2) if price_known else None,
                "all_available": bool(leg_available) and all(leg_available),
                "total_duration": f"{ride_min // 60}小时{ride_min % 60}分钟",
                "note": "总历时为各段运行时间之和，不含换乘候车；实际到达日可能跨天"
            })
    # 排序：有票优先，其次按总价从低到高
    results.sort(key=lambda r: (
        0 if r['all_available'] else 1,
        r['total_price'] if r['total_price'] is not None else float('inf'),
        len(r['legs'])
    ))
    return results[:max_results]

# -------------------- 多跳规划 --------------------
ZTK_HUBS = {
    "新乡": "XXF", "郑州": "ZZF", "洛阳": "LYF", "西安": "XAY",
    "武汉": "WHN", "武昌": "WCN", "汉口": "HKN", "长沙": "CSQ",
    "株洲": "ZZQ", "衡阳": "HYQ", "怀化": "HHQ", "贵阳": "GIW",
    "昆明": "KMM", "成都": "CDW", "重庆": "CQW", "六盘水": "UMW",
    "石家庄": "SJP", "北京": "BJP", "北京西": "BXP", "驻马店": "ZDN",
    "襄阳": "XFN", "南昌": "NCG", "合肥": "HFH",
    # 补充：华南 / 西南通道枢纽
    "信阳": "XUN", "岳阳": "YYQ", "广州": "GZQ", "韶关东": "SGQ",
    "桂林": "GLZ", "柳州": "LZZ", "南宁": "NNZ",
    "遵义": "ZYE", "安顺": "ASW", "曲靖": "QJM"
}

async def auto_plan_route(session, start_station, end_station, date, train_types="ZTK", max_hops=4, force_refresh=False, top=10):
    start_code = await get_station_code(session, start_station)
    end_code = await get_station_code(session, end_station)
    if not start_code or not end_code:
        return {"error": "无法获取起点/终点代码"}
    cache_graph.update_station_name(start_code, start_station)
    cache_graph.update_station_name(end_code, end_station)

    if not force_refresh:
        cached_paths = cache_graph.find_paths(start_code, end_code, date, train_types, max_hops)
        if cached_paths:
            print(f"✅ 从缓存图中找到 {len(cached_paths)} 条路径", file=sys.stderr)
            routes = []
            for path in cached_paths[:3]:
                legs = []
                for step in path:
                    blk = format_cached_edge(step, step['from_code'], step['to_code'])
                    pinfo = parse_prices(blk)
                    legs.append({
                        "from": cache_graph.station_names.get(step['from_code'], step['from_code']),
                        "to": cache_graph.station_names.get(step['to_code'], step['to_code']),
                        "from_code": step['from_code'],
                        "to_code": step['to_code'],
                        "type": "direct",
                        "price": pinfo['min_price'] if pinfo else None,
                        "available": pinfo['available'] if pinfo else None,
                        "details": [blk]
                    })
                known = [l['price'] for l in legs if l['price'] is not None]
                routes.append({
                    "legs": legs,
                    "transfers": len(legs) - 1,
                    "total_price": round(sum(known), 2) if len(known) == len(legs) else None,
                    "all_available": all(l['available'] for l in legs)
                })
            return {
                "query_type": "auto_plan",
                "date": date,
                "from": start_station,
                "to": end_station,
                "train_types": train_types,
                "max_hops": max_hops,
                "total_routes": len(routes),
                "routes": routes,
                "cached": True
            }

    print("🔄 缓存未命中，开始实时探索...", file=sys.stderr)
    code_to_name = {v: k for k, v in ZTK_HUBS.items()}
    queue = deque()
    queue.append((start_code, []))
    visited = set([start_code])
    found_routes = []

    while queue:
        cur_code, path = queue.popleft()
        if len(path) >= max_hops: continue
        for hub_name, hub_code in ZTK_HUBS.items():
            if hub_code == cur_code: continue
            ticket_info = await get_tickets_between(session, cur_code, hub_code, date, train_types, use_cache=True)
            if not ticket_info: continue
            # 终点站不参与 visited：否则只有第一条到达终点的路径会被记录，
            # 后续所有（可能更便宜的）到达终点的路径都会被跳过。
            step = {
                "from": code_to_name.get(cur_code, cur_code),
                "to": hub_name,
                "from_code": cur_code,
                "to_code": hub_code,
                "type": ticket_info["type"],
                "details": ticket_info.get("trains") or ticket_info.get("schemes")
            }
            # 本段最低票价（direct 取最便宜车次；interline 方案内多车次求和后再取最低）
            price, avail = summarise_leg_price(step["details"], step["type"])
            step["price"] = price
            step["available"] = avail

            if hub_code == end_code:
                found_routes.append(path + [step])
                continue
            if hub_code in visited:
                continue
            visited.add(hub_code)
            queue.append((hub_code, path + [step]))

    # 组装路线：统计总价并按「有票优先 → 总价升序」排序
    route_objs = []
    for legs in found_routes:
        prices = [l.get("price") for l in legs]
        known = [p for p in prices if p is not None]
        route_objs.append({
            "legs": legs,
            "transfers": len(legs) - 1,
            "total_price": round(sum(known), 2) if len(known) == len(legs) else None,
            "all_available": all(l.get("available") for l in legs)
        })
    route_objs.sort(key=lambda r: (
        0 if r["all_available"] else 1,
        r["total_price"] if r["total_price"] is not None else float('inf'),
        r["transfers"]
    ))
    return {
        "query_type": "auto_plan",
        "date": date,
        "from": start_station,
        "to": end_station,
        "train_types": train_types,
        "max_hops": max_hops,
        "total_routes": len(route_objs),
        "routes": route_objs[:top],
        "cached": False
    }

# -------------------- 主查询（核心修改） --------------------
async def async_main(session, from_loc, to_loc, date=None, via_city=None, train_types=None, multi_cities=None, top=10):
    if date is None:
        date = await get_current_date(session)
        if not date: return {"error": "无法获取当前日期"}
    from_code = await get_station_code(session, from_loc)
    to_code = await get_station_code(session, to_loc)
    if not from_code or not to_code:
        return {"error": f"无法获取车站代码"}
    cache_graph.update_station_name(from_code, from_loc)
    cache_graph.update_station_name(to_code, to_loc)

    if multi_cities:
        codes = []
        for c in multi_cities:
            code = await get_station_code(session, c)
            if not code:
                return {"error": f"无法获取途经站代码: {c}"}
            cache_graph.update_station_name(code, c)
            codes.append(code)
        routes = await multi_hop_via(session, from_code, to_code, codes, date, train_types, max_results=top)
        return {"query_type": "multi_hop", "date": date, "from": from_loc, "to": to_loc,
                "via": multi_cities, "train_types": train_types,
                "total_routes": len(routes), "routes": routes}

    if via_city:
        # 先尝试原生中转接口
        raw = await query_interline(session, from_code, to_code, date, train_types)
        if raw and "Error:" not in raw:
            blocks = parse_transfer_blocks(raw)
            filtered = filter_by_via(blocks, via_city, exclude_same_train=False, allowed_train_types=train_types)
            if filtered:
                return {"query_type": "interline_with_via", "date": date, "from": from_loc, "to": to_loc,
                        "via": via_city, "train_types": train_types, "total_schemes": len(blocks),
                        "matched_schemes": len(filtered), "schemes": filtered}
        # 原生接口无结果（尤其是ZTK情况），降级为分段拼接
        print(f"⚠️ 原生中转无结果，尝试分段拼接...", file=sys.stderr)
        via_code = await get_station_code(session, via_city)
        if not via_code:
            return {"error": f"无法获取途经站代码: {via_city}"}
        combined = await segment_combine_via(session, from_code, via_code, to_code, date, train_types)
        if combined:
            return {"query_type": "interline_with_via", "date": date, "from": from_loc, "to": to_loc,
                    "via": via_city, "train_types": train_types, "total_schemes": len(combined),
                    "matched_schemes": len(combined), "schemes": combined, "fallback": "segmented"}
        else:
            return {"error": "未找到可拼接的中转方案"}

    # 无 via 的正常流程
    direct_raw = await query_direct(session, from_code, to_code, date, train_types)
    if direct_raw and "Error:" not in direct_raw:
        blocks = [b for b in parse_direct_blocks(direct_raw) if filter_by_train_types(b, train_types)]
        if blocks:
            return {"query_type": "direct", "date": date, "from": from_loc, "to": to_loc,
                    "train_types": train_types, "total_trains": len(blocks), "trains": blocks[:20]}
    inter_raw = await query_interline(session, from_code, to_code, date, train_types)
    if not inter_raw or "Error:" in inter_raw: return {"error": "无任何车票信息"}
    blocks = parse_transfer_blocks(inter_raw)
    blocks = [b for b in blocks if not is_same_train_transfer(b) and filter_by_train_types(b, train_types)]
    return {"query_type": "interline_fallback", "date": date, "from": from_loc, "to": to_loc,
            "train_types": train_types, "total_schemes": len(blocks), "schemes": blocks[:10]}

# -------------------- 命令行入口 --------------------
def main():
    if len(sys.argv) < 3:
        print("Usage: python train_query.py <from> <to> [--date yyyy-MM-dd] [--via <city>] [--multi <c1,c2>] [--train-type <types>] [--auto-plan] [--max-hops N] [--top N] [--refresh]")
        sys.exit(1)
    from_loc, to_loc = sys.argv[1], sys.argv[2]
    date, via_city, train_types, auto_plan, max_hops, force_refresh = None, None, None, False, 4, False
    multi_cities, top = None, 10
    args = sys.argv[3:]
    i = 0
    while i < len(args):
        if args[i] == "--date" and i+1 < len(args):
            date = args[i+1]; i+=2
        elif args[i] == "--via" and i+1 < len(args):
            via_city = args[i+1]; i+=2
        elif args[i] == "--multi" and i+1 < len(args):
            multi_cities = [c.strip() for c in re.split(r'[,，]', args[i+1]) if c.strip()]; i+=2
        elif args[i] == "--train-type" and i+1 < len(args):
            train_types = args[i+1].upper(); i+=2
        elif args[i] == "--auto-plan":
            auto_plan = True; i+=1
        elif args[i] == "--max-hops" and i+1 < len(args):
            max_hops = int(args[i+1]); i+=2
        elif args[i] == "--refresh":
            force_refresh = True; i+=1
        elif args[i] == "--top" and i+1 < len(args):
            top = int(args[i+1]); i+=2
        else:
            i+=1

    async def run():
        async with sse_client(url=MCP_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                if auto_plan:
                    return await auto_plan_route(session, from_loc, to_loc, date, train_types, max_hops, force_refresh, top)
                else:
                    return await async_main(session, from_loc, to_loc, date, via_city, train_types, multi_cities, top)

    result = asyncio.run(run())
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
