/* Exercise actual generated lifecycle functions with a deterministic WebGL fake.
 * This proves resource ownership and failure recovery, not GPU rendering. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'../source/player-p5.html'),'utf8');
function section(start,end){
 const a=html.indexOf(start),b=html.indexOf(end,a);
 assert(a>=0&&b>a,'Generated viewer lifecycle hooks missing');return html.slice(a,b);
}
const lifecycle=section('function resetRendererMetadata()','function recordedState(');
const waitsAndEvents=section('function abortIfChanged(','function bindCanvas(');
let nextContext=0;
function fakeGL(fault=null){
 const owner=++nextContext,objects=[],deleted=[],waiters=[];
 const state={owner,objects,deleted,waiters,fault,lost:false,probeWaiting:false,boundBuffer:null};
 const create=type=>{const object={owner,type,live:true};objects.push(object);return object;};
 const remove=(type,object)=>{
  assert.equal(object.owner,owner,'Wrong context deleted an object');
  assert.equal(object.type,type);assert(object.live,'Double delete or stale handle');
  object.live=false;deleted.push(object);
 };
 const methods={
  isContextLost:()=>state.lost,
  createShader:type=>{const s=create('shader');s.shaderType=type;return s;},
  compileShader:s=>{if(state.fault==='fragmentCompile'&&s.shaderType==='FRAGMENT_SHADER')throw Error('Injected fragment compile error');},
  createProgram:()=>create('program'),createVertexArray:()=>create('vao'),
  createBuffer:()=>create('buffer'),createTexture:()=>create('texture'),createFramebuffer:()=>create('fbo'),
  fenceSync:()=>create('sync'),
  deleteShader:s=>remove('shader',s),deleteProgram:p=>remove('program',p),
  deleteVertexArray:v=>remove('vao',v),deleteBuffer:b=>remove('buffer',b),
  deleteTexture:t=>remove('texture',t),deleteFramebuffer:f=>remove('fbo',f),deleteSync:s=>remove('sync',s),
  getExtension:name=>name==='KHR_parallel_shader_compile'?{COMPLETION_STATUS_KHR:'COMPLETE'}:null,
  getProgramParameter:(p,key)=>key==='COMPLETE'?!['compileTimeout','compilePending'].includes(state.fault):state.fault!=='link',
  getProgramInfoLog:()=> 'Injected link error',getShaderInfoLog:()=>'',
  getParameter:key=>key==='MAX_UNIFORM_BLOCK_SIZE'?65536:12,
  getUniformBlockIndex:(p,name)=>Number(name.slice(-1)),getActiveUniformBlockParameter:()=>16,
  bindBuffer:(target,buffer)=>{state.boundBuffer=buffer;},
  bufferData:(target,bytes)=>{state.boundBuffer.bytes=new Uint8Array(bytes);},
  getBufferSubData:(target,offset,out)=>{out.set(state.boundBuffer.bytes);if(state.fault==='upload')out[0]^=1;},
  checkFramebufferStatus:()=>state.fault==='framebuffer'?'INCOMPLETE':'FRAMEBUFFER_COMPLETE',
  clientWaitSync:()=>{state.probeWaiting=true;return ['probeTimeout','probePending'].includes(state.fault)?'TIMEOUT_EXPIRED':'CONDITION_SATISFIED';},
  getUniformLocation:()=>({}),
 };
 const gl=new Proxy(methods,{get(target,key){
  if(key in target)return target[key];
  if(/^[A-Z_]+$/.test(key))return key;
  return ()=>{};
 }});
 state.gl=gl;state.live=()=>objects.filter(x=>x.live);
 state.lose=()=>{state.lost=true;for(const object of state.live())object.live=false;};
 return state;
}
function fixture(initial){
 const elements=new Map();let clock=0,current=initial;
 const blocks=[0,1].map(i=>({name:'Block'+i,binding:i,base64:Buffer.alloc(16,i+1).toString('base64')}));
 const test={context:initial.gl,pauseGate:null,
  pause(){if(test.pauseGate)return new Promise(resolve=>test.pauseGate.push(resolve));
   if(current.fault==='probePending'&&current.probeWaiting)return new Promise(resolve=>current.waiters.push(resolve));return Promise.resolve();},
  sleep(){return current.fault==='compilePending'?new Promise(resolve=>current.waiters.push(resolve)):Promise.resolve();},
  now(){clock+=['compileTimeout','probeTimeout'].includes(current.fault)?400001:1;return clock;},
 };
 const context=vm.createContext({TEST:test,console,Uint8Array,performance:{now:test.now},window:{},
  A:{shader:'reference',webglNumeric:{variants:[{maximum_block_bytes:65536,block_count:2,source:'reference',blocks}]}},
  bytes64:s=>new Uint8Array(Buffer.from(s,'base64')),
  $:id=>{if(!elements.has(id))elements.set(id,{});return elements.get(id);},
 });
 vm.runInContext(`
 let gl=TEST.context,program=null,vao=null,fbo=null,colorTarget=null,U={},rendererResources=null;
 let renderReady=false,compilePromise=null,contextSerial=1,width=0,height=0,dirty=false;
 let buildCount=0,drawCalls=0,probeCount=0,lossCount=0,restoreCount=0,lastClock=0;
 let sim=null,lastLossState=null,restoredState=null,lastShaderMode='replay',mode='replay',maxPixelsPerSubmission=16384;
 const canvas={},pauseRAF=()=>TEST.pause(),sleep=()=>TEST.sleep();
 const createContext=()=>{},recordedState=()=>[],uploadState=()=>{},showFilm=()=>{};
 ${waitsAndEvents}
 ${lifecycle}
 globalThis.api={compile,disposeRenderer,
  snapshot:()=>({renderReady,program,vao,resources:rendererResources,promise:compilePromise,buffers:numericTableBuffers.length,selected:selectedNumericTables,readback:numericTableReadbackVerified,width,height,contextSerial}),
  invalidate:(next,restore)=>{handleLost({preventDefault(){}});gl=next;restore();handleRestored();},
 };
 `,context);
 return {api:context.api,test,replace(next){current.lose();context.api.invalidate(next.gl,()=>{current=next;next.lost=false;});}};
}
async function until(predicate){for(let i=0;i<30;i++){if(predicate())return;await Promise.resolve();}assert.fail('Deterministic async checkpoint was not reached');}
const checks=[];
async function check(name,fn){await fn();checks.push({name,passed:true});}
(async()=>{
 for(const fault of ['fragmentCompile','link','compileTimeout','upload','framebuffer','probeTimeout']){
  await check(fault+' releases every partial allocation and retries',async()=>{
   const ctx=fakeGL(fault),{api}=fixture(ctx);
   await assert.rejects(api.compile());assert.equal(ctx.live().length,0,'Failure retained GPU allocations');
   const failed=api.snapshot();assert.equal(failed.program,null);assert.equal(failed.vao,null);
   assert.equal(failed.resources,null);assert.equal(failed.promise,null);assert.equal(failed.buffers,0);
   assert.equal(failed.selected,null);assert.equal(failed.readback,false);assert.equal(failed.renderReady,false);
   ctx.fault=null;await api.compile();assert.equal(api.snapshot().renderReady,true);assert.equal(api.snapshot().readback,true);
   assert.deepEqual(ctx.live().map(x=>x.type).sort(),['buffer','buffer','fbo','program','texture','vao']);
   const count=ctx.objects.length;await api.compile();assert.equal(ctx.objects.length,count,'Healthy renderer was rebuilt');
   api.disposeRenderer();assert.equal(ctx.live().length,0);api.disposeRenderer();
  });
 }
 for(const stage of ['compilePending','probePending'])for(const sameObject of [false,true]){
  await check('stale '+stage+' attempt cannot dispose '+(sameObject?'restored':'replacement')+' context or clear its promise',async()=>{
   const old=fakeGL(stage),f=fixture(old);
   const first=f.api.compile(),firstRejected=assert.rejects(first,{name:'AbortError'});
   await until(()=>old.waiters.length===1);
   const wakeOld=old.waiters.shift(),next=sameObject?old:fakeGL();
   f.replace(next);next.fault='probePending';next.probeWaiting=false;
   const second=f.api.compile();await until(()=>next.waiters.length===1);
   const pending=f.api.snapshot().promise,resources=f.api.snapshot().resources,live=next.live().slice(),deletes=next.deleted.length;
   wakeOld();await firstRejected;
   assert.equal(f.api.snapshot().promise,pending);assert.equal(f.api.snapshot().resources,resources);
   assert.deepEqual(next.live(),live);assert.equal(next.deleted.length,deletes,'Stale task deleted a new resource');
   next.fault=null;next.waiters.shift()();await second;assert.equal(f.api.snapshot().renderReady,true);
   f.api.disposeRenderer();assert.equal(next.live().length,0);
  });
 }
 await check('context change before first allocation aborts without touching new context',async()=>{
  const old=fakeGL(),next=fakeGL(),f=fixture(old),gate=[];f.test.pauseGate=gate;
  const first=f.api.compile(),rejected=assert.rejects(first,{name:'AbortError'});await until(()=>gate.length===1);
  f.replace(next);f.test.pauseGate=null;gate.shift()();await rejected;
  assert.equal(old.objects.length,0);assert.equal(next.objects.length,0);
  await f.api.compile();f.api.disposeRenderer();assert.equal(next.live().length,0);
 });
 console.log(JSON.stringify({passed:true,gpu_execution:false,checks},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
