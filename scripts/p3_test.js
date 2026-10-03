const {JSDOM}=require("C:/Users/白光坤/.workbuddy/binaries/node/workspace/node_modules/jsdom");
const fs=require('fs');

function load(htmlFile, before){
  const html=fs.readFileSync(htmlFile,'utf8');
  const errs=[];
  const dom=new JSDOM(html,{runScripts:"dangerously",pretendToBeVisual:true,url:"https://citong.github.io/12306-cheapest-route/"+htmlFile});
  const W=dom.window;
  W.addEventListener('error',e=>errs.push(e.message||String(e.error)));
  if(before) before(W);
  return {W,errs};
}

function tripTests(){
  return new Promise(res=>{
    // ---- 用例1：无回填，去程卡片显示 CTA ----
    let {W,errs}=load('trip.html');
    setTimeout(()=>{
      const d=W.document;
      d.getElementById('from').value='济南';
      d.getElementById('city').value='北京';
      d.getElementById('date').value='2026-11-01';
      d.getElementById('go').dispatchEvent(new W.Event('click'));
      const tc=d.querySelector('.tcard');
      const link=tc?tc.querySelector('a.btn.sm'):null;
      console.log('[行程-无回填] 去程卡片存在:', !!tc);
      console.log('  链接文本:', link?link.textContent.trim():'(无)');
      console.log('  链接href含参数:', link? link.getAttribute('href').includes('from=')&&link.getAttribute('href').includes('to='):false);
      console.log('  href:', link?link.getAttribute('href'):'-');

      // ---- 用例2：回填匹配 ----
      let r=load('trip.html', W2=>{
        try{ W2.localStorage.setItem('irt_last_route', JSON.stringify({
          from:'济南', to:'北京', date:'2026-11-01', fromLabel:'济南', toLabel:'北京',
          price:553, transfers:0, spanMin:142, code:'G103', ts:Date.now()
        })); }catch(e){}
      });
      const d2=r.W.document;
      setTimeout(()=>{
        d2.getElementById('from').value='济南';
        d2.getElementById('city').value='北京';
        d2.getElementById('date').value='2026-11-01';
        d2.getElementById('go').dispatchEvent(new r.W.Event('click'));
        const tc2=d2.querySelector('.tcard');
        console.log('[行程-回填匹配] 去程卡片显示已查到:', !!tc2 && /已查到/.test(tc2.textContent));
        console.log('  摘要含 G103/¥553:', !!tc2 && /G103/.test(tc2.textContent) && /553/.test(tc2.textContent));
        console.log('  行程页 JS errors:', errs.concat(r.errs).length? errs.concat(r.errs).join(';') : 'none');
        res();
      },260);
    },260);
  });
}

function routeTests(){
  return new Promise(res=>{
    let {W,errs}=load('index.html');
    setTimeout(()=>{
      console.log('[路线-普通加载(无参)] JS errors:', errs.length? errs.join(';'):'none');
      // 深链：from/to/date 在 url，boot 会 applyDeepLink。jsdom 无 EventSource/LIVE，offline 分支会处理。
      let r=load('index.html',null); // 默认 url 无参
      // 模拟带参：重新构造带 search 的 dom
      const html=fs.readFileSync('index.html','utf8');
      const dom2=new JSDOM(html,{runScripts:"dangerously",pretendToBeVisual:true,
        url:"https://citong.github.io/12306-cheapest-route/index.html?from=%E6%B5%8E%E5%8D%97&to=%E5%8C%97%E4%BA%AC&date=2026-11-01"});
      const errs2=[]; dom2.window.addEventListener('error',e=>errs2.push(e.message||String(e.error)));
      setTimeout(()=>{
        console.log('[路线-深链(带参)] from输入值:', dom2.window.document.getElementById('from').value,
          '| to输入值:', dom2.window.document.getElementById('to').value);
        console.log('[路线-深链] JS errors:', errs2.length? errs2.join(';'):'none');
        res();
      },260);
    },260);
  });
}

(async()=>{
  await tripTests();
  await routeTests();
  process.exit(0);
})();
