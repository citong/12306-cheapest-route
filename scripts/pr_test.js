// 验证行程页「偏好设置」真正生效：
//  1) 点击偏好标签即重渲染（不需要再点「生成行程」）
//  2) 偏好改变会改变入选景点集合（命中条 & KPI 安排景点数变化）
//  3) ★ 偏好徽标只出现在命中偏好的景点上（遍历所有天数面板后统计）
const {JSDOM}=require("C:/Users/白光坤/.workbuddy/binaries/node/workspace/node_modules/jsdom");
const fs=require('fs');
const html=fs.readFileSync('trip.html','utf8');

function prefbar(d){
  const out=d.getElementById('out');
  const pb=out.querySelector('.prefbar');
  const hit=(pb && /命中\s*<b>(\d+)<\/b>/.exec(pb.innerHTML)) ? +RegExp.$1 : -1;
  const total=(pb && /本城\s*(\d+)\s*个景点/.exec(pb.textContent)) ? +RegExp.$1 : -1;
  const tags=[...out.querySelectorAll('.prefbar .ptag')].map(e=>e.textContent);
  return {hit, total, tags};
}

// 遍历所有天数 tab，统计全部面板上出现的 ★ 徽标数（默认只渲染第 1 天）
function allDayStars(d){
  const out=d.getElementById('out');
  const tabs=[...out.querySelectorAll('#tabs .tab')];
  let stars=0;
  tabs.forEach(t=>{
    t.dispatchEvent(new W.Event('click'));
    stars+=out.querySelectorAll('#daypanel .b-hit').length;
  });
  return stars;
}

function chip(d,t){ return [...d.querySelectorAll('.tg')].find(e=>e.dataset.t===t); }

const dom=new JSDOM(html,{runScripts:"dangerously",pretendToBeVisual:true,url:"https://x/trip.html"});
const W=dom.window, errs=[];
W.addEventListener('error',e=>errs.push(e.message));
setTimeout(()=>{
  const d=W.document;
  d.getElementById('city').value='北京';
  d.getElementById('days').value='3';
  d.getElementById('go').dispatchEvent(new W.Event('click'));
  const a=Object.assign(prefbar(d),{stars:allDayStars(d)});
  console.log('默认(必去/美食/自然): 安排景点命中=%d/%d 徽标=%d 偏好=%j',
    a.hit,a.total,a.stars,a.tags);

  // 只保留「美食」——不点「生成行程」，仅点标签
  ['必去','自然'].forEach(t=>{ const c=chip(d,t); if(c) c.dispatchEvent(new W.Event('click')); });
  const b=Object.assign(prefbar(d),{stars:allDayStars(d)});
  console.log('仅美食:            安排景点命中=%d/%d 徽标=%d 偏好=%j',
    b.hit,b.total,b.stars,b.tags);

  // 取消全部偏好 -> 显示全部
  ['美食'].forEach(t=>{ const c=chip(d,t); if(c) c.dispatchEvent(new W.Event('click')); });
  const c2=Object.assign(prefbar(d),{stars:allDayStars(d)});
  console.log('无偏好:            安排景点命中=%d/%d 徽标=%d 偏好=%j',
    c2.hit,c2.total,c2.stars,c2.tags);

  const pass=[];
  pass.push(['点击标签即重渲染(无需点生成)', a.tags.join()!==b.tags.join()]);
  pass.push(['偏好改变入选数量', b.hit!==a.hit]);
  pass.push(['取消偏好后恢复全部', c2.hit===0]);
  pass.push(['命中数随偏好变化', a.hit!==b.hit]);
  pass.push(['★徽标数=命中数(只给命中项)', a.stars===a.hit && b.stars===b.hit && c2.stars===0]);
  pass.push(['无JS报错', errs.length===0]);
  console.log('\n--- 断言 ---');
  let bad=0;
  pass.forEach(([n,ok])=>{ console.log((ok?'PASS':'FAIL')+'  '+n); if(!ok) bad++; });
  if(errs.length) console.log('errors:', errs.join(';'));
  process.exit(bad?1:0);
},300);
