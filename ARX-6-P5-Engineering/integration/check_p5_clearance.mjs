/* Independent rigid-proxy geometry screen. These are posed clearance checks,
 * not dynamics trajectories. Pair distances also inspect any excluded pair. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import load from '../runtime/node_modules/@mujoco/mujoco/mujoco.js';

const R=path.dirname(fileURLToPath(import.meta.url));
const read=n=>fs.readFileSync(path.join(R,n),'utf8');
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const xml=read('ARX-6-P5.xml'),p=JSON.parse(read('parameters.json'));
const tracePath=process.env.ARX_CLEARANCE_TRACE?path.resolve(process.env.ARX_CLEARANCE_TRACE):path.join(R,'results/nominal.json');
const traceText=fs.readFileSync(tracePath,'utf8'),trace=JSON.parse(traceText);
const reportPath=process.env.ARX_CLEARANCE_REPORT?path.resolve(process.env.ARX_CLEARANCE_REPORT):path.join(R,'reports/P5-clearance-sweep.json');
if(p.model_revision!=='P5'||trace.metrics.provenance.xml_sha256!==sha(xml))throw new Error('Fresh P5 nominal trace and matching model required');
const mj=await load();mj.FS.writeFile('/p5-clearance.xml',xml);
const m=mj.MjModel.mj_loadXML('/p5-clearance.xml'),d=new mj.MjData(m),segment=new mj.DoubleBuffer(6);
mj.mj_resetDataKeyframe(m,d,0);
const home=Array.from(d.qpos.slice(0,6));
const count=m.ngeom,names=Array.from({length:count},(_,i)=>mj.mj_id2name(m,5,i));
const bodyNames=Array.from({length:m.nbody},(_,i)=>mj.mj_id2name(m,1,i));
const bodies=Array.from(m.geom_bodyid),welds=bodies.map(b=>m.body_weldid[b]);
const puck=mj.mj_name2id(m,1,'puck'),types=Array.from(m.geom_type),sizes=Array.from(m.geom_size);
let pairCount=0;
for(let a=0;a<count;a++)for(let b=a+1;b<count;b++){
  if(welds[a]===welds[b]||bodies[a]===puck||bodies[b]===puck)continue;
  pairCount++;
}
const nearLimit=.005,threshold=.0001;
function bounds(){
  const pos=d.geom_xpos,rot=d.geom_xmat,result=[];
  for(let g=0;g<count;g++){
    const size=sizes.slice(g*3,g*3+3),half=[];
    for(let axis=0;axis<3;axis++){
      const r0=rot[g*9+axis*3],r1=rot[g*9+axis*3+1],r2=rot[g*9+axis*3+2];
      if(types[g]===6)half.push(Math.abs(r0)*size[0]+Math.abs(r1)*size[1]+Math.abs(r2)*size[2]);
      else if(types[g]===5)half.push(size[0]*Math.sqrt(Math.max(0,1-r2*r2))+Math.abs(r2)*size[1]);
      else if(types[g]===3)half.push(size[0]+Math.abs(r2)*size[1]);
      else if(types[g]===2)half.push(size[0]);
      else half.push(m.geom_rbound[g]);
    }
    result.push([pos[g*3],pos[g*3+1],pos[g*3+2],...half]);
  }
  return result;
}
function separation(a,b){
  let sum=0;for(let i=0;i<3;i++){const gap=Math.max(0,Math.abs(a[i]-b[i])-a[i+3]-b[i+3]);sum+=gap*gap;}
  return Math.sqrt(sum);
}
function screen(label,states){
  let maxPen=0,distanceCalls=0;const nearPairs=new Map(),intersections=new Map();
  for(const state of states){
    d.qpos.set(state.q,0);d.qvel.fill(0);mj.mj_forward(m,d);
    const boxes=bounds();
    const order=Array.from({length:count},(_,i)=>i).sort((a,b)=>(boxes[a][0]-boxes[a][3])-(boxes[b][0]-boxes[b][3]));
    for(let ai=0;ai<count;ai++)for(let bi=ai+1;bi<count;bi++){
      const a=order[ai],b=order[bi];
      if(boxes[b][0]-boxes[b][3]>boxes[a][0]+boxes[a][3]+nearLimit)break;
      if(welds[a]===welds[b]||bodies[a]===puck||bodies[b]===puck)continue;
      if(separation(boxes[a],boxes[b])>nearLimit)continue;
      const distance=mj.mj_geomDistance(m,d,a,b,nearLimit,segment);distanceCalls++;
      if(distance>=nearLimit)continue;
      const [ga,gb]=a<b?[a,b]:[b,a],key=names[ga]+' / '+names[gb];
      const pairBodies=[bodyNames[bodies[ga]],bodyNames[bodies[gb]]];
      const item={pair:key,bodies:pairBodies,category:pairBodies.some(b=>b==='world'||b==='fixed_hardware')?'arm to fixture':'moving arm bodies',minimum_signed_distance_mm:distance*1000,state:state.label,q_rad:state.q};
      if(!nearPairs.has(key)||distance*1000<nearPairs.get(key).minimum_signed_distance_mm)nearPairs.set(key,item);
      if(distance<0)maxPen=Math.max(maxPen,-distance);
      if(distance<-threshold&&(!intersections.has(key)||distance*1000<intersections.get(key).minimum_signed_distance_mm))intersections.set(key,item);
    }
  }
  return {name:label,states:states.length,maximum_penetration_mm:maxPen*1000,
    no_penetration_above_0p1_mm:maxPen<threshold,distance_evaluations:distanceCalls,
    intersecting_pairs:[...intersections.values()].sort((a,b)=>a.minimum_signed_distance_mm-b.minimum_signed_distance_mm),
    closest_pairs:[...nearPairs.values()].sort((a,b)=>a.minimum_signed_distance_mm-b.minimum_signed_distance_mm).slice(0,30),
    closest_revised_component_pairs:[...nearPairs.values()].filter(p=>/P5_J[1-6]_/.test(p.pair)).sort((a,b)=>a.minimum_signed_distance_mm-b.minimum_signed_distance_mm).slice(0,30)};
}
const nominal=[];
for(let i=0;i<trace.frames.length;i+=10)nominal.push({label:`nominal t=${trace.frames[i][0].toFixed(6)} s`,q:trace.frames[i].slice(1,7)});
const groups=[screen('actual nominal trajectory sampled every 1/12 s',nominal)];
if(!process.argv.includes('--nominal-only')){
  const oneJoint=[];
  for(let axis=0;axis<6;axis++)for(let n=0;n<=60;n++){
    const q=home.slice(),range=p.integration.joint_hard_limits_rad[axis];q[axis]=range[0]+(range[1]-range[0])*n/60;
    oneJoint.push({label:`J${axis+1} isolated hard-range sample ${n}/60; other joints at home`,q});
  }
  groups.push(screen('individual hard-range sweeps about home',oneJoint));
  function halton(n,base){let f=1,value=0;while(n){f/=base;value+=f*(n%base);n=Math.floor(n/base);}return value;}
  const primes=[2,3,5,7,11,13],coupled=[];
  for(let n=1;n<=216;n++)coupled.push({label:`coupled soft-range Halton sample ${n}/216`,q:primes.map((base,i)=>{
    const [a,b]=p.integration.joint_soft_limits_rad[i];return a+(b-a)*halton(n,base);
  })});
  groups.push(screen('coupled soft-range geometric samples',coupled));
}
const report={revision:'P5',date_utc:new Date().toISOString(),model_sha256:sha(xml),nominal_trace_sha256:sha(traceText),
  scope:'Exact MuJoCo primitive pair distances for represented rigid material, including excluded contact pairs. Same welded-body material and the intentional puck interactions are omitted. No flexible belt/spring/cable geometry or manufacturing tolerance. The off-path samples are geometric poses, not commanded or dynamically executed trajectories; sampling is not an exhaustive configuration-space proof.',
  minimum_clearance_search_band_mm:nearLimit*1000,penetration_threshold_mm:threshold*1000,geom_count:count,cross_body_pairs:pairCount,groups};
fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(groups.map(g=>({name:g.name,states:g.states,maximum_penetration_mm:g.maximum_penetration_mm,intersecting_pairs:g.intersecting_pairs.slice(0,10),distance_evaluations:g.distance_evaluations})),null,2));
segment.delete();d.delete();m.delete();
if(!groups[0].no_penetration_above_0p1_mm)process.exitCode=1;
