const {JSDOM}=require("C:/Users/白光坤/.workbuddy/binaries/node/workspace/node_modules/jsdom");
const fs=require('fs');
const html=fs.readFileSync('trip.html','utf8');

function run(withL){
  return new Promise(res=>{
    const errs=[];
    const dom=new JSDOM(html,{runScripts:"dangerously",pretendToBeVisual:true});
    const W=dom.window;
    if(withL){
      W.__calls={map:0,marker:0,polyline:0,tile:0};
      W.L={
        map:()=>{ W.__calls.map++; const m={setView:()=>m,addTo:()=>{},on:()=>{},fitBounds:()=>{},invalidateSize:()=>{}}; return m; },
        tileLayer:()=>{ W.__calls.tile++; const t={addTo:()=>t,on:()=>t}; return t; },
        marker:()=>{ W.__calls.marker++; const k={addTo:()=>k,bindTooltip:()=>k}; return k; },
        polyline:()=>{ W.__calls.polyline++; const p={addTo:()=>p}; return p; }
      };
    }
    W.addEventListener('error',e=>errs.push(e.message));
    setTimeout(()=>{
      const d=W.document;
      d.getElementById('city').value='北京';
      d.getElementById('days').value='3';
      d.getElementById('go').dispatchEvent(new W.Event('click'));
      const tabs=[...d.querySelectorAll('#tabs .tab')];
      tabs.forEach(t=> t.dispatchEvent(new W.Event('click')));
      // 等所有 setTimeout(0) 与 invalidateSize 的 40ms timer 完成
      setTimeout(()=>{
        const ds=d.getElementById('daysmall');
        const merr=ds.querySelector('.merr').style.display;
        if(withL){
          console.log('[有L=true] 最终 merr.display=', merr||'(空/已出图)',
            '| L调用:', JSON.stringify(W.__calls));
        } else {
          console.log('[有L=false] 最终 merr.display=', merr||'(空)',
            '<-- 应为 flex');
        }
        console.log('  JS errors:', errs.length? errs.join(';') : 'none');
        res();
      },120);
    },350);
  });
}
(async()=>{
  console.log('== 路径A：无 Leaflet（离线容错）==');
  await run(false);
  console.log('== 路径B：有 Leaflet（正常出图）==');
  await run(true);
  process.exit(0);
})();
