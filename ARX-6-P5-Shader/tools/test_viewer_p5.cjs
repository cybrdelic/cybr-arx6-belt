/* Behavioral checks for the delivered offline film / inspection / physics UI. */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const ROOT=path.resolve(__dirname,'..');
const executable=process.env.ARX_CHROME||path.resolve(ROOT,'../../arx_browser_cache/chrome-headless-shell-linux64/chrome-headless-shell');
const functionalOnly=process.argv.includes('--functional-only');
let browser,page,phase='launch',phaseStarted=Date.now();
const errors=[],consoleErrors=[];
const report={revision:'P5',checks:[],environment:'Headless Chromium with ANGLE on Mesa EGL/llvmpipe software WebGL. This checks desktop rendering and an emulated mobile viewport, not a physical Android GPU. The SwiftShader driver exceeded this workspace resource budget during startup.'};
function check(name,ok,detail){report.checks.push({name,passed:!!ok,detail});console.log(name,!!ok);fs.writeFileSync(path.join(ROOT,'reports/viewer-tests-p5.json'),JSON.stringify(report,null,2));}
function setPhase(name){phase=name;phaseStarted=Date.now();report.phase=name;report.phase_started_at=new Date().toISOString();console.log('Phase:',name,report.phase_started_at);}
async function failureDiagnostics(){
 if(!page||page.isClosed())return{page_closed:true};
 let timer;
 try{return await Promise.race([
  page.evaluate(()=>({diagnostics:window.ARX?.diagnostics?.(),error:window.ARX_ERROR||null,ui:Object.fromEntries(['loadtitle','loadmessage','notice','status','progress'].map(id=>[id,document.getElementById(id)?.textContent])),overlay_hidden:document.getElementById('overlay')?.hidden,retry_hidden:document.getElementById('retry')?.hidden})).catch(e=>({diagnostic_error:String(e)})),
  new Promise(resolve=>{timer=setTimeout(()=>resolve({diagnostic_timeout_seconds:10}),10000);})
 ]);}finally{clearTimeout(timer);}
}
(async()=>{
 browser=await chromium.launch({executablePath:executable,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-gpu','--use-gl=angle','--use-angle=gl-egl','--enable-webgl','--ignore-gpu-blocklist','--disable-gpu-sandbox','--disable-web-security'],env:{...process.env,LP_NUM_THREADS:'2',LIBGL_ALWAYS_SOFTWARE:'1',EGL_PLATFORM:'surfaceless'}});
 page=await browser.newPage({viewport:{width:1280,height:720}});page.setDefaultTimeout(180000);page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error'){consoleErrors.push(m.text());if(consoleErrors.length>50)consoleErrors.shift();}});
 const html=fs.readFileSync(path.join(ROOT,'ARX-6-P5.html'),'utf8');report.html_sha256=crypto.createHash('sha256').update(html).digest('hex');
 const embedded=JSON.parse(html.match(/<script type="application\/json" id="assets">([\s\S]*?)<\/script>/)[1]);
 fs.writeFileSync(path.join(ROOT,'reports/browser-parity-shader.glsl'),embedded.shader);
 report.literal_shader_sha256=embedded.shaderSHA;report.physics_sha256=embedded.physicsSHA;
 await page.setContent(html,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>window.ARX?.ready);
 let d=await page.evaluate(()=>ARX.diagnostics());check('Film starts without a WebGL allocation',d.mode==='film'&&!d.webglAllocated,d);
 if(!functionalOnly){const media=await page.evaluate(async()=>{const v=document.querySelector('video');if(v.src&&v.readyState<1)await new Promise((resolve,reject)=>{v.addEventListener('loadedmetadata',resolve,{once:true});v.addEventListener('error',()=>reject(new Error(v.error?.message)),{once:true});});return{src:!!v.src,duration:v.duration,width:v.videoWidth,height:v.videoHeight};});
 check('Embedded inspection film loads with native 1080p metadata',media.src&&media.width===1920&&media.height===1080&&Math.abs(media.duration-72)<.05,media);}
 await page.screenshot({path:path.join(ROOT,'reports/viewer-film.png')});
 await page.evaluate(()=>{document.querySelector('#resolution').value='256';});
 setPhase('initial_shader_startup');await page.evaluate(()=>ARX.enterMode('replay'));report.initial_shader_startup_seconds=(Date.now()-phaseStarted)/1000;d=await page.evaluate(()=>ARX.diagnostics());check('Fresh shader compiles and renders',d.rendererReady&&d.completedFrames>=1,d);
 if(!d.rendererReady)throw Error(d.lastError||'Renderer did not start');
 check('Exact numeric geometry buffers pass driver byte readback',d.numericTables?.readbackVerified,d.numericTables);
 await page.evaluate(()=>ARX.renderAt(2.5));
 fs.writeFileSync(path.join(ROOT,'reports/browser-parity-frame.json'),JSON.stringify(await page.evaluate(()=>({pixels:ARX.readPixels(),state:ARX.state().frame,diagnostics:ARX.diagnostics()}))));
 await page.evaluate(()=>ARX.inspect(2,0,.55,true));await page.screenshot({path:path.join(ROOT,'reports/viewer-shoulder.png')});
 const grouped=await page.locator('#canvas').screenshot();await page.evaluate(()=>{const sel=document.querySelector('#part');const p=Number(sel.options[1].value);return ARX.inspect(2,p,0,false);});
 const isolated=await page.locator('#canvas').screenshot();check('Individual exact-part isolation changes the rendered image',!grouped.equals(isolated));
 await page.evaluate(()=>ARX.inspect(0,0,0,false));const initial=await page.evaluate(()=>ARX.state().frame);await page.evaluate(()=>ARX.renderAt(6.25));const later=await page.evaluate(()=>ARX.state().frame);check('Replay seeks to a different recorded physical state',Math.abs(later[0]-6.25)<.001&&initial[1]!==later[1]);
 await page.evaluate(()=>ARX.enterMode('live'));const state=await page.evaluate(()=>ARX.state().frame);check('Live P5 solver starts at 2.5 s',Math.abs(state[0]-2.5)<.002);
 await page.evaluate(()=>ARX.step(24));const stepped=await page.evaluate(()=>ARX.state().frame);check('Live physical state advances',stepped[0]>state[0]);
 await page.evaluate(()=>ARX.testLoseContext());await page.waitForFunction(()=>ARX.diagnostics().lossCount===1);d=await page.evaluate(()=>ARX.diagnostics());check('Context loss returns to film and pauses physics',d.mode==='film'&&d.contextLost,d);
 await page.evaluate(()=>ARX.testRestoreContext());await page.waitForFunction(()=>ARX.diagnostics().restoreCount===1);const restored=await page.evaluate(()=>ARX.state().frame);check('Context restoration preserves every physical field',JSON.stringify(restored)===JSON.stringify(stepped));
 setPhase('context_recovery');report.context_recovery_timeout_seconds=900;
 await page.click('#retry');await page.waitForFunction(()=>{if(window.ARX_ERROR)throw Error(window.ARX_ERROR);return ARX.diagnostics().mode==='live'&&ARX.diagnostics().rendererReady&&document.querySelector('#overlay').hidden;},null,{timeout:900000});report.context_recovery_seconds=(Date.now()-phaseStarted)/1000;d=await page.evaluate(()=>ARX.diagnostics());check('Reduced-load retry rebuilds GPU resources',d.longEdge<=256&&d.samples===1&&d.buildCount>=2,d);
 check('Recovered renderer retains every physical field',JSON.stringify(await page.evaluate(()=>ARX.state().frame))===JSON.stringify(stepped));setPhase('normal_stop_and_mobile');
 await page.evaluate(()=>{ARX.sim().setOptions({normalStopTime:ARX.sim().data.time});return ARX.step(600);});check('Normal stop responds in the live solver',(await page.evaluate(()=>ARX.state().telemetry.mode))==='CONTROLLED_STOP');
 await page.evaluate(()=>ARX.showFilm());check('No uncaught browser errors',errors.length===0,errors);
 const mobile=await browser.newPage({viewport:{width:412,height:915},deviceScaleFactor:3,isMobile:true,hasTouch:true,userAgent:'Mozilla/5.0 (Linux; Android 17) AppleWebKit/537.36 Chrome/156.0.0.0 Mobile Safari/537.36'});await mobile.setContent(html,{waitUntil:'domcontentloaded'});await mobile.waitForFunction(()=>window.ARX?.ready);const mobileDefaults=await mobile.evaluate(()=>({resolution:Number(document.querySelector('#resolution').value),samples:Number(document.querySelector('#samples').value),allocated:ARX.diagnostics().webglAllocated}));check('Mobile starts on film with capped single-sample shader defaults',mobileDefaults.resolution<=320&&mobileDefaults.samples===1&&!mobileDefaults.allocated,mobileDefaults);await mobile.screenshot({path:path.join(ROOT,'reports/viewer-mobile-film.png')});
 report.passed=report.checks.every(x=>x.passed);report.phase='complete';report.console_errors=consoleErrors;fs.writeFileSync(path.join(ROOT,'reports/viewer-tests-p5.json'),JSON.stringify(report,null,2));await browser.close();if(!report.passed)process.exitCode=1;
})().catch(async e=>{report.error=String(e.stack||e);report.passed=false;report.failure_phase=phase;report.failure_phase_elapsed_seconds=(Date.now()-phaseStarted)/1000;report.failure_diagnostics=await failureDiagnostics();report.page_errors=errors;report.console_errors=consoleErrors;fs.writeFileSync(path.join(ROOT,'reports/viewer-tests-p5.json'),JSON.stringify(report,null,2));console.error(e);if(browser)await browser.close();process.exitCode=1;});
