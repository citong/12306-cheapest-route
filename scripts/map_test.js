/* 验证 map.html 的运行时逻辑：
   1) 读取 localStorage['irt_last_route'] 作为“刚刚搜索的行程”；
   2) 出发地(绿)/目的地(红) 与搜索一致，且每个城市展开为全部车站（多增加站点）；
   3) 无搜索时 STOPS 为空（默认不显示出发/到达）。 */
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync(__dirname + '/../map.html', 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('FAIL: 未找到内联脚本'); process.exit(1); }
const code = m[1];

const store = {};
const localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
};
function fakeEl() {
  return {
    textContent: '', innerHTML: '', value: '', style: {},
    classList: { add() {}, remove() {} }, onclick: null, onkeydown: null,
    dataset: {}, appendChild() {}, querySelector() { return null; },
    querySelectorAll() { return []; }, children: [], addEventListener() {},
  };
}
const document = {
  getElementById: () => fakeEl(),
  createElement: () => ({ set src(v) {}, set onload(v) {}, set onerror(v) {},
    set rel(v) {}, set href(v) {}, appendChild() {} }),
  head: { appendChild() {} },
  body: { appendChild() {} },
  addEventListener() {},
};
const sandbox = { document, localStorage, console, setTimeout, clearTimeout,
  AbortSignal: undefined, fetch: () => Promise.reject(new Error('no-net')),
  JSON, Object, Array, Math, String, Number, Promise, Date };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(code, sandbox, { timeout: 5000 });

// 顶层 let 绑定（STOPS / RT_INFO）不会挂到 sandbox 上，需用 runInContext 读取
const get = (expr) => vm.runInContext(expr, sandbox, { timeout: 3000 });

let fails = 0;
const assert = (cond, msg) => { console.log((cond ? 'PASS' : 'FAIL') + ' · ' + msg); if (!cond) fails++; };

// ---- 用例 1：城市级搜索（北京 → 广州），应展开为各城市全部车站 ----
store['irt_last_route'] = JSON.stringify({ fromLabel: '北京', toLabel: '广州', ts: Date.now() });
sandbox.applySearch();
let S = get('STOPS');
let starts = S.filter(s => s.k === 'start');
let ends = S.filter(s => s.k === 'end');
assert(starts.length > 1, '北京 展开为多车站（起点 ' + starts.length + ' 个，样例 ' + starts.slice(0,4).map(s=>s.n).join('/') + '）');
assert(ends.length > 1, '广州 展开为多车站（终点 ' + ends.length + ' 个）');
assert(starts.every(s => s.k === 'start') && ends.every(s => s.k === 'end'), '起点均为 start、终点均为 end');
const rt1 = get('RT_INFO');
assert(rt1 && rt1.fromN === '北京' && rt1.toN === '广州', 'RT_INFO 记录搜索的 北京→广州');

// ---- 用例 2：车站级搜索（北京西 → 广州南），应按所属城市展开全部车站 ----
store['irt_last_route'] = JSON.stringify({ fromLabel: '北京西', toLabel: '广州南', ts: Date.now() });
sandbox.applySearch();
S = get('STOPS');
starts = S.filter(s => s.k === 'start');
ends = S.filter(s => s.k === 'end');
assert(starts.length > 1, '车站级“北京西”自动展开为北京全部车站（' + starts.length + ' 个）');
assert(ends.length > 1, '车站级“广州南”自动展开为广州全部车站（' + ends.length + ' 个）');

// ---- 用例 3：无搜索 → STOPS 为空（默认不显示出发/到达）----
store['irt_last_route'] = null;
sandbox.applySearch();
assert(get('STOPS').length === 0, '无搜索时 STOPS 为空（不显示出发/目的地）');
assert(get('RT_INFO') === null, '无搜索时 RT_INFO 为 null');

console.log(fails === 0 ? '\n全部通过 ✓' : '\n有 ' + fails + ' 项失败 ✗');
process.exit(fails === 0 ? 0 : 1);
