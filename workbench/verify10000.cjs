const {chromium}=require('C:/Users/spide/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs');
(async()=>{
const url=process.argv[2]||'http://127.0.0.1:8769/collection-10000/index.html';
const expected=+(process.argv[3]||10000),all=process.argv.includes('--all');
const browser=await chromium.launch({channel:'msedge',headless:true}),p=await browser.newPage({viewport:{width:1440,height:1050}});
const errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.goto(url);
const ready=()=>p.waitForFunction(()=>/visible fonts loaded|Try a different filter/.test(document.querySelector('#status').textContent));
await ready();
if(await p.evaluate(()=>DATASET.length)!==expected)throw Error('Catalog size');
if(await p.locator('#count').textContent()!=='500 styles match')throw Error('Default core count');
await p.selectOption('#tier','Balanced');await ready();
if(await p.locator('#count').textContent()!=='250 styles match')throw Error('Balanced tier');
await p.selectOption('#tier','Experimental');await ready();
if(await p.locator('#count').textContent()!==(expected-750).toLocaleString()+' styles match')throw Error('Experimental tier');
await p.locator('#reset').click();await ready();
let loaded=20;
if(all){
loaded=await p.evaluate(async()=>{let n=0;for(const r of DATASET){const f=new FontFace('qa_'+r.id,'url("'+r.woff2+'")');await f.load();if(f.status!=='loaded')throw Error(r.id);n++}return n});
if(loaded!==10000)throw Error('Font load count');
}
await p.locator('#text').fill('Cafe\u0301 漢');await p.locator('#size').fill('24');
if(!(await p.locator('.sample').first().textContent()).startsWith('Café'))throw Error('NFC');
if(!(await p.locator('.warning').first().textContent()).includes('漢'))throw Error('Missing coverage warning');
if(await p.locator('.sample').first().evaluate(e=>getComputedStyle(e).fontSize)!=='24px')throw Error('Font size');
await p.selectOption('#family','relay');await p.selectOption('#weight','400');await p.selectOption('#width','5');await p.selectOption('#slant','upright');await ready();
if(await p.locator('#count').textContent()!=='2 styles match')throw Error('Combined filters');
await p.locator('.flag').first().click();await p.locator('#review-only').click();await ready();
if(await p.locator('#count').textContent()!=='1 styles match')throw Error('Review filter');
await p.locator('.flag').first().click();
await p.locator('#new-fonts').click();await ready();
if(await p.locator('#count').textContent()!==(expected-2000).toLocaleString()+' styles match')throw Error('Expansion filter');
await p.locator('#search').fill('surge edge');await ready();
if(await p.locator('#count').textContent()!==((expected-2000)/32)+' styles match')throw Error('Treatment tags');
await p.locator('#reset').click();await p.locator('#text').fill('ATTACK AT DAWN');await p.locator('#size').fill('42');await ready();
await p.locator('#next').click();await ready();
await p.waitForFunction(()=>Math.abs(scrollY-document.querySelector('#cards').offsetTop)<3);
await p.locator('#prev').click();await ready();
if(expected===10000){
 const info=await p.locator('.bundle').first().getAttribute('href');
 const response=await p.request.get(new URL(info,p.url()).href);
 if(!response.ok())throw Error('Group download failed');
 await p.evaluate(()=>scrollTo(0,document.querySelector('#cards').offsetTop));
 await p.screenshot({path:'../collection-10000/browser-preview.png'});
}
await p.setViewportSize({width:390,height:844});
if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
if(errors.length)throw Error(errors.join('\n'));
const report={catalogStyles:expected,webfontsLoaded:loaded,defaultCoreCount:500,filters:true,newExpansionFilter:true,treatmentTags:true,nfc:true,coverageWarnings:true,sizeControl:true,reviewFlags:true,paginationScroll:true,mobileOverflow:false,pageErrors:errors};
if(expected===10000)fs.writeFileSync('../collection-10000/'+(all?'browser-validation.json':'browser-interface-validation.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

