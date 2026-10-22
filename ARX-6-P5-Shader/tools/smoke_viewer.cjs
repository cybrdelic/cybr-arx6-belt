/* Bounded real WebGL2 UBO rendering, including on macOS without GL4.3 SSBOs. */
const {chromium}=require('playwright');
const {browserOptions}=require('./browser_options.cjs');
const fs=require('fs'),path=require('path');
const {execFile}=require('child_process');
const {promisify}=require('util');
const root=path.resolve(__dirname,'..');
let browser,server,phase='launch',closing,backend;
const out=process.env.ARX_VIEWER_OUTPUT||path.join(root,'.local');
function alive(pid){try{process.kill(pid,0);return true;}catch(e){if(e.code==='ESRCH')return false;throw e;}}
async function cleanup(){
 if(closing)return closing;
 closing=(async()=>{
  if(!server)return;
  const child=server.process();
  let timer;
  await Promise.race([
   Promise.allSettled([browser?.close(),server.close()]),
   new Promise(resolve=>{timer=setTimeout(resolve,5000);})
  ]).finally(()=>clearTimeout(timer));
  if(child.exitCode===null&&alive(child.pid)){
   try{
    if(process.platform==='win32')await promisify(execFile)('taskkill',['/PID',String(child.pid),'/T','/F'],{timeout:5000});
    else await Promise.race([server.kill(),new Promise((_,reject)=>setTimeout(()=>reject(Error('Browser kill timed out')),5000))]);
   }catch(e){if(alive(child.pid))throw e;}
  }
  if(alive(child.pid))throw Error('Owned browser process remained alive after bounded teardown');
 })();
 return closing;
}
const budget=Number(process.env.ARX_VIEWER_TIMEOUT_MS||180000);
if(!Number.isFinite(budget)||budget<1000||budget>900000)throw Error('ARX_VIEWER_TIMEOUT_MS must be 1000..900000');
const timeout=setTimeout(()=>{console.error(`Robot viewer exceeded ${budget/1000} second budget during ${phase}`);cleanup().finally(()=>process.exit(1));},budget);
(async()=>{
 server=await chromium.launchServer(browserOptions());
 server.process().stderr?.on('data',data=>process.stderr.write(data));
 browser=await chromium.connect(server.wsEndpoint());
 const cdp=await browser.newBrowserCDPSession();
 const {gpu}=await cdp.send('SystemInfo.getInfo');
 backend={devices:gpu.devices,glRenderer:gpu.auxAttributes?.glRenderer,glVersion:gpu.auxAttributes?.glVersion,displayType:gpu.auxAttributes?.displayType};
 console.log('Browser graphics backend: '+JSON.stringify(backend));await cdp.detach();
 if(process.argv.includes('--context-only')){console.log('Browser launch and bounded cleanup only; shader not exercised');return;}
 const page=await browser.newPage({viewport:{width:640,height:360}});
 page.on('console',message=>{if(['warning','error'].includes(message.type()))console.error('Browser '+message.type()+': '+message.text());});
 page.on('pageerror',error=>console.error('Browser page error: '+error));
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
 fs.mkdirSync(out,{recursive:true});
 await page.locator('#canvas').screenshot({path:path.join(out,'viewer-smoke.png')});
 fs.writeFileSync(path.join(out,'viewer-smoke.json'),JSON.stringify({platform:process.platform,backend,diagnostics,scope:'One fresh WebGL2 robot frame with verified geometry table bytes; no full film or hardware qualification'},null,2));
 console.log(JSON.stringify(diagnostics));
})().catch(e=>{console.error(e);process.exitCode=1;fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'viewer-smoke.failure.json'),JSON.stringify({platform:process.platform,phase,backend,error:String(e),scope:'Failure diagnostic; not a completed rendered frame'},null,2));}).finally(async()=>{try{await cleanup();}catch(e){console.error('Browser cleanup failed',e);process.exitCode=1;}finally{clearTimeout(timeout);setTimeout(()=>process.exit(process.exitCode||0),1000).unref();}});
