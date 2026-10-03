// trip.html 运行时冒烟测试：node trip_test.js
const {JSDOM}=require("C:/Users/白光坤/.workbuddy/binaries/node/workspace/node_modules/jsdom");
const fs=require('fs');
const html=fs.readFileSync('trip.html','utf8');
const errs=[];
const dom=new JSDOM(html,{runScripts:"dangerously",pretendToBeVisual:true});
dom.window.addEventListener('error',e=>errs.push(e.message));
setTimeout(()=>{
  const d=dom.window.document, W=dom.window;
  console.log('可选城市        :', d.getElementById('city').options.length);
  d.getElementById('city').value='丽江';
  d.getElementById('days').value='4';
  d.getElementById('go').dispatchEvent(new W.Event('click'));
  console.log('城市封面图      :', !!d.querySelector('.hero img'));
  console.log('封面标题        :', d.querySelector('.hero h2').textContent,
              '| 简介长度:', (d.querySelector('.hero .hintro').textContent||'').length);
  console.log('KPI             :', [...d.querySelectorAll('.kpi b')].map(x=>x.textContent).join(' / '));
  const tabs=[...d.querySelectorAll('#tabs .tab')];
  console.log('天数tab         :', tabs.length);
  tabs.forEach((t,i)=>{
    t.dispatchEvent(new W.Event('click'));
    const spots=d.querySelectorAll('#daypanel .ti').length;
    const imgs=d.querySelectorAll('#daypanel img.sph').length;
    const trans=d.querySelectorAll('#daypanel .transit').length;
    const meals=d.querySelectorAll('#daypanel .meal').length;
    const notes=d.querySelectorAll('#daypanel .note').length;
    const end=((d.querySelector('#daypanel .dayend')||{}).textContent||'').trim();
    console.log('  第'+(i+1)+'天: 景点'+spots+' 图'+imgs+' 交通段'+trans+' 用餐'+meals+' 贴士'+notes+' | '+end.slice(0,50));
  });
  console.log('预算明细行      :', d.querySelectorAll('.blk .price').length);
  console.log('预算合计        :', (d.querySelector('.price.total b')||{}).textContent);
  console.log('行前清单条数    :', d.querySelectorAll('.blk ul li').length);
  console.log('住宿链接        :', !!d.querySelector('.hotel a'));
  // 遍历所有城市，确保都能出图且不报错
  let noImg=[], bad=[];
  [...d.getElementById('city').options].forEach(o=>{
    d.getElementById('city').value=o.value;
    d.getElementById('go').dispatchEvent(new W.Event('click'));
    if(!d.querySelector('.hero img')) noImg.push(o.value);
    if(!d.querySelectorAll('#daypanel .ti').length) bad.push(o.value);
  });
  console.log('无封面图城市    :', noImg.length?noImg:'无');
  console.log('出行程异常城市  :', bad.length?bad:'无');
  console.log('JS errors      :', errs.length?errs:'none');
  process.exit(0);
},500);
