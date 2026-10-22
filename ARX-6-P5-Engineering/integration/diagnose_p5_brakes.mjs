/* High-rate event diagnosis. Does not modify the frozen model or controller. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import load from '../runtime/node_modules/@mujoco/mujoco/mujoco.js';
const R=path.dirname(fileURLToPath(import.meta.url));
const read=n=>fs.readFileSync(path.join(R,n),'utf8');
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const xml=read('ARX-6-P5.xml'),base=JSON.parse(read('parameters.json'));
const api=JSON.parse(read('../dynamics/interface.json'));
const mj=await load();
const O=path.resolve(process.env.ARX_BRAKE_DIAG_OUT||path.join(R,'diagnostics','brake-events'));
fs.mkdirSync(O,{recursive:true});
const mode=process.env.ARX_BRAKE_DIAG_MODE||'baseline';
const hz=Number(process.env.ARX_BRAKE_DIAG_HZ||2400);
const rate=Number(process.env.ARX_BRAKE_DIAG_REFERENCE_RATE||1);
let controllerSource=read('controller.mjs');
if(rate!==1)controllerSource=controllerSource.replace('let t=time%10;',`let t=(time*${rate})%10;`);
if(mode==='stribeck')controllerSource=controllerSource.replace('speed>.01?b.screening_dynamic_torque_Nm:b.holding_torque_Nm','b.screening_dynamic_torque_Nm+(b.holding_torque_Nm-b.screening_dynamic_torque_Nm)*Math.exp(-(speed/.02)**2)');
const importedSource=controllerSource.replace("from './safety.mjs'",`from '${pathToFileURL(path.join(R,'safety.mjs')).href}'`);
const {ArmSimulation}=await import('data:text/javascript;base64,'+Buffer.from(importedSource).toString('base64'));
fs.writeFileSync(path.join(O,`controller-${mode}-rate${rate}.txt`),controllerSource);
const only=process.argv[2]||null;
const cases=[
 {name:'power_loss_3.2',time:3.2,seconds:4.4,options:{motorOffTime:3.2}},
 {name:'weak_spring_double_delay_3.2',time:3.2,seconds:4.4,options:{motorOffTime:3.2,springScale:.9,brakeDelayScale:2}},
 {name:'weak_spring_double_delay_7.2',time:7.2,seconds:9,options:{motorOffTime:7.2,springScale:.9,brakeDelayScale:2}},
 {name:'stationary_placement_power_loss',time:3.6,seconds:4.8,options:{motorOffTime:3.6,springScale:.9,brakeDelayScale:2}},
];
for(const c of cases){
 if(only&&c.name!==only)continue;
 const faultTime=c.time/rate,seconds=faultTime+c.seconds-c.time;
 const scenarioOptions={...c.options,motorOffTime:faultTime};
 const p=structuredClone(base);
 if(mode==='dynamic40')for(const b of Object.values(p.integration.brakes))b.screening_dynamic_torque_Nm=.4*b.holding_torque_Nm;
 else if(mode==='dynamic40_ramp2')for(const b of Object.values(p.integration.brakes)){
   b.screening_dynamic_torque_Nm=.4*b.holding_torque_Nm;b.ramp_s*=2;
 }
 else if(mode==='ramp2')for(const b of Object.values(p.integration.brakes))b.ramp_s*=2;
 else if(!['baseline','stribeck'].includes(mode))throw new Error('Unknown diagnostic mode '+mode);
 const s=new ArmSimulation(mj,xml,p,api,scenarioOptions);
 if(process.env.ARX_BRAKE_DIAG_HZ)s.model.opt.timestep=1/hz;
 const dt=s.model.opt.timestep,n=Math.round(seconds/dt),stride=Math.round(1/(120*dt)),raw=p.motors.belt_screen_capacity_Nm,allow=p.motors.belt_allowable_output_torque_Nm;
 const names=Array.from({length:s.model.ngeom},(_,i)=>mj.mj_id2name(s.model,5,i));
 const maxTorque=new Array(6).fill(0),peak=new Array(6).fill(null),aboveAllow=new Array(6).fill(0),aboveRaw=new Array(6).fill(0),events=Array.from({length:6},()=>[]),active=new Array(6).fill(null);
 const settledMax=new Array(6).fill(0),lastAbove=new Array(6).fill(null),rows=[];
 let faultQ=null,maxDrift=new Array(6).fill(0),minHardMargin=Infinity,maxStructuralPen=0;
 function contacts(){
   const cs=s.data.contact,out=[];
   try{for(let k=0;k<cs.size();k++){
     const cc=cs.get(k);
     try{
       if(cc.dist>0)continue;
       mj.mj_contactForce(s.model,s.data,k,s.forceBuffer);
       out.push({pair:[names[cc.geom1],names[cc.geom2]],distance_m:cc.dist,local_force_N_Nm:Array.from(s.forceBuffer.GetView())});
     }finally{cc.delete();}
   }}finally{cs.delete();}
   return out;
 }
 mj.mj_kinematics(s.model,s.data);
 for(let k=0;k<n;k++){
   const preQ=Array.from(s.data.qpos.slice(0,6));
   s.step();
   const t=s.steps*dt,acc=Array.from(s.data.qvel.slice(0,6),(x,i)=>(x-s.preStepVelocity[i])/dt);
   const belt=acc.map((a,i)=>s.torque[i]-s.model.dof_armature[i]*a);
   if(!faultQ&&s.safety.faultTime!=null)faultQ=preQ;
   for(let j=0;j<6;j++){
     const v=Math.abs(belt[j]);
     minHardMargin=Math.min(minHardMargin,s.data.qpos[j]-p.integration.joint_hard_limits_rad[j][0],p.integration.joint_hard_limits_rad[j][1]-s.data.qpos[j]);
     if(v>maxTorque[j]){
       maxTorque[j]=v;
       peak[j]={time_s:t,step:k,belt_torque_Nm:belt[j],pre_q_rad:preQ,q_rad:Array.from(s.data.qpos.slice(0,6)),pre_velocity_rad_s:s.preStepVelocity.slice(),velocity_rad_s:Array.from(s.data.qvel.slice(0,6)),acceleration_rad_s2:acc,motor_generated_torque_Nm:Array.from(s.torque),brake_capacity_Nm:Array.from(s.brakeCapacity),brake_actual_torque_Nm:Array.from(s.brakeTorque),qfrc_constraint_Nm:Array.from(s.data.qfrc_constraint.slice(0,6)),qfrc_bias_Nm:Array.from(s.data.qfrc_bias.slice(0,6)),qfrc_applied_Nm:Array.from(s.data.qfrc_applied.slice(0,6)),contacts:contacts(),puck_qpos:Array.from(s.data.qpos.slice(8,15)),puck_velocity:Array.from(s.data.qvel.slice(8,14))};
     }
     if(v>allow[j]){
       aboveAllow[j]+=dt;
       if(active[j]===null)active[j]={start_s:t-dt,end_s:t,steps:1,peak_Nm:v};
       else{active[j].end_s=t;active[j].steps++;active[j].peak_Nm=Math.max(active[j].peak_Nm,v);}
     }else if(active[j]!==null){events[j].push(active[j]);active[j]=null;}
     if(v>raw[j])aboveRaw[j]+=dt;
     if(faultQ){
       maxDrift[j]=Math.max(maxDrift[j],Math.abs(s.data.qpos[j]-faultQ[j]));
       if(Math.abs(s.data.qvel[j])>.002)lastAbove[j]=t;
       if(t>faultTime+.5)settledMax[j]=Math.max(settledMax[j],Math.abs(s.data.qvel[j]));
     }
   }
   if(t>=faultTime-.02){
     const cs=contacts();for(const cc of cs)if(!cc.pair.includes('puck'))maxStructuralPen=Math.max(maxStructuralPen,-cc.distance_m);
     rows.push({t,q:Array.from(s.data.qpos.slice(0,6)),v:Array.from(s.data.qvel.slice(0,6)),belt,brake_capacity:Array.from(s.brakeCapacity),brake_torque:Array.from(s.brakeTorque),contacts:cs.map(x=>({pair:x.pair,distance_m:x.distance_m,normal_force_N:x.local_force_N_Nm[0]}))});
   }
   if((k+1)%stride===0||k+1===n)mj.mj_kinematics(s.model,s.data);
 }
 for(let j=0;j<6;j++)if(active[j])events[j].push(active[j]);
 const summary={case:c.name,mode,hz,dt_s:dt,reference_rate:rate,physical_fault_time_s:faultTime,date:new Date().toISOString(),scenario_options:scenarioOptions,brake_spec:p.integration.brakes,
   provenance:{model:sha(xml),controller:sha(read('controller.mjs')),diagnostic_controller:sha(controllerSource),parameters:sha(read('parameters.json')),diagnostic_script:sha(read('diagnose_p5_brakes.mjs'))},
   raw_capacity_Nm:raw,service_allowance_Nm:allow,peak_estimated_belt_torque_Nm:maxTorque,above_allowance_total_s:aboveAllow,above_raw_capacity_total_s:aboveRaw,above_allowance_events:events,peak_events:peak,
   max_speed_after_fault_plus_half_second_rad_s:settledMax,last_time_speed_over_0p002_rad_s:lastAbove,final_speed_rad_s:Array.from(s.data.qvel.slice(0,6)),max_drift_deg:maxDrift.map(x=>x*180/Math.PI),min_hard_margin_rad:minHardMargin,max_structural_penetration_m:maxStructuralPen,
   interpretation:'Rigid transmission diagnostic; upstream rotor inertia is included. Event duration is an integration-step duration, not a catalog impulse allowance. Non-baseline brake parameters are sensitivity assumptions, not newly qualified hardware specifications.'};
 const tag=`${c.name}-${mode}-rate${rate}-${hz}`;
 fs.writeFileSync(path.join(O,`${tag}-summary.json`),JSON.stringify(summary,null,2)+'\n');
 fs.writeFileSync(path.join(O,`${tag}-events.json`),JSON.stringify({summary,rows}));
 console.log(JSON.stringify({case:c.name,mode,hz,rate,peak:maxTorque,above_allowance_s:aboveAllow,above_raw_s:aboveRaw,settledMax,final_speed:summary.final_speed_rad_s,minHardMargin,maxStructuralPen}));
 s.destroy();
}
