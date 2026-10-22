/* Final media-only checks. Never enters replay/live or compiles the shader.
 * Capture before the media rebuild: node tools/test_media_p5.cjs --capture-baseline
 * Verify after the final rebuild:   node tools/test_media_p5.cjs
 */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {spawnSync}=require('child_process');
const ROOT=path.resolve(__dirname,'..');
const ENG=path.resolve(ROOT,'../ARX-6-P5-Engineering');
const args=process.argv.slice(2);
function option(flag,fallback){const i=args.indexOf(flag);if(i<0)return fallback;if(!args[i+1]||args[i+1].startsWith('--'))throw Error('Missing value for '+flag);return path.resolve(args[i+1]);}
const HTML=option('--html',path.join(ROOT,'ARX-6-P5.html'));
const VIDEO=option('--video',path.join(ROOT,'ARX-6-P5-Inspection-1080p.mp4'));
const BASELINE=option('--baseline',path.join(ROOT,'reports/viewer-media-baseline-p5.json'));
const REPORT=option('--report',path.join(ROOT,'reports/viewer-media-tests-p5.json'));
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const readJSON=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const fileSHA=p=>sha(fs.readFileSync(p));
function canonical(x){
 if(x===null||typeof x!=='object')return JSON.stringify(x);
 if(Array.isArray(x))return '['+x.map(canonical).join(',')+']';
 return '{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}';
}
const equal=(a,b)=>canonical(a)===canonical(b);
const assetsPattern=/<script\s+type="application\/json"\s+id="assets">([\s\S]*?)<\/script>/;
function parseHTML(html){
 const m=html.match(assetsPattern);if(!m)throw Error('Embedded assets JSON is missing');
 const assets=JSON.parse(m[1]);
 const modules=[...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/g)]
  .filter(m=>/\btype\s*=\s*["']module["']/.test(m[1])).map(m=>m[2]);
 if(modules.length!==1)throw Error('Expected exactly one executable viewer module');
 const assetHashes=Object.fromEntries(Object.keys(assets).filter(k=>!['film','filmMetadata'].includes(k)).sort()
  .map(k=>[k,sha(typeof assets[k]==='string'?assets[k]:canonical(assets[k]))]));
 // Only final media payload/metadata, poster data URLs and the MP5 -> MP4
 // button-label correction may differ from the functional-test page.
 const normalized=html.replace(assetsPattern,'<script type="application/json" id="assets">__ASSETS__</script>')
  .replace(/data:image\/(?:jpeg|png|webp);base64,[A-Za-z0-9+/=]+/g,'__POSTER_DATA_URL__')
  .replace(/(<button\b[^>]*\bid=["']downloadFilm["'][^>]*>)[\s\S]*?(<\/button>)/g,'$1Save MP4$2');
 const posters=[...html.matchAll(/data:image\/(?:jpeg|png|webp);base64,([A-Za-z0-9+/=]+)/g)].map(m=>Buffer.from(m[1],'base64'));
 return {assets,modules,moduleHashes:modules.map(sha),assetHashes,normalizedShellSHA:sha(normalized),posters};
}
function sourceHashes(){
 const names=['ARX-6-P5.xml','parameters.json','controller.mjs','safety.mjs','mass_properties.json','p5_collision_proxies.json','geometry-meshes.json','spec.json','generate_cad_p2.py','results/nominal.json'];
 const out=Object.fromEntries(names.map(n=>['ARX-6-P5-Engineering/integration/'+n,fileSHA(path.join(ENG,'integration',n))]));
 out['ARX-6-P5-Shader/ARX-6-P5-Live.glsl']=fileSHA(path.join(ROOT,'ARX-6-P5-Live.glsl'));
 return out;
}
function functionalSnapshot(){
 const p=path.join(ROOT,'reports/viewer-tests-p5.json');if(!fs.existsSync(p))return null;
 const r=readJSON(p);return{path:'reports/viewer-tests-p5.json',html_sha256:r.html_sha256||null,
  literal_shader_sha256:r.literal_shader_sha256||null,physics_sha256:r.physics_sha256||null,
  passed:r.passed??null,checks_recorded:r.checks?.length||0,error:r.error||null};
}
function capture(){
 if(fs.existsSync(BASELINE)&&!args.includes('--overwrite-baseline'))throw Error('Baseline already exists; it must not be silently replaced after the media build.');
 const html=fs.readFileSync(HTML,'utf8'),p=parseHTML(html),functional=functionalSnapshot();
 if(functional?.html_sha256&&functional.html_sha256!==sha(html))throw Error('Current HTML differs from the page named by the functional-test report.');
 const baseline={revision:'P5',created_utc:new Date().toISOString(),html_path:HTML,html_sha256:sha(html),
  functional_test_observed:functional,module_sha256:p.moduleHashes,non_media_asset_sha256:p.assetHashes,
  normalized_page_shell_sha256:p.normalizedShellSHA,poster_url_count:p.posters.length,
  embedded_physics_sha256:p.assets.physicsSHA,literal_shader_sha256:p.assets.shaderSHA,
  decoded_wasm_sha256:sha(Buffer.from(p.assets.wasm,'base64')),source_file_sha256:sourceHashes(),
  media_at_capture:{film_embedded:!!p.assets.film,film_metadata:p.assets.filmMetadata},
  builder_sha256_at_capture:fileSHA(path.join(ROOT,'tools/build_viewer_p5.py')),
  allowed_changes:['assets.film','assets.filmMetadata','poster image data URLs','downloadFilm button label Save MP5 to Save MP4'],
  scope:'Identity anchor for a separate media-only check. This record does not assert that the functional test has passed.'};
 fs.mkdirSync(path.dirname(BASELINE),{recursive:true});fs.writeFileSync(BASELINE,JSON.stringify(baseline,null,2)+'\n');
 console.log(JSON.stringify({baseline:BASELINE,html_sha256:baseline.html_sha256,modules:baseline.module_sha256.length,
  non_media_asset_keys:Object.keys(baseline.non_media_asset_sha256),film_embedded:baseline.media_at_capture.film_embedded,
  functional_test_passed_at_capture:functional?.passed??null,browser_launched:false},null,2));
}
const report={revision:'P5',started_utc:new Date().toISOString(),passed:false,html_sha256:null,baseline_html_sha256:null,
 source_identity_preserved:false,checks:[],source_identity:{},media_metadata:{},film_first:{},browser_launched:false,
 environment:'Media-only Chromium check with the same ANGLE/Mesa launch configuration as the functional test. JavaScript WebGL context requests are intercepted and rejected; any request fails this test. Replay and live physics are never entered.',
 scope:'Final embedded film metadata, native P5 poster, download label, film-first behavior and identity relative to the functional-test page. Functional shader/physics/recovery results remain in their separate report.'};
function saveReport(){fs.mkdirSync(path.dirname(REPORT),{recursive:true});fs.writeFileSync(REPORT,JSON.stringify(report,null,2)+'\n');}
function check(section,name,passed,detail){const c={section,name,passed:!!passed,detail};report.checks.push(c);console.log(name,!!passed);saveReport();return c.passed;}
function probeVideo(file){
 const r=spawnSync(process.env.ARX_FFPROBE||'ffprobe',['-v','error','-select_streams','v:0','-show_entries',
  'stream=index,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,duration:format=duration,format_name','-of','json',file],
  {encoding:'utf8',timeout:30000,maxBuffer:1024*1024});
 if(r.error||r.status!==0)throw Error('ffprobe failed: '+(r.error||r.stderr));return JSON.parse(r.stdout);
}
function ratio(x){const [a,b]=String(x).split('/').map(Number);return a/(b||1);}
function posterReconstruction(file){
 const script="from PIL import Image\nfrom io import BytesIO\nimport hashlib,json,sys\nim=Image.open(sys.argv[1]); source=list(im.size); im.thumbnail((1920,1080)); b=BytesIO(); im.save(b,format='JPEG',quality=94); print(json.dumps({'source_dimensions':source,'poster_dimensions':list(im.size),'jpeg_sha256':hashlib.sha256(b.getvalue()).hexdigest()}))";
 const r=spawnSync(process.env.ARX_PYTHON||'python3',['-c',script,file],{encoding:'utf8',timeout:30000,maxBuffer:1024*1024});
 if(r.error||r.status!==0)throw Error('Native poster reconstruction failed: '+(r.error||r.stderr));return JSON.parse(r.stdout);
}
let browser;
async function verify(){
 const baseline=readJSON(BASELINE),html=fs.readFileSync(HTML,'utf8'),p=parseHTML(html),A=p.assets;
 report.html_sha256=sha(html);report.baseline_html_sha256=baseline.html_sha256;
 report.source_identity={module_sha256:p.moduleHashes,non_media_asset_sha256:p.assetHashes,
  normalized_page_shell_sha256:p.normalizedShellSHA,source_file_sha256:sourceHashes(),
  functional_test_observed_at_capture:baseline.functional_test_observed,
  functional_test_status_now:functionalSnapshot(),allowed_changes:baseline.allowed_changes};
 check('source_identity','Executable viewer module unchanged from functional-test baseline',equal(p.moduleHashes,baseline.module_sha256),{baseline:baseline.module_sha256,current:p.moduleHashes});
 check('source_identity','All non-media embedded assets unchanged',equal(p.assetHashes,baseline.non_media_asset_sha256),{keys:Object.keys(p.assetHashes),changed:Object.keys({...p.assetHashes,...baseline.non_media_asset_sha256}).filter(k=>p.assetHashes[k]!==baseline.non_media_asset_sha256[k])});
 check('source_identity','Page shell differs only by poster URLs and allowed download label',p.normalizedShellSHA===baseline.normalized_page_shell_sha256&&p.posters.length===baseline.poster_url_count,{current:p.normalizedShellSHA,baseline:baseline.normalized_page_shell_sha256,poster_urls:p.posters.length});
 check('source_identity','Physical and shader source files retain baseline hashes',equal(report.source_identity.source_file_sha256,baseline.source_file_sha256),{changed:Object.keys({...report.source_identity.source_file_sha256,...baseline.source_file_sha256}).filter(k=>report.source_identity.source_file_sha256[k]!==baseline.source_file_sha256[k])});
 check('source_identity','Embedded declared physics and literal shader identity preserved',equal(A.physicsSHA,baseline.embedded_physics_sha256)&&A.shaderSHA===baseline.literal_shader_sha256&&sha(A.shader)===A.shaderSHA&&sha(A.xml)===A.physicsSHA['ARX-6-P5.xml'],{physics_sha256:A.physicsSHA,literal_shader_sha256:A.shaderSHA});
 check('source_identity','Embedded MuJoCo WASM bytes unchanged',sha(Buffer.from(A.wasm,'base64'))===baseline.decoded_wasm_sha256,{wasm_sha256:sha(Buffer.from(A.wasm,'base64'))});
 report.source_identity_preserved=report.checks.filter(c=>c.section==='source_identity').every(c=>c.passed);
 if(!A.film)throw Error('Final MP4 is not embedded. Rebuild the viewer after the final film exists before running this verifier.');
 const embeddedFilm=Buffer.from(A.film,'base64'),filmSHA=fileSHA(VIDEO),ffprobe=probeVideo(VIDEO),stream=ffprobe.streams?.[0]||{};
 report.media_metadata={source_video:VIDEO,source_video_sha256:filmSHA,embedded_video_sha256:sha(embeddedFilm),
  embedded_bytes:embeddedFilm.length,ffprobe,embedded_film_metadata:A.filmMetadata};
 check('media_metadata','Embedded MP4 bytes exactly match the final source video',sha(embeddedFilm)===filmSHA,{source:filmSHA,embedded:sha(embeddedFilm),bytes:embeddedFilm.length});
 check('media_metadata','Source MP4 is native 1920x1080, 72 seconds and 24 fps',stream.width===1920&&stream.height===1080&&Math.abs(Number(ffprobe.format?.duration)-72)<.05&&Math.abs(ratio(stream.avg_frame_rate)-24)<1e-8&&Math.abs(ratio(stream.r_frame_rate)-24)<1e-8&&String(ffprobe.format?.format_name).includes('mp4'),{stream,format:ffprobe.format});
 if(stream.nb_frames&&stream.nb_frames!=='N/A')check('media_metadata','MP4 metadata contains 1728 video frames',Number(stream.nb_frames)===1728,{nb_frames:stream.nb_frames});
 check('media_metadata','Embedded film build metadata identifies the same final source',A.filmMetadata?.revision==='P5'&&A.filmMetadata.sha256===filmSHA&&A.filmMetadata.width===1920&&A.filmMetadata.height===1080&&A.filmMetadata.fps===24&&A.filmMetadata.duration_seconds===72&&A.filmMetadata.shader_sha256===baseline.literal_shader_sha256&&A.filmMetadata.trajectory_sha256===baseline.source_file_sha256['ARX-6-P5-Engineering/integration/results/nominal.json'],A.filmMetadata);
 const posterPath=path.join(ROOT,'ARX-6-P5-1080p.png'),still=readJSON(path.join(ROOT,'reports/still-p5.json')),
  build=readJSON(path.join(ROOT,'reports/viewer-build.json')),posterSHA=fileSHA(posterPath),reconstructed=posterReconstruction(posterPath);
 const posterJpegSHA=fileSHA(path.join(ROOT,'assets/poster.jpg'));
 report.media_metadata.poster={source_png_sha256:posterSHA,still_report:still,reconstruction:reconstructed,stored_jpeg_sha256:posterJpegSHA,embedded_jpeg_sha256:p.posters.map(sha)};
 check('media_metadata','Poster source is the native P5 1080p still at the frozen 2.5 s state',still.revision==='P5'&&still.width===1920&&still.height===1080&&still.physical_time_s===2.5&&still.file_sha256===posterSHA&&build.poster_sha256===posterSHA&&still.shader_sha256===baseline.literal_shader_sha256&&still.trajectory_sha256===baseline.source_file_sha256['ARX-6-P5-Engineering/integration/results/nominal.json']&&equal(reconstructed.source_dimensions,[1920,1080]),{still,viewer_build_poster_sha256:build.poster_sha256,source_png_sha256:posterSHA});
 check('media_metadata','Embedded posters are exact JPEG derivatives of the native P5 still',p.posters.length===2&&p.posters.every(b=>sha(b)===reconstructed.jpeg_sha256)&&posterJpegSHA===reconstructed.jpeg_sha256&&equal(reconstructed.poster_dimensions,[1920,1080]),report.media_metadata.poster);

 const {chromium}=require('playwright');
 const executable=process.env.ARX_CHROME||path.resolve(ROOT,'../../arx_browser_cache/chrome-headless-shell-linux64/chrome-headless-shell');
 browser=await chromium.launch({executablePath:executable,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--enable-gpu','--use-gl=angle','--use-angle=gl-egl','--enable-webgl','--ignore-gpu-blocklist','--disable-gpu-sandbox','--disable-web-security'],env:{...process.env,LP_NUM_THREADS:'2',LIBGL_ALWAYS_SOFTWARE:'1',EGL_PLATFORM:'surfaceless'}});
 report.browser_launched=true;
 const context=await browser.newContext({viewport:{width:1280,height:720}});
 const page=await context.newPage();page.setDefaultTimeout(30000);const errors=[],externalRequests=[];
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/i.test(r.url()))externalRequests.push(r.url());});
 // setContent writes this document without navigating away from its realm.
 // Guard the context APIs first so an accidental shader start fails quickly.
 await page.evaluate(()=>{
  window.__ARX_MEDIA_CONTEXT_REQUESTS=[];
  for(const C of [HTMLCanvasElement,typeof OffscreenCanvas==='undefined'?null:OffscreenCanvas])if(C){
   const original=C.prototype.getContext;C.prototype.getContext=function(type,...rest){
    if(/webgl/i.test(String(type))){window.__ARX_MEDIA_CONTEXT_REQUESTS.push(String(type));throw Error('Media-only verification rejects WebGL startup');}
    return original.call(this,type,...rest);
   };
  }
 });
 await page.setContent(html,{waitUntil:'domcontentloaded',timeout:30000});
 await page.waitForFunction(()=>window.ARX?.ready);
 const initial=await page.evaluate(()=>({diagnostics:ARX.diagnostics(),requests:window.__ARX_MEDIA_CONTEXT_REQUESTS,filmVisible:!document.querySelector('#film').hidden,canvasHidden:document.querySelector('#canvas').hidden,button:{text:document.querySelector('#downloadFilm').textContent.trim(),hidden:document.querySelector('#downloadFilm').hidden,disabled:document.querySelector('#downloadFilm').disabled}}));
 report.film_first.initial=initial;
 check('film_first','Final viewer opens on film without requesting WebGL or stepping physics',initial.diagnostics.mode==='film'&&initial.diagnostics.filmEmbedded&&!initial.diagnostics.webglAllocated&&!initial.diagnostics.rendererReady&&initial.diagnostics.buildCount===0&&initial.diagnostics.completedFrames===0&&initial.diagnostics.physicsStepped===0&&Array.isArray(initial.requests)&&initial.requests.length===0&&initial.filmVisible&&initial.canvasHidden,initial);
 check('film_first','Download control is visible, enabled and correctly labeled Save MP4',initial.button.text==='Save MP4'&&!initial.button.hidden&&!initial.button.disabled,initial.button);
 await page.waitForFunction(()=>{const v=document.querySelector('#film');return v.readyState>=1||!!v.error;});
 await page.waitForFunction(()=>{const i=document.querySelector('#poster');return i.complete&&i.naturalWidth>0;});
 const media=await page.evaluate(()=>{const v=document.querySelector('#film'),i=document.querySelector('#poster');return{duration:v.duration,width:v.videoWidth,height:v.videoHeight,readyState:v.readyState,currentSrcScheme:v.currentSrc.split(':')[0],error:v.error?{code:v.error.code,message:v.error.message}:null,posterWidth:i.naturalWidth,posterHeight:i.naturalHeight,posterMatchesVideo:v.poster===i.src,paused:v.paused};});
 report.media_metadata.browser=media;
 check('media_metadata','Browser loads the embedded 1920x1080, 72-second MP4 metadata',!media.error&&media.width===1920&&media.height===1080&&Math.abs(media.duration-72)<.05&&media.currentSrcScheme==='blob',media);
 check('media_metadata','Browser decodes the same native-size poster for image and video',media.posterWidth===1920&&media.posterHeight===1080&&media.posterMatchesVideo,media);
 const playback=await page.evaluate(()=>new Promise(resolve=>{
  const v=document.querySelector('#film');v.pause();v.muted=true;v.playsInline=true;
  const started=performance.now(),startTime=v.currentTime,hasFrameCallback=typeof v.requestVideoFrameCallback==='function';
  let done=false,timer=null,poll=null,frameRequest=null,frameCallbacks=0,lastFrame=null,playResolved=false,playError=null;
  const mediaError=()=>v.error?{code:v.error.code,message:v.error.message,
   kind:({1:'aborted',2:'network',3:'decode',4:'source_not_supported'})[v.error.code]||'unknown'}:null;
  function finish(reason){
   if(done)return;done=true;clearTimeout(timer);clearInterval(poll);
   if(frameRequest!==null&&typeof v.cancelVideoFrameCallback==='function')v.cancelVideoFrameCallback(frameRequest);
   v.removeEventListener('error',onError);v.pause();
   const advanced=v.currentTime-startTime,error=mediaError(),quality=typeof v.getVideoPlaybackQuality==='function'?v.getVideoPlaybackQuality():null;
   resolve({passed:reason==='decoded'&&playResolved&&!error&&!playError&&advanced>=.2&&(!hasFrameCallback||frameCallbacks>=2)&&v.paused,
    deadline_ms:15000,elapsed_ms:performance.now()-started,completion:reason,timed_out:reason==='timeout',
    start_current_time:startTime,end_current_time:v.currentTime,advanced_seconds:advanced,
    request_video_frame_callback_available:hasFrameCallback,frame_callbacks:frameCallbacks,last_frame:lastFrame,
    play_resolved:playResolved,play_error:playError,media_error:error,ready_state:v.readyState,network_state:v.networkState,
    paused_after_check:v.paused,muted:v.muted,can_play_mp4:v.canPlayType('video/mp4'),
    decoded_frame_counters:quality?{total_video_frames:quality.totalVideoFrames,dropped_video_frames:quality.droppedVideoFrames}:null});
  }
  function progress(){
   if(done)return;
   if(v.error){finish('media_error');return;}
   if(playResolved&&v.currentTime-startTime>=.2&&(!hasFrameCallback||frameCallbacks>=2))finish('decoded');
  }
  function onError(){finish('media_error');}
  function onFrame(now,metadata){
   if(done)return;frameCallbacks++;
   lastFrame={media_time:metadata.mediaTime,presented_frames:metadata.presentedFrames,width:metadata.width,height:metadata.height};
   progress();if(!done)frameRequest=v.requestVideoFrameCallback(onFrame);
  }
  v.addEventListener('error',onError);timer=setTimeout(()=>finish('timeout'),15000);poll=setInterval(progress,50);
  if(v.error){finish('media_error');return;}
  if(hasFrameCallback)frameRequest=v.requestVideoFrameCallback(onFrame);
  try{Promise.resolve(v.play()).then(()=>{playResolved=true;progress();},e=>{playError={name:e.name||'Error',message:e.message||String(e)};finish('play_rejected');});}
  catch(e){playError={name:e.name||'Error',message:e.message||String(e)};finish('play_rejected');}
 }));
 report.media_metadata.browser_playback=playback;
 check('media_playback','Muted film advances at least 0.2 seconds and presents two decoded frames when callbacks are available, then pauses',playback.passed,playback);
 await page.screenshot({path:path.join(ROOT,'reports/viewer-final-media-p5.png')});
 const final=await page.evaluate(()=>({diagnostics:ARX.diagnostics(),requests:window.__ARX_MEDIA_CONTEXT_REQUESTS}));report.film_first.final=final;
 check('film_first','Media metadata and playback checks complete with zero WebGL requests and zero physics steps',final.requests.length===0&&!final.diagnostics.webglAllocated&&!final.diagnostics.rendererReady&&final.diagnostics.completedFrames===0&&final.diagnostics.buildCount===0&&final.diagnostics.physicsStepped===0,final);
 check('film_first','No uncaught page errors or external network requests',errors.length===0&&externalRequests.length===0,{errors,externalRequests});
 check('source_identity','HTML, video and physical source files stayed unchanged during verification',fileSHA(HTML)===report.html_sha256&&fileSHA(VIDEO)===filmSHA&&equal(sourceHashes(),baseline.source_file_sha256),{html_sha256:fileSHA(HTML),video_sha256:fileSHA(VIDEO)});
 report.source_identity_preserved=report.checks.filter(c=>c.section==='source_identity').every(c=>c.passed);
 report.passed=report.checks.every(c=>c.passed);report.completed_utc=new Date().toISOString();saveReport();
 await browser.close();browser=null;
 console.log(JSON.stringify({report:REPORT,passed:report.passed,html_sha256:report.html_sha256,baseline_html_sha256:report.baseline_html_sha256,source_identity_preserved:report.source_identity_preserved,checks:report.checks.length},null,2));
 if(!report.passed)process.exitCode=1;
}
if(args.includes('--capture-baseline')){
 try{capture();}catch(e){console.error(e.stack||e);process.exitCode=1;}
}else{
 verify().catch(async e=>{report.error=String(e.stack||e);report.passed=false;report.completed_utc=new Date().toISOString();saveReport();console.error(e);if(browser)await browser.close();process.exitCode=1;});
}
