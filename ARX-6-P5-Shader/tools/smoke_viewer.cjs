/* Bounded real WebGL2 UBO rendering, including on macOS without GL4.3 SSBOs. */
const {chromium}=require('playwright');
const {browserOptions}=require('./browser_options.cjs');
const fs=require('fs'),path=require('path');
const {execFile}=require('child_process');
const {promisify}=require('util');
const root=path.resolve(__dirname,'..');
let browser,server,phase='launch',closing;
async function cleanup(){
 if(closing)return closing;
 closing=(async()=>{
  if(!server)return;
  const child=server.process();
  await Promise.race([server.close().catch(()=>{}),new Promise(resolve=>setTimeout(resolve,5000))]);
  if(child.exitCode===null){
   if(process.platform==='win32')await promisify(execFile)('taskkill',['/PID',String(child.pid),'/T','/F']);
   else await server.kill();
  }
 })();
 return closing;
}
const budget=Number(process.env.ARX_VIEWER_TIMEOUT_MS||180000);
if(!Number.isFinite(budget)||budget<1000||budget>900000)throw Error('ARX_VIEWER_TIMEOUT_MS must be 1000..900000');
const timeout=setTimeout(()=>{console.error(`Robot viewer exceeded ${budget/1000} second budget during ${phase}`);cleanup().finally(()=>process.exit(1));},budget);
(async()=>{
 server=await chromium.launchServer(browserOptions());
 browser=await chromium.connect(server.wsEndpoint());
 if(process.argv.includes('--context-only')){console.log('Browser launch and bounded cleanup only; shader not exercised');return;}
 const page=await browser.newPage({viewport:{width:640,height:360}});
 page.setDefaultTimeout(budget-500);
 phase='load';
 await page.setContent(fs.readFileSync(path.join(root,'ARX-6-P5.html'),'utf8'),{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.ARX?.ready);
 phase='compile-and-first-frame';console.log(phase);
 await page.evaluate(()=>{document.querySelector('#resolution').value='256';return ARX.enterMode('replay');});
 const diagnostics=await page.evaluate(()=>ARX.diagnostics());
 if(!diagnostics.rendererReady||diagnostics.completedFrames<1||!diagnostics.numericTables?.readbackVerified)throw Error(JSON.stringify(diagnostics));
 phase='seek-and-readback';console.log(phase);await page.evaluate(()=>ARX.renderAt(2.5));
 const pixels=await page.evaluate(()=>ARX.readPixels());
 const raw=Buffer.from(pixels.rgbaBottomUp,'base64');
 let low=255,high=0;for(let i=0;i<raw.length;i++)if(i%4!==3){low=Math.min(low,raw[i]);high=Math.max(high,raw[i]);}
 if(!raw.length||high===low)throw Error('Blank render readback');
 const out=process.env.ARX_VIEWER_OUTPUT||path.join(root,'.local');fs.mkdirSync(out,{recursive:true});
 await page.locator('#canvas').screenshot({path:path.join(out,'viewer-smoke.png')});
 fs.writeFileSync(path.join(out,'viewer-smoke.json'),JSON.stringify({platform:process.platform,diagnostics,scope:'One fresh WebGL2 robot frame with verified geometry table bytes; no full film or hardware qualification'},null,2));
 console.log(JSON.stringify(diagnostics));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{try{await cleanup();}catch(e){console.error('Browser cleanup failed',e);process.exitCode=1;}finally{clearTimeout(timeout);}});
